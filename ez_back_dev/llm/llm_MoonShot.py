from langchain_community.llms.moonshot import Moonshot
import os

os.environ["MOONSHOT_API_KEY"] = "your_api_key"


class MoonShotModel:
    def __init__(self):
        self.model = Moonshot()

    def get_model(self):
        return self.model
