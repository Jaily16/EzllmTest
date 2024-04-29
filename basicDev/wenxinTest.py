from langchain_wenxin import ChatWenxin

WENXIN_APP_Key = "vfEiNO9e9oI86VwhMG2gbvRN"
WENXIN_APP_SECRET = "bhFyrPHo7t1hQnGOQUj9Mn1vTdetk7Xd"
#
llm = ChatWenxin(
model="wenxin", baidu_api_key=WENXIN_APP_Key, baidu_secret_key=WENXIN_APP_SECRET
)

response = llm.invoke("你好")
print(response)