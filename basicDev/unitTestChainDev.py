import os
from functools import partial
from operator import itemgetter
from typing import List

from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate, format_document, ChatPromptTemplate
from llm import chatGPTModel
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.pydantic_v1 import BaseModel, Field
from chain import BasicChain
from langchain_core.documents import Document

os.environ["OPENAI_API_KEY"] = "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"
os.environ["LANGCHAIN_API_KEY"] = "ls__8f1d0a23c4cb4c9d8b58076ba3de84c7"
os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Unit_Test_Dev"

llm_model = chatGPTModel.ChatGPTModel()
testDocVecPath = "project/p001/test/test_0_faiss_index"


# 定义一个工具类，将Document类连接成为字符串
def docs_to_string(docs):
    return "\n\n".join(format_document(doc, document_prompt) for doc in docs)


# 从某个知识库中搜索相关文档信息
def search_relevant_info_from_doc(vector_path, embeddings, query):
    db = FAISS.load_local(vector_path, embeddings, allow_dangerous_deserialization=True)
    relevant_docs = db.similarity_search(query)
    return relevant_docs


# 定义模块类(记录业务中有哪几个模块)
class Model(BaseModel):
    models: List[str] = Field(description="该业务中含有哪些模块")


# 定义类类
class Class(BaseModel):
    classes: List[str] = Field(description="该业务中含有哪些类")


# 定义函数类
class Function(BaseModel):
    functions: List[str] = Field(description="该业务中含有哪些函数")


# 定义测试方法类
class StaticBlackBoxMethod(BaseModel):
    methods: List[str] = Field(description="适用哪些静态黑盒测试方法，每一项为一种测试方法名称")


class StaticWhiteBoxMethod(BaseModel):
    methods: List[str] = Field(description="适用哪些静态白盒测试方法，每一项为一种测试方法名称")


class UnitTestMethod(BaseModel):
    block_box: bool = Field(description="是否能进行静态黑盒测试")
    white_box: bool = Field(description="是否能进行静态白盒测试")


parser = JsonOutputParser(pydantic_object=Function)

document_prompt = PromptTemplate.from_template("{page_content}")

# 测试使用stuff链对用于单元测试的模块/子系统/类/函数进行划分
# 模块的相关信息

module_info_doc = search_relevant_info_from_doc(testDocVecPath,
                                                llm_model.getEmbeddings(), "模块划分的列表，每一项为一个模块名称")
class_info_doc = search_relevant_info_from_doc(testDocVecPath,
                                               llm_model.getEmbeddings(), "类划分的列表，每一项为一个类名称")
function_info_doc = search_relevant_info_from_doc(testDocVecPath,
                                                  llm_model.getEmbeddings(), "函数划分的列表，每一项为一个函数名称")

# 加载业务文档
loader = PyPDFLoader("testDoc/测试业务1-Java控制台实现教务管理系统.pdf")
pages = loader.load_and_split()

summary_query = "请对下面的业务文档进行整理，要求文档的内容和结构全部完整保留，同时去除无意义的符号和字符，业务文档如下:"
test_doc_str = "BasicChain.BasicChain.invoke_stuff_chain_get_str(summary_query, pages, llm_model.getModel())"

module_query = "请根据以下业务内容描述，仅从文档给出的内容分析该软件业务划分为哪几个模块，业务内容如下:\n\n" + test_doc_str
class_query = "请根据以下业务内容描述，仅从文档给出的内容分析该软件业务划分为哪几个类，业务内容如下:\n\n" + test_doc_str
function_query = "请根据以下业务内容描述，仅从文档给出的内容分析该软件业务划分为哪几个函数，业务内容如下:\n\n" + test_doc_str

