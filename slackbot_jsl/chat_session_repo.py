import os, glob
import nest_of_utils as noutils
from openai.types.chat import ChatCompletion, ChatCompletionUserMessageParam, \
    ChatCompletionAssistantMessageParam, ChatCompletionMessageParam, ChatCompletionMessage

class chat_session_repo:
    def __init__(self, context_length:int = 8):
        self.current_sessions:dict[str,list[ChatCompletionMessageParam]] ={}
        self.context_length = context_length
        
    def __put_messages(self, user_id:str, messages:list[ChatCompletionMessageParam]) -> None:
        self.current_sessions[user_id] = messages[-self.context_length:]

    def append_message_by_openai_resp(self, user_id:str, openai_resp:ChatCompletion) -> None:
        self.append_message(user_id, openai_resp.choices[0].message)


    def append_message(self, user_id:str, message:ChatCompletionMessageParam) -> None:
        if len(self.current_sessions[user_id]) == self.context_length:
            self.current_sessions[user_id].pop(0)
        elif len(self.current_sessions[user_id]) > self.context_length:
            self.__put_messages(user_id, self.current_sessions[user_id][-(self.context_length-1):])
        self.current_sessions[user_id].append(message)

    def get_messsages(self, user_id:str) -> list[ChatCompletionMessageParam]:
        """
        ユーザーのセッションから全メッセージを取得します。
        存在しない場合、historyファイルから会話履歴を取得
        """
        if user_id not in self.current_sessions:
            self.__put_messages(user_id, self.__get_messages_from_history(user_id))
        return self.current_sessions.get(user_id, [])[-self.context_length:]

    def __get_messages_from_history(self, user_id:str) -> list[ChatCompletionMessageParam]:
        """
        historyファイルから会話履歴を取得
        """
        print(os.getcwd())
        resList = [ ChatCompletionAssistantMessageParam(**noutils.filter_dic(res['choices'][0]['message'], ['role', 'content'])) for res 
                in noutils.load_json_files(glob.glob(f'./history/gpt_response_{user_id}*.json'), self.context_length // 2, islast=True)]
        reqList = [ ChatCompletionUserMessageParam(role="user", content=f"{req['event']['text']}") for req 
                in noutils.load_json_files(glob.glob(f'./history/gpt_slack_request_{user_id}*.json'), self.context_length // 2, islast=True)]
        return [elem for pair in zip(reqList, resList) for elem in pair]

