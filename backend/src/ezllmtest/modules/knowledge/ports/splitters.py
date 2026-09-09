"""具名文档切分策略端口；应用无需导入 LangChain splitter 实现。"""
_adapters = {}

def bind(adapters):
    """由 bootstrap 绑定现有策略对象，参数及 Token 边界保持。"""
    _adapters.clear()
    _adapters.update(adapters)

class DocumentSplitter:
    """只暴露文本/文档切分操作，不暴露 provider 或索引实现。"""
    # 记录切分器名称；具体文档处理由对应切分实现承担。
    def __init__(self, name):
        self.name = name
    # 取得 bootstrap 注入的切分实现；缺失装配时失败，不在业务层动态导入 SDK。
    def _implementation(self):
        if self.name not in _adapters:
            raise RuntimeError("runtime_dependencies:splitter_unbound")
        return _adapters[self.name]
    # 把带元数据的文档交给已绑定切分策略，保持来源信息由实现处理。
    def split_documents(self, documents):
        return self._implementation().split_documents(documents)
    # 按当前具名策略切分文本，不自行更换 tokenizer 或块大小。
    def split_text(self, text):
        return self._implementation().split_text(text)
    # 把文本与元数据交给策略生成文档对象，应用层不依赖具体 LangChain 类型构造。
    def create_documents(self, texts, metadatas=None):
        return self._implementation().create_documents(texts, metadatas)

design_child_text_splitter = DocumentSplitter('design_child_text_splitter')
design_parent_text_splitter = DocumentSplitter('design_parent_text_splitter')
knowledge_text_splitter = DocumentSplitter('knowledge_text_splitter')
require_child_text_splitter = DocumentSplitter('require_child_text_splitter')
require_parent_text_splitter = DocumentSplitter('require_parent_text_splitter')
testdoc_text_splitter_for_acceptance = DocumentSplitter('testdoc_text_splitter_for_acceptance')
testdoc_text_splitter_for_api = DocumentSplitter('testdoc_text_splitter_for_api')
testdoc_text_splitter_for_db = DocumentSplitter('testdoc_text_splitter_for_db')
testdoc_text_splitter_for_integration = DocumentSplitter('testdoc_text_splitter_for_integration')
testdoc_text_splitter_for_menu = DocumentSplitter('testdoc_text_splitter_for_menu')
testdoc_text_splitter_for_nfunctional = DocumentSplitter('testdoc_text_splitter_for_nfunctional')
testdoc_text_splitter_for_ui = DocumentSplitter('testdoc_text_splitter_for_ui')
testdoc_text_splitter_for_unit = DocumentSplitter('testdoc_text_splitter_for_unit')
testdoc_text_splitter_for_use_case = DocumentSplitter('testdoc_text_splitter_for_use_case')