prompt = PromptTemplate(
    template="请回答下面的问题: \n{query}\n\n{format_instructions}\n如果输出的是代码块，请不要包含首尾的```符号",
    input_variables=["query"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)

analyze_chain = prompt | llm_model.getModel() | parser
# analyze = analyze_chain.invoke({"query": function_query})
# 问题不大

# 加载所有知识库，知识库采用refine链进行总结
# relevant_knowledge_docs = []
# for i in range(21):
#     knowledge_vec_path = "project/p001/knowledge/knowledge_" + str(i) + "_faiss_index"
#     docs = search_relevant_info_from_doc(knowledge_vec_path, llm_model.getEmbeddings(), "请问如何进行单元测试")
#     relevant_knowledge_docs += docs

# 改为使用融合后的知识库
relevant_knowledge_docs = search_relevant_info_from_doc("project/p001/integration_knowledge/faiss_index",
                                                        llm_model.getEmbeddings(), "请问如何进行单元测试")

# 这一部分可以封装成为类
# 构建工具函数：将Document转换成字符串
partial_format_document = partial(format_document, prompt=document_prompt)

first_prompt = PromptTemplate.from_template("请总结以下内容，使得其意思连贯，字数不得少于原内容字数的一半:\n\n {context}")
context_chain = {"context": partial_format_document} | first_prompt | llm_model.getModel() | StrOutputParser()

refine_prompt = PromptTemplate.from_template(
    "这是之前的总结: {prev_response}."
    "请你将以下的总结内容与之前的内容整合，提取出与单元测试相关的内容，并且使得其语意通顺: {context}."
)

refine_chain = (
        {
            "prev_response": itemgetter("prev_response"),
            "context": lambda x: partial_format_document(x["doc"]),
        }
        | refine_prompt
        | llm_model.getModel()
        | StrOutputParser()
)


def refine_loop(docs, chain):
    summary = context_chain.invoke(docs[0])
    for i, doc in enumerate(docs[1:]):
        summary = chain.invoke({"prev_response": summary, "doc": doc})
    return summary


llm_learnt_about_unit_test = refine_loop(relevant_knowledge_docs, refine_chain)
print(llm_learnt_about_unit_test)

# 使用refine链找出测试方法，外部知识库
# 改为使用融合后的知识库
relevant_method_knowledge_docs = search_relevant_info_from_doc("project/p001/integration_knowledge/faiss_index",
                                                               llm_model.getEmbeddings(),
                                                               "请问软件测试用到的方法有哪些")

# 这一部分可以封装成为类

refine_method_prompt = PromptTemplate.from_template(
    "这是之前的总结: {prev_response}."
    "请你将以下的总结内容与之前的内容整合，并且结合你知道的软件测试方法，整合出有关于软件测试方法(技巧)的内容，"
    "告诉我们软件测试方法有哪些，并且每个方法具体介绍，使得其语意通顺: {context}."
)

refine_method_chain = (
        {
            "prev_response": itemgetter("prev_response"),
            "context": lambda x: partial_format_document(x["doc"]),
        }
        | refine_method_prompt
        | llm_model.getModel()
        | StrOutputParser()
)

# 整理自身知道的软件测试方法
# 加载业务文档
loader_2 = PyPDFLoader("baseknowledge/软件测试方法和技术-测试方法.pdf")
pages_2 = loader_2.load_and_split()

# llm_learnt_about_test_method = refine_loop(relevant_method_knowledge_docs, refine_method_chain)
# print(llm_learnt_about_test_method)


# 利用stuff策略将总结出系统知道的软件测试方法
knowledge_text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=2000,
    chunk_overlap=100,
)

base_pages = knowledge_text_splitter.split_documents(pages_2)

base_method_integration_template = PromptTemplate.from_template("请使用中文将下述有关于软件测试方法的文档进行内容提取，要求"
                                                                "完整提取文档中所提到的所有测试方法，同时每种方法的要进行相应的"
                                                                "介绍，每种方法介绍不得少于700字，以下为软件测试方法文档: \n\n{content}")

base_first_prompt = PromptTemplate.from_template("请用中文对该软件测试方法的文档进行内容提取，提取内容结构清晰且使得其意思连贯，必须保留所有出现过的"
                                                 "软件测试方法以及其介绍，每种方法介绍的字数不得少于800字:\n\n {context}")
base_context_chain = {"context": partial_format_document} | base_first_prompt | llm_model.getModel() | StrOutputParser()

base_refine_prompt = PromptTemplate.from_template(
    "这是之前的软件测试相关方法总结: {prev_response}."
    "请你将以下的总结内容与之前的内容整合，整合出所有的软件测试方法以及其介绍，并且使得其语意通顺: {context}."
)

base_refine_chain = (
        {
            "prev_response": itemgetter("prev_response"),
            "context": lambda x: partial_format_document(x["doc"]),
        }
        | refine_prompt
        | llm_model.getModel()
        | StrOutputParser()
)

# 提取需要测试的模块的全部内容(使用stuff链，以用户交互模块和Student类为例)
uim_query = ("请从业务文档中提取出有关用户交互模块的全部内容，要求内容保留完整，如果有与模块相关联代码要"
             "将代码完整保留，尽量包含完整的输入输出描述以及模块的功能逻辑，下面是业务文档内容:")
uic_query = ("请从业务文档中提取出有关Student类的全部内容，要求内容保留完整，如果有与该类相关联代码要"
             "将代码完整保留，尽量包含完整的输入输出描述以及模块的功能逻辑，同时请忽略文档中一些无意义的符号和乱码，"
             "在正确组织文档的前提下进行分析，下面是业务文档内容:")
user_interaction_class_info = BasicChain.BasicChain.invoke_stuff_chain_get_str(uic_query, pages,
                                                                               llm_model.getModel())
# 判断能进行何种单元测试
unit_test_chain_1 = BasicChain.BasicChain.json_chain(UnitTestMethod, llm_model.getModel())
uwt_query = ("请根据下面的业务类描述，分析仅通过该业务类的描述内容是否为其进行静态黑盒测试并设计用例， 如果能，认为其可以进行静态黑盒测试；"
             "同时分析仅通过该业务类的描述内容是否为其进行静态白盒测试并设计用例，如果有相关代码描述并且足够进行用例的设计，认为其可以进行"
             "静态白盒测试。相关的类内容如下: \n\n") + user_interaction_class_info
