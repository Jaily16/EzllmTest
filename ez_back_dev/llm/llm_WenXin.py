from langchain_wenxin.chat_models import ChatWenxin

WENXIN_APP_Key = "your_api_key"
WENXIN_APP_SECRET = "your_api_key"
#
llm = ChatWenxin(
    model="wenxin", baidu_api_key=WENXIN_APP_Key, baidu_secret_key=WENXIN_APP_SECRET
)


class WenXinModel:
    def __init__(self):
        self.model = ChatWenxin(
            model="ernie-bot",
            baidu_api_key=WENXIN_APP_Key,
            baidu_secret_key=WENXIN_APP_SECRET
        )

    def get_model(self):
        return self.model
