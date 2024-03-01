# coding: utf-8
import os, json, datetime
from openai import OpenAI
from datetime import datetime
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# slackbotやopenapiのAPIキーはの環境変数に入れておいてね
client = OpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)


current_sessions ={}

# aiの振る舞いを記載したテキストファイルパスを同フォルダに置いておいてね
ai_instructions_file_path = 'ai_instructions.md'

# とりあえずAIへのデフォルト指示(フォールバック)を読み込んでおく
ai_instructions:str = "あなたはなんか賢いかんじのChatBotです。"


def add_message(user_id, message):
    # もしそのユーザの地図がまだ描かれていなかったら、地図を新しく作るんだ✏️
    if user_id not in current_sessions:
        current_sessions[user_id] = []
    # そしてそのユーザの地図に、トークオブジェクトの宝石を埋め込むのさ💎✨
    current_sessions[user_id].append(message)

def get_message(user_id):
    if user_id not in current_sessions:
        return []
    return current_sessions[user_id]
# ボットトークンとソケットモードハンドラーを使ってアプリを初期化します
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# メンション以外、helloを含む場合。権限付けてないので今は有効じゃない
@app.message("hello")
def message_hello(body, say):
    # イベントがトリガーされたチャンネルへ say() でメッセージを送信します
    handle_message(body, say)

# メンション
@app.event("app_mention")
def message_mention(body, say):
    handle_message(body, say)

# DMはメンションついててもついてなくてもこれ
@app.event("message")
def handle_message_events(body, say):
    handle_message(body, say)


def handle_message(body, say):
    '''
    一番大事なコードだよ！
    '''
    print(json.dumps(body,indent=2))
    slack_user_id = body['event']['user']
    write_text_to_file_with_timestamp(f"slack_request_{slack_user_id}.json", json.dumps(body,indent=2), True)
    resp = send_text_to_gpt(body["event"]["text"], slack_user_id)
    print(resp)
    write_text_to_file_with_timestamp(f"gpt_response_{slack_user_id}.json", resp.model_dump_json(indent=2), True)

    reply = resp.choices[0].message.content.strip()
    say(f"<@{slack_user_id}>\r\n{reply}")


def write_text_to_file_with_timestamp(file_path, text, timestamp=False):
    """
    指定されたファイルパスにテキストを書き込む関数です。timestampがTrueの場合、ファイル名にタイムスタンプを追加します。

    引数:
    - filepath (str): テキストを書き込むファイルのパス。
    - text (str): ファイルに書き込むテキスト。
    - timestamp (bool, optional): ファイル名にタイムスタンプを追加するかどうか。デフォルトはFalse。
    """
    if timestamp:
        # ファイルパスを拡張子前と拡張子に分割
        base, ext = os.path.splitext(file_path)
         # 現在の日時を「_yyyyMMdd_hh24mmss」形式で取得
        now = datetime.now().strftime('_%Y%m%d_%H%M%S')
        # タイムスタンプをファイル名に追加
        file_path = f"{base}{now}{ext}"

    # テキストをutf-8でファイルに書き込み
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(text)

    # ファイル作成完了のメッセージ
    print(f"ファイル「{file_path}」を作成したよ😊✨！")


def send_text_to_gpt(text, session_id):
    new_message = {"role": "user", "content": f"{text}"}
    messages = [ {"role": "system", "content": ai_instructions} ]
    messages.extend(get_message(session_id)[:8])
    messages.append(new_message)
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=messages)
    if response.choices[0].finish_reason == 'stop':
        add_message(session_id, new_message)
        add_message(session_id, response.choices[0].message)
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