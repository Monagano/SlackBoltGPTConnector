import logging, os, json, re
import storage_utils, gpt_utils
import nest_of_utils as nou
from dataclasses import dataclass

# デバッグレベルのログを出力します
# 実際に使うスクリプト・アプリではデフォルトの INFO レベルにして
# 必要なログは自分で追加のログを出力するようにしましょう
logging.basicConfig(level=logging.DEBUG)

from slack_sdk import WebClient
from slack_sdk.web.slack_response import SlackResponse
client = WebClient(os.environ["SLACK_BOT_TOKEN"])

@dataclass
class FwSlackMsgState:
    bot_id: str
    user_id: str
    user_message: str
    slack_action: dict | None
    mode: str = "normal"
    isGptAction: bool = True
    resp_message: str = ""

def handle_message(body, say):
    """
    Slackからのメッセージを処理し、OpenAI GPTへの問い合わせとその応答を行います。
    """
    print(json.dumps(body))
    user_id = ""
    if "event" in body:
        if 'user' in body['event']:
            user_id = body['event']['user']
        elif 'message' in body['event'] and 'user' in body['event']['message']:
            user_id = body['event']['message']['user']
    elif "user" in body and "id" in body["user"]:
        user_id = body["user"]["id"]

    state:FwSlackMsgState | None = None
    is_error = False
    try:
        state = build_state(user_id=user_id, body=body)

        # GPT連携ならリクエストして結果を応答に仮セット
        if state.isGptAction:
            state.resp_message = request_gpt_with_state(state=state)

        # 応答送信
        if state.mode == "get_single_file":
            # GPTに作って貰ってた場合を考慮
            state.resp_message = get_file_message(state.resp_message if state.isGptAction else state.user_message)
        if state.mode == "get_filelist":
            say(blocks=make_filelist_message(state.resp_message))
        else:
            say(f"<@{state.user_id}>\r\n{state.resp_message}")
    except Exception as e:
        print(e)
        # TODO キャラクター設定ごとに用意
        say(("<@" + user_id + ">\r\n" if user_id else "")
            + '申し訳ございません。何らかのエラーが発生しました。管理者に問い合わせてくださいなお、チャットの編集やファイルアップロードにはまだ対応しておりません。')
        is_error = True
    finally:
        req_log_name = 'error_' if is_error else ''
        req_log_name += 'gpt_' if state and state.isGptAction else ''
        req_log_name += f'slack_request_{body["event"]["user"]}.json'
        # 成否問わず、リクエストをロギング
        nou.write_text_to_file_with_timestamp(f"./history//{req_log_name}", json.dumps(body,indent=2), True)

def request_gpt_with_state(state:FwSlackMsgState) -> str:
    resp_dump = ""
    is_error = False
    try:
        resp = gpt_utils.send_text_to_gpt(state.user_message, state.user_id)
        print(resp)
        resp_dump = resp.model_dump_json(indent=2)
        if resp.choices[0].finish_reason != "stop":
            raise RuntimeError(f"レスポンス不正(finish_reason):{resp.choices[0].finish_reason}")
        return resp.choices[0].message.content.strip()
    except Exception as e:
        resp_dump = resp_dump or json.dumps(e, indent=2)
        is_error = True
        raise
    finally:
        nou.write_text_to_file_with_timestamp(
            f"./history/{('error_' if is_error else '')}gpt_response_{state.user_id}.json", resp_dump, True)

def build_state(user_id:str, body:dict) -> FwSlackMsgState:
    slack_action = body["actions"][0] if "actions" in body else None
    state = FwSlackMsgState(
        bot_id = body["api_app_id"] if slack_action else body["authorizations"][0]["user_id"],
        user_id = user_id,
        user_message = slack_action["value"] if slack_action else re.sub(rf'<@{user_id}>\s*', '', body["event"]["text"]) , # メンションは消す。
        slack_action = slack_action
    )

    if state.slack_action:
        state.isGptAction = False
        if state.slack_action["action_id"] == "file_choose":
            state.mode = "get_single_file"

    elif any(keyword in state.user_message for keyword in ['社内フォーマット', '社内文書', '手続き書類', '手続書類', '社内様式', '社内書式']):
        if any(keyword in state.user_message for keyword in ['一覧で', '一覧を表示', 'リスト表示', 'リストで', 'ファイル一覧', '一覧化']):
            state.mode = "get_filelist"
            state.user_message = body["event"]["text"] = gpt_utils.mkmsg_file_choose()
        else:
            state.mode = "get_single_file"
            state.user_message = body["event"]["text"] = gpt_utils.mkmsg_file_search(state.user_message)

    return state

def get_file_permalink(upload_file_name:str) -> str:
    '''
    ファイルのパーマリンクを作成
    存在しない場合はアップロードから行う。
    '''
    auth_test = client.auth_test()
    bot_user_id = auth_test["user_id"]
    print(f"App's bot user: {bot_user_id}")
    
    resp_slack:SlackResponse = client.files_list(user=bot_user_id)
    uploaded_files = [file for file in resp_slack.data["files"] if file["name"] == upload_file_name]
    
    if uploaded_files:
        target_file = uploaded_files[0]
    else:
        fbytes = storage_utils.get_file(upload_file_name)
        upload_result = client.files_upload(
            title=upload_file_name,
            filename=upload_file_name,
            content=fbytes,
        )
        target_file = upload_result["file"]

    return target_file["permalink"]

def get_file_message(upload_file_name:str) -> str:
    permalink = get_file_permalink(upload_file_name)
    return f"要求されたファイル: <{permalink}|{upload_file_name}>"

def make_filelist_message(intro_message:str) -> list[dict[str, any]]:
    blocks=[
		{
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": f"*{intro_message}*"
			}
		}]
    blocks += [{
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*{fname}*"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": "選択"
            },
            "action_id": "file_choose",
            "value": f"{fname}"
        }
    } for fname in storage_utils.get_filename_list()]
    return blocks

# アプリを起動します
if __name__ == "__main__":
    result = get_file_permalink('受験エントリー票.xlsx')
    print(result)
    