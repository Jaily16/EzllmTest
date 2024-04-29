import os
from langchain_core.pydantic_v1 import BaseModel, Field
from llm import chatGPTModel
from chain import BasicChain

# 利用langsmith监控运行
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Start_Test_Analyze_Dev"

from functools import partial
from langchain_core.prompts import PromptTemplate, format_document
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders.pdf import PyPDFLoader


# 定义对业务能做何种测试概括结果的Json类型
# 定义单元测试判断类
class UnitTestType(BaseModel):
    unit_test: bool = Field(description="该业务能否做单元测试")
    model_test: bool = Field(description="该业务是否有模块划分")
    subsystem_test: bool = Field(description="该业务是否有子系统划分")
    class_test: bool = Field(description="该业务是否有类划分")
    function_test: bool = Field(description="该业务是否有函数划分")


class IntegrationTestType(BaseModel):
    integrationTest: bool = Field(description="该业务能否做集成测试")
    model_integration: bool = Field(description="该业务是否有模块划分")
    subsystem_integration: bool = Field(description="该业务是否有子系统划分")
    class_integration: bool = Field(description="该业务能否做类的集成测试")
    function_integration: bool = Field(description="该业务能否做函数级别的集成测试")


class ApiTestType(BaseModel):
    api_test: bool = Field(description="该业务能否是网站架构")
    http_api_test: bool = Field(description="该业务能否做网站的api接口测试")


class AcceptanceTestType(BaseModel):
    acceptance_test: bool = Field(description="该业务能否做验收测试")


class NonfunctionalTestType(BaseModel):
    nonfunctional_test: bool = Field(description="该业务能否做非功能性测试")
    press_test: bool = Field(description="该业务能否做非功能性测试中的压力负载测试")
    performance_test: bool = Field(description="该业务能否做非功能性测试中的性能测试")
    configration_test: bool = Field(description="该业务能否做非功能性测试中的配置测试")
    national_test: bool = Field(description="该业务能否做非功能性测试中的本地化(语言)测试")
    safety_test: bool = Field(description="该业务能否做非功能性测试中的安全性测试")
    compatibility_test: bool = Field(description="该业务能否做非功能性测试中的兼容性测试")
    database_test: bool = Field(description="该业务能否做非功能性测试中的数据库测试")


class TestType(BaseModel):
    unit_test_type: UnitTestType = Field(description="业务能否进行单元测试以及能进行的单元测试类型")
    integration_test_type: IntegrationTestType = Field(description="业务能否进行集成测试以及能进行的集成测试类型")
    api_test_type: ApiTestType = Field(description="业务能否进行api接口测试以及能进行的接口测试类型")
    acceptance_test_type: AcceptanceTestType = Field(description="业务能否进行验收测试以及能进行的验收测试类型")
    nonfunctional_test_type: NonfunctionalTestType = Field(
        description="业务能否进行非功能性测试以及能进行的非功能性测试类型")


chatgpt_llm_model = chatGPTModel.ChatGPTModel()

# 按照业务分析需求读入业务文档，开发版只使用了一个文档进行测试，实际上应该逐个读入并且合并Document testDocVecPath = "project/p001/test/test_0_faiss_index"
# test_doc_db = FAISS.load_local(testDocVecPath, chatgpt_llm_model.getEmbeddings(),
# allow_dangerous_deserialization=True) test_analyse_doc = test_doc_db.similarity_search("") print(test_analyse_doc)

# 加载业务文档
loader = PyPDFLoader("testDoc/测试业务1-Java控制台实现教务管理系统.pdf")
pages = loader.load_and_split()

# 业务文档不太可能超出token大小限制，不如整合成一个字符串一次性输入
doc_str = ""

for page in pages:
    doc_str += page.page_content

# map_reduce策略

document_prompt = PromptTemplate.from_template("{page_content}")
# partial 固定format_document的一个参数
partial_format_document = partial(format_document, prompt=document_prompt)

map_chain = (
        {"context": partial_format_document}
        | PromptTemplate.from_template("请总结输入的业务文档内容，要求语意通顺，符合软件业务文档的要求:\n\n{context}")
        | chatgpt_llm_model.getModel()
        | StrOutputParser()
)

reduce_chain = (
        {"context": lambda strs: "\n\n".join(strs)}
        | PromptTemplate.from_template("将以上总结的内容整合成为一个完整的业务文档，如果文档中"
                                       "能找到相关信息，按照下列必要内容组织业务文档，"
                                       "业务文档内容要求包含项目架构、项目模块、项目子系统、"
                                       "项目类划分、项目类内(如果划分了类)函数划分、项目功能性需求、"
                                       "项目非功能性需求、项目api接口以及你认为可以总结的其他软件"
                                       "项目文档应该有的内容部分。业务文档内容如下:\n\n{context}")
        | chatgpt_llm_model.getModel()
        | StrOutputParser()
)

map_reduce = map_chain.map() | reduce_chain
# test_doc_summary = map_reduce.invoke(pages, config={"max_concurrency": 5})

# 对业务文档进行一次概括总结，以分析该业务能做何种测试，直接使用stuff链进行总结尝试
BUSINESS_SUMMARY_PROMPT_STR = ("你是一名软件业务文档的总结专家，你有一份软件业务文档。"
                               "现在请你根据该文档的内容，按照项目架构、"
                               "项目模块划分、项目子系统划分、项目类划分、项目函数划分(如果是类内的"
                               "函数则归类到类划分中)、项目功能性需求(按照用例分析)、项目的非功能性需求、"
                               "项目的api接口划分的文档结构对业务文档进行完整的内容总结；注意:如果"
                               "你发现无法总结出文档的某个部分，例如文档中并没有子系统或api等的描述，请你舍弃"
                               "掉这一部分的总结，文档没有目前提到的内容请不要添加，且不要过度总结"
                               "总结的文档要忠于原文档，且内容足够完整。下面是业务文档内容:")

test_doc_summary = BasicChain.BasicChain.invoke_stuff_chain_get_str(BUSINESS_SUMMARY_PROMPT_STR, pages,
                                                                    chatgpt_llm_model.getModel())
print(test_doc_summary)

# 进行业务文档可以进行何种测试的分析(感觉总结过的文档会不准确，因此直接输入文档全部内容)
parser = JsonOutputParser(pydantic_object=TestType)

software_test_query = "请根据以下业务内容描述，仅从文档给出的内容分析该软件业务能做何种测试，业务内容如下:\n\n" + test_doc_summary
prompt = PromptTemplate(
    template="请回答下面的问题: \n{query}\n\n{format_instructions}\n如果输出的是代码块，请不要包含首尾的```符号",
    input_variables=["query"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

analyze_chain = prompt | chatgpt_llm_model.getModel() | parser
# analyze = analyze_chain.invoke({"query": software_test_query})
