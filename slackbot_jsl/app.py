# coding: utf-8
import os, json, datetime, glob
from openai import OpenAI
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# slackbotやopenapiのAPIキーはの環境変数に入れておいてね
# ボットトークンとソケットモードハンドラーを使ってアプリを初期化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


current_sessions ={}
context_length = 8
# aiの振る舞いを記載したテキストファイルパスを同フォルダに置いておいてね
ai_instructions_file_path = 'ai_instructions.md'

# とりあえずAIへのデフォルト指示(フォールバック)を読み込んでおく
ai_instructions:str = "あなたはなんか賢いかんじのChatBotです。"


def put_messages(user_id, messages):
    current_sessions[user_id] = messages
def get_messsages(user_id, message_count):
    """
    ユーザーのセッションから全メッセージを取得します。
    存在しない場合、historyファイルから会話履歴を取得
    """
    return current_sessions.get(user_id, get_messages_from_history(user_id, message_count))[:message_count]

def get_messages_from_history(user_id, message_count):
    """
    historyファイルから会話履歴を取得
    """
    print(os.getcwd())
    resList = [res['choices'][0]['message'] for res 
               in load_json_files(glob.glob(f'./slackbot_jsl/history/gpt_response_{user_id}*.json'), message_count // 2, islast=True)]
    resList = [whitelist_dic(msg, ['role', 'content']) for msg in resList] # resListの各要素についてrole,content以外は除去
    reqList = [ {"role": "user", "content": f"{req['event']['text']}"} for req 
               in load_json_files(glob.glob(f'./slackbot_jsl/history/slack_request_{user_id}*.json'), message_count // 2, islast=True)]
    return [elem for pair in zip(reqList, resList) for elem in pair]

def whitelist_dic(dic:dict, whitelist:list[str]) -> dict:
    return {k: dic[k] for k in whitelist if k in dic}

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
        say(f"<@{body['event']['message']['user']}>\r\n普通のチャットしか応答できないんだ！ごめんね！\r\n(チャットの編集やファイルアップロードにはまだ対応してないよ！)")
        return
    slack_user_id = body['event']['user']
    user_message = body["event"]["text"]
    print(json.dumps(body,indent=2))
    resp = send_text_to_gpt(user_message, slack_user_id)
    print(resp)
    isSucced = resp.choices[0].finish_reason == "stop"
    write_text_to_file_with_timestamp(
        f"./slackbot_jsl/history/{('' if isSucced else 'error_')}slack_request_{slack_user_id}.json", 
        json.dumps(body,indent=2), True)
    write_text_to_file_with_timestamp(
        f"./slackbot_jsl/history/{('' if isSucced else 'error_')}gpt_response_{slack_user_id}.json", 
        resp.model_dump_json(indent=2), True)

    reply = resp.choices[0].message.content.strip()
    say(f"<@{slack_user_id}>\r\n{reply}")


def write_text_to_file_with_timestamp(file_path, text, timestamp=False, encoding='utf-8'):
    """
    指定されたファイルパスにテキストを書き込む関数です。timestampがTrueの場合、ファイル名にタイムスタンプを追加します。

    引数:
    - filepath (str): テキストを書き込むファイルのパス。
    - text (str): ファイルに書き込むテキスト。
    - timestamp (bool, optional): ファイル名にタイムスタンプを追加するかどうか。デフォルトはFalse。
    - encoding (str): 保存エンコード
    """
    if timestamp:
        # ファイルパスを拡張子前と拡張子に分割
        base, ext = os.path.splitext(file_path)
         # 現在の日時を「_yyyyMMdd_hh24mmss」形式で取得
        now = datetime.now().strftime('_%Y%m%d_%H%M%S')
        # タイムスタンプをファイル名に追加
        file_path = f"{base}{now}{ext}"

    # テキストをutf-8でファイルに書き込み
    with open(file_path, 'w', encoding=encoding) as file:
        file.write(text)

    # ファイル作成完了のメッセージ
    print(f"ファイル「{file_path}」を作成したよ😊✨！")


def load_json_files(files: list[str], n: int, islast: bool = False) -> list[dict]:
    """
    指定されたファイルリストから上位(下位)N件のファイルを読み込み、辞書に変換します。

    Args:
        files (List[str]): ファイルパスのリスト
        n (int): 読み込むファイルの最大数
        islast (bool): 下位をとる
    Returns:
        list[dict]: 読み込んだJSONファイルの内容を辞書に変換したリスト
    """
    top_n_files_content = []
    for file_path in (sorted(files)[-n:] if islast else sorted(files)[:n]):
        with open(file_path, 'r', encoding='utf-8') as file:
            top_n_files_content.append(json.load(file))
    return top_n_files_content

def send_text_to_gpt(text, session_id):
    instructions_message = {"role": "system", "content": ai_instructions}
    messages = get_messsages(session_id, context_length)
    messages.append({"role": "user", "content": f"{text}"})
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=([instructions_message] + messages)) #pythonでprependってこうやるのがいいらしい [obj] + objs
    if response.choices[0].finish_reason == 'stop':
        messages.append(whitelist_dic(response.choices[0].message.model_dump(), ['role', 'content']))
        put_messages(session_id, messages[-context_length:]) #最新だけ残すように気を付けること
    return response

# アプリを起動します
if __name__ == "__main__":
    # 設定ファイルが存在するかチェック
    if not os.path.exists(ai_instructions_file_path):
        ai_instructions_file_path =  os.path.join(os.getcwd(), "slackbot_jsl", ai_instructions_file_path)

    if os.path.exists(ai_instructions_file_path):
        try:
            # ファイルをUTF-8で開いて全文を読み込む
            with open(ai_instructions_file_path, 'r', encoding='utf-8') as file:
                ai_instructions = file.read()
        except Exception as e:
            # 読み込み中のエラーをキャッチした場合、デフォルトの文字列はそのまま
            print(f"ファイル読み込みエラーが発生しました: {e}")
    else:
        # ファイルが存在しない場合、デフォルトの文字列はそのまま
        print("指定されたファイルは存在しません😭")
    # とりあえずBoltのソケット開始！
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()