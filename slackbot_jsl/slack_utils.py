import logging, os, json, re, traceback
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

def handle_message(body, say):
    """
    Slackからのメッセージを処理し、OpenAI GPTへの問い合わせとその応答を行います。
    """
    print(json.dumps(body))
    user_id = get_user_id_from_body(body)
    state:FwSlackMsgState | None = None
    is_error = False
    try:
        # 要求を解析
        state = build_state(user_id=user_id, body=body)

        # GPT連携ならリクエストして結果を応答に仮セット
        gpt_resp = request_gpt_with_state(state=state) if state.isGptAction else None

        # 応答送信
        if state.mode == "get_single_file":
            # GPTに作って貰ってた場合を考慮
            blocks = [get_file_message_block(gpt_resp or state.user_message)]
        elif state.mode == "get_filelist":
            blocks = make_filelist_message_blocks(gpt_resp or state.user_message)
        else:
            blocks = [make_dafault_block(f"<@{state.user_id}>\r\n{gpt_resp}")]
        say(blocks=blocks)
    except Exception as e:
        print(e)
        traceback.print_exc()
        # TODO キャラクター設定ごとに用意
        say(("<@" + user_id + ">\r\n" if user_id else "")
            + '申し訳ございません。何らかのエラーが発生しました。管理者に問い合わせてくださいなお、チャットの編集やファイルアップロードにはまだ対応しておりません。')
        is_error = True
    finally:
        req_log_name = 'error_' if is_error else ''
        req_log_name += 'gpt_' if state and state.isGptAction else ''
        req_log_name += f'slack_request_{user_id}.json'
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
        print(resp_dump)
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
        state.mode = state.slack_action["action_id"]
    elif any(keyword in state.user_message for keyword in ['社内フォーマット', '社内文書', '手続き書類', '手続書類', '社内様式', '社内書式', '社内ファイル']):
        if any(keyword in state.user_message for keyword in ['一覧で', '一覧を表示', 'リスト表示', 'リストで', 'ファイル一覧', '一覧化', '一覧見せて', '一覧を','社内ファイル一覧']):
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

def get_file_message_block(upload_file_name:str) -> dict:
    permalink = get_file_permalink(upload_file_name)
    block = make_dafault_block(f"要求されたファイル: <{permalink}|{upload_file_name}>") 
    block |= make_button_dict_rapped("ファイル一覧はこちら", "get_filelist", "提供ファイル一覧")
    return block

def make_filelist_message_blocks(intro_message:str) -> list[dict[str, any]]:
    blocks=[make_dafault_block(f"*{intro_message}*")]
    blocks += [make_dafault_block(f"*{fname}*") | make_button_dict_rapped("選択", "get_single_file", f"{fname}")
         for fname in storage_utils.get_filename_list()]
    return blocks

def make_dafault_block(message:str) -> dict:
    return {
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": message
			}
		}

def make_button_dict_rapped(button_text:str, action_id:str, value:str) -> dict:
    return {
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": button_text
            },
            "action_id": action_id,
            "value": value
        }
    }

def get_user_id_from_body(body:dict) -> str:
    if "event" in body:
        event = body['event']
        if 'user' in event:
            return event['user']
        elif 'message' in event and 'user' in event['message']:
            return event['message']['user']
    elif "user" in body and "id" in body["user"]:
        return body["user"]["id"]
    return ""

# アプリを起動します
if __name__ == "__main__":
    result = get_file_permalink('受験エントリー票.xlsx')
    print(result)
    