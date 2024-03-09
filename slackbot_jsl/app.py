# coding: utf-8
import os, json, re
import slack_utils
import subprocess
import signal
import sys
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_bolt.adapter.fastapi import SlackRequestHandler
from dotenv import load_dotenv
from fastapi import FastAPI, Request

def terminate_process(proc):
    proc.terminate()  # 子プロセスを終了させる
    proc.wait()       # 子プロセスの終了を待つ

# ローカルではソケットモードが楽
is_socket_mode = os.environ.get("USESOCKET", "YES") == "YES"

# if is_socket_mode:
#     # 子プロセスを起動
#     proc = subprocess.Popen(['python', 'socket_mode_app.py'])
#     # SIGINTやSIGTERMを受け取った際に子プロセスを終了させるハンドラーを設定
#     signal.signal(signal.SIGINT, lambda signum, frame: terminate_process(proc))
#     signal.signal(signal.SIGTERM, lambda signum, frame: terminate_process(proc))

# ローカルの時は実際には使われないけど、関数定義のためにインスタンスを作るよ
# slackbotやopenapiのAPIキーはの環境変数に入れておいてね
app = App(token=os.environ.get("SLACK_BOT_TOKEN"), signing_secret=os.environ.get("SLACK_SIGNING_SECRET"))
app_handler = SlackRequestHandler(app) # FastAPI統合

api = FastAPI()

@app.middleware
def skip_retry(logger, request, next):
    """
    リトライには応答しないよ
    """
    if "x-slack-retry-num" not in request.headers:
        next()

@app.event("app_mention")
def handle_message_mention(body, say):
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

@app.action("file_choose")
def  handle_action_file_choose(body, say):
    """
    ファイル選択アクション受信時の処理。
    """
    slack_utils.handle_message(body, say)

@api.post("/slack/events")
async def endpoint(req: Request):
    """
    ここのエンドポイントでSlack Boltと連携する
    """
    return await app_handler.handle(req)

@api.get("/hogehoge")
async def endpoint(req: Request):
    return {"Hello": "World"}

# @api.get("/fuga")
# async def endpoint(req: Request):
#     app.client.chat_postMessage(channel="#######", text="fuga-")
#     return {"Hello": "World"}

