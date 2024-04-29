import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

# 用户提供的知识库有多个，业务文档也可能有多个，要解决读取多个知识库的问题，考虑都采取建立多个向量索引库的方式，id取数据库中随机生成的唯一id

# 每个业务项目都有自己的文件夹
project_path = "project/p001/"

knowledge_pdfs = ['软件测试方法和技术-部署测试环境', '软件测试方法和技术-测试方法',
                  '软件测试方法和技术-测试需求分析与测试计划',
                  '软件测试方法和技术-单元测试', '软件测试方法和技术-集成测试', '软件测试方法和技术-软件本地化测试',
                  '软件测试方法和技术-验收测试', '软件测试-编写和跟踪测试用例', '软件测试-动态白盒测试',
                  '软件测试-动态黑盒测试',
                  '软件测试-计划测试工作', '软件测试-兼容性测试', '软件测试-静态白盒测试', '软件测试-静态黑盒测试',
                  '软件测试-配置测试', '软件测试-缺陷轰炸和beta测试', '软件测试-软件安全性测试',
                  '软件测试-外国语言测试',
                  '软件测试-易用性测试', '软件测试-网站测试', '软件测试-自动测试和测试工具']

test_pdfs = ['测试业务1-Java控制台实现教务管理系统']

os.environ["OPENAI_API_KEY"] = "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"


# 将文档转换成向量进行保存
def load_and_save_doc(doc, splitter, embeddings, path):
    pages = splitter.split_documents(doc)
    db = FAISS.from_documents(pages, embeddings)
    db.save_local(path)


knowledge_text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=2000,
    chunk_overlap=100,
)

test_text_splitter = CharacterTextSplitter(
    separator="\n\n",
    chunk_size=1000,
    chunk_overlap=100,
)

embeddings = OpenAIEmbeddings()

# 存储知识库，因为逐个文档检索的效率太差了，改为融合成为单个知识库检索
i = 0
know_big_doc = []
for pdf in knowledge_pdfs:
    source_path = "knowledge/" + pdf + ".pdf"
    loader = PyPDFLoader(source_path)
    doc = loader.load_and_split()
    know_big_doc += doc

inter_path = project_path + "integration_knowledge/faiss_index"
load_and_save_doc(know_big_doc, knowledge_text_splitter, embeddings, inter_path)
print("融合知识库存储完成")


# 存储业务文档
# i = 0
# for pdf in test_pdfs:
#     source_path = "testDoc/" + pdf + ".pdf"
#     loader = PyPDFLoader(source_path)
#     doc = loader.load_and_split()
#     index_path = project_path + "test/" + "test_" + str(i) + "_faiss_index"
#     load_and_save_doc(doc, test_text_splitter, embeddings, index_path)
#     print("业务文档" + str(i) + "存储完成")
#     i += 1

# loader = PyPDFLoader(path)
# pages = loader.load_and_split()

# new_pages = text_splitter.split_documents(pages)
# embeddings = OpenAIEmbeddings()
# db = FAISS.from_documents(new_pages, embeddings)

# query = "模块划分"
# docs = db.similarity_search(query)
