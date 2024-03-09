# coding: utf-8
import os
import slack_utils
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# ローカルの時は実際には使われないけど、関数定義のためにインスタンスを作るよ
# slackbotやopenapiのAPIキーはの環境変数に入れておいてね
app=App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.middleware
def skip_retry(request, next):
    """
    リトライには応答しないよ
    """
    if "x-slack-retry-num" not in request.headers:
        next()

@app.event("app_mention")
def message_mention(body, say):
    """
    アプリがメンションされた時の処理。(DMはDM側で処理)
    """
    slack_utils.handle_message(body, say)

@app.event("message")
def handle_message_events(body, say):
    """
    DMを含むメッセージ受信時の処理。
    """
    slack_utils.handle_message(body, say)

# アプリを起動します
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