unit_test_chain_1.invoke({"query": uwt_query})
# 分析能进行的黑盒测试方法
unit_test_chain_2 = BasicChain.BasicChain.json_chain(StaticBlackBoxMethod, llm_model.getModel())
bla_query = ("请根据下面的业务类描述，请用中文分析仅通过该业务类的描述内容判断"
             "该对该业务类进行单元测试可以使用哪些静态黑盒测试方法，"
             "这里的静态黑盒测试方法指的是软件测试中测试方法技巧，例如边界值划分法、等价类划分法;"
             "要求静态黑盒测试方法尽可能全面有效。相关的类内容如下: \n\n") + user_interaction_class_info
whi_query = ("请根据下面的业务类描述，请用中文分析仅通过该业务类的描述内容判断"
             "该对该业务类进行单元测试可以使用哪些静态白盒测试方法，"
             "这里的静态白盒测试方法指的是软件测试中的白盒测试方法技巧;"
             "要求列出的静态白盒测试方法尽可能全面有效可行。相关的类内容如下: \n\n") + user_interaction_class_info
# blackboxMethod = unit_test_chain_2.invoke({"query": bla_query})
# print(blackboxMethod)
whiteboxMethod = unit_test_chain_2.invoke({"query": whi_query})
print(whiteboxMethod)

# 使用map reduce链对知识库中的相关方法进行总结
method_dict = {}


def summary_test_method_in_knowledge(method_name):
    query = "什么是" + method_name
    method_knowledge_docs = search_relevant_info_from_doc("project/p001/integration_knowledge/faiss_index",
                                                          llm_model.getEmbeddings(),
                                                          query)
    part_query = "请从文本中提取有关与" + method_name + "的相关内容，并且对该方法进行总结描述，要求尽可能详细，文本如下:"
    total_query = "请根据所有的总结内容，整合出" + method_name + "的完整表述，要求字数1000字左右"
    description = BasicChain.BasicChain.invoke_map_reduce_chain_get_str(part_query, total_query,
                                                                        method_knowledge_docs,
                                                                        llm_model.getModel(), 5)
    method_dict[method_name] = description


for name in whiteboxMethod["methods"]:
    summary_test_method_in_knowledge(name)

print(method_dict)

blackbox_knowledge = ""
for name in whiteboxMethod["methods"]:
    blackbox_knowledge += name + ':\n' + method_dict[name] + '\n'

generate_unit_test_case_template = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名优秀的软件测试专家，善于分析软件业务和设计测试用例，同时你学习过以下关于单元测试的知识: \n\n{knowledge}; "
                   "同时你还学习过以下静态白盒测试方法: \n\n{black_knowledge}"),
        ("human", "现有一个软件业务需要做单元测试，需要做单元测试的是该业务中的一个业务类Student类，该业务类的具体描述如下: \n\n{description}\n\n"
                  "请你结合你学习过的单元测试相关知识，同时利用所有你学过的静态白盒测试方法为该业务类生成相应的单元测试用例，生成的单元测试用例格式为，"
                  "用例名称、用例标识、用例说明、输入说明、输出说明、前提和约束、预期测试结果以及平均标准，最后将所有单元测试用例进行综合成为最终版，"
                  "你给出的最终用例设计要做到高覆盖和高效率，并结合类的相关代码相应的给出Junit的测试用例代码")
    ]
)
unit_test_chain = generate_unit_test_case_template | llm_model.getModel() | StrOutputParser()
print(unit_test_chain.invoke({"knowledge": llm_learnt_about_unit_test, "black_knowledge": blackbox_knowledge,
                              "description": user_interaction_class_info}))

# stuff_chain = (
#         {
#             "content": lambda docs: "\n\n".join(
#                 format_document(doc, document_prompt) for doc in docs
#             )
#         }
#         | base_method_integration_template
#         | llm_model.getModel()
#         | StrOutputParser()
# )
# llm_learnt_about_test_method = stuff_chain.invoke(pages_2)

analyse_unit_test_template = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名优秀的软件测试专家，善于分析软件业务和设计测试用例，同时你学习过以下关于单元测试的知识: \n\n{knowledge}"),
        ("human", "请你根据你所学过的知识，对我提供的业务文档进行分析，你需要判断该业务能否做模块的单元测试，如果能，是哪几个模块需要进行"
                  "测试？如果不能，请回答不能的原因；判断该业务能否做子系统的单元测试，如果能，是哪几个子系统？如果不能，请回答原因；判断"
                  "该业务能否做类的单元测试，如果能，是哪几个类？如果不能，请回答原因；判断该业务能否做类中函数的单元测试，如果能，请回答能"
                  "如果不能，请回答原因，以下是业务文档: \n\n{test_doc}"),
    ]
)

analyse_chain = analyse_unit_test_template | llm_model.getModel() | StrOutputParser()

# print(analyse_chain.invoke({"knowledge": llm_learnt_about_unit_test, "test_doc": doc_integrated_by_llm}))
