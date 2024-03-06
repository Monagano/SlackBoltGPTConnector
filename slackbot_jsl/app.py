# coding: utf-8
import os, json, re
import nest_of_utils as noutils
import commonmarkslack
from chat_session_repo import chat_session_repo
from openai import OpenAI
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ローカルではソケットモードが楽
is_socket_mode = os.environ.get("USESOCKET", "YES") == "YES"
# slackbotやopenapiのAPIキーはの環境変数に入れておいてね
# ボットトークンとソケットモードハンドラーを使ってアプリを初期化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
if is_socket_mode:
    app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
else:
    app = App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))

# 会話のコンテキスト履歴保持数は8
chat_repo = chat_session_repo(context_length = 8)
# aiの振る舞いを記載したテキストファイルパス
ai_instructions_file_path:str = os.environ.get("GPT_INSTRUCTIONS",'./slackbot_jsl/ai_instructions.md')
ai_instructions:str = ""
parser = commonmarkslack.Parser()
renderer = commonmarkslack.SlackRenderer()

@app.event("app_mention")
def message_mention(body, say):
    """
    アプリがメンションされた時の処理。(DMはDM側で処理)
    """
    handle_message(body, say)

@app.event("message")
def handle_message_events(body, say):
    """
    DMを含むメッセージ受信時の処理。
    """
    handle_message(body, say)


def handle_message(body, say):
    """
    Slackからのメッセージを処理し、OpenAI GPTへの問い合わせとその応答を行います。
    """
    if 'user' not in body['event']:
        # TODO キャラクター設定ごとに用意
        say(f"<@{body['event']['message']['user']}>\r\n申し訳ございません。通常のチャット以外にはまだ未対応です。\r\n(チャットの編集やファイルアップロードにはまだ対応してないよ！)")
        return
    bot_id = body["authorizations"][0]["user_id"]
    slack_user_id = body['event']['user']
    user_message = re.sub(rf'<@{bot_id}>\s*', '', body["event"]["text"]) # メンションは消す。
    print(json.dumps(body))
    try:
        resp = send_text_to_gpt(user_message, slack_user_id)
        print(resp)
        isSucced = resp.choices[0].finish_reason == "stop"
        resp_dump = resp.model_dump_json(indent=2)
    except Exception as e:
        isSucced = False
        resp_dump = json.dumps(e, indent=2)
        return
    finally:
        noutils.write_text_to_file_with_timestamp(
            f"./slackbot_jsl/history/{('' if isSucced else 'error_')}slack_request_{slack_user_id}.json", 
            json.dumps(body,indent=2), True)
        noutils.write_text_to_file_with_timestamp(
            f"./slackbot_jsl/history/{('' if isSucced else 'error_')}gpt_response_{slack_user_id}.json", 
            resp_dump, True)
    
    if isSucced:
        # slackの特殊記法mrkdwnに対応
        ast = parser.parse(resp.choices[0].message.content.strip())
        slack_md = renderer.render(ast)

    reply = slack_md if isSucced else "申し訳ありません。openai-APIでエラーが発生しているようです。"
    say(f"<@{slack_user_id}>\r\n{reply}")


def send_text_to_gpt(text:str, session_id:str):
    '''
    GPTに会話履歴付きでテキストを投げる。
    会話履歴の復元と保存
    失敗時ハンドリングなど。
    '''
    instructions_message = ChatCompletionSystemMessageParam(role="system", content=ai_instructions)
    messages = chat_repo.get_messsages(session_id)
    new_req_message = ChatCompletionUserMessageParam(role="user", content=text)
    messages.append(new_req_message)
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=([instructions_message] + messages)) #pythonでprependってこうやるのがいいらしい [obj] + objs
    if response.choices[0].finish_reason == 'stop':
        # 成功時だよ
        chat_repo.append_message(session_id, new_req_message)
        chat_repo.append_message_by_openai_resp(session_id, response)
    return response

# アプリを起動します
if __name__ == "__main__":
    # 設定ファイル読み込み
    is_success, content = noutils.read_all_text_from_file(ai_instructions_file_path)
    ai_instructions = content if is_success else "あなたはなんか賢いかんじのChatBotです。"
    
    if is_socket_mode:
        # とりあえずBoltのソケット開始！
        SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
    else:
        app.start(port=int(os.environ.get("PORT", 8080)))
