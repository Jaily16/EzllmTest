from langchain_community.chat_models import ChatSparkLLM
from langchain_core.messages import HumanMessage

# 星火3.5
# app_id = 'xx'
# api_key = 'xxx'
# api_secret = 'xxx'

# 星火3.0
app_id = 'your_api_key'
api_key = 'your_api_key'
api_secret = 'your_api_key'


class SparkModel:
    def __init__(self):
        self.model = ChatSparkLLM(
            spark_app_id=app_id, spark_api_key=api_key, spark_api_secret=api_secret
        )

    def get_model(self):
        return self.model

