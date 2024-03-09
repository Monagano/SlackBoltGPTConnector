import os, storage_utils
from chat_session_repo import chat_session_repo
import nest_of_utils as noutils
from openai.types.chat import ChatCompletionUserMessageParam, ChatCompletionSystemMessageParam
from openai import OpenAI


# 会話のコンテキスト履歴保持数は8
chat_repo:chat_session_repo = chat_session_repo(context_length = 8)
# aiの振る舞いを記載したテキストファイルパス
ai_instructions_file_path:str = os.environ.get("GPT_INSTRUCTIONS",'./ai_instructions.md')
# 設定ファイル読み込み
is_success, content = noutils.read_all_text_from_file(ai_instructions_file_path)
ai_instructions = content if is_success else "あなたはなんか賢いかんじのChatBotです。"
# ボットトークンとソケットモードハンドラーを使ってアプリを初期化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def mkmsg_file_search(source_message:str) -> str:
    cs_blobs_dict = storage_utils.get_file_list()
    return f'''
以下のメッセージが求めているファイルがどのファイル名であるか、付属のファイル一覧の中から最も相応しいファイル名1つを選んで、ファイル名のみを返答してください。
■ メッセージ
{source_message}

■ ファイル一覧
''' + "\n".join(["- " + blob_name for blob_name in cs_blobs_dict])

def mkmsg_file_choose() -> str:
    return f'あなたらしい口調で、ファイル一覧から、ダウンロードしたいファイルを一つ選ぶよう促す短いメッセージを作成して、作成したメッセージのみを発言してください。'

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