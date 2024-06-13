from langchain_text_splitters import RecursiveCharacterTextSplitter

# 用于切分业务文档的文本用于对业务文档进行初步分析的切分器
testdoc_text_splitter_for_menu = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=14000,
    chunk_overlap=2000,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对业务文档进行单元信息的提取(划分的大一点这样准很多)
testdoc_text_splitter_for_unit = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=13000,
    chunk_overlap=4000,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对业务文档进行前端ui信息的提取(不需要划分太大)
testdoc_text_splitter_for_ui = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=7000,
    chunk_overlap=1000,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对业务文档进行数据库信息的提取(稍微让一页中能装下所有的数据库表格)
testdoc_text_splitter_for_db = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=9000,
    chunk_overlap=900,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对业务文档进行集成测试信息的提取(划分的更大一点,因为集成的各模块信息在文档中可能比较分散)
testdoc_text_splitter_for_integration = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=14000,
    chunk_overlap=5220,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对业务文档进行用例信息的提取
testdoc_text_splitter_for_use_case = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1900,
    chunk_overlap=200,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档的文本来对需求文档进行信息提取
testdoc_text_splitter_for_acceptance = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=13000,
    chunk_overlap=2000,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务文档进行父文档回溯的文本切割器
# a.用于切割需求文档(由于用例和非功能性需求可能较长因此这样分割)
require_parent_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3000,
    chunk_overlap=800,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)
require_child_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=740,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)
# b.用于切割开发设计文档
design_parent_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=5250,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)
design_child_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1000,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务开发文档查找api知识的文本分割器
testdoc_text_splitter_for_api = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3000,
    chunk_overlap=800,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分业务需求文档查找非功能性需求的文本分割器要切的足够小
testdoc_text_splitter_for_nfunctional = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=800,
    chunk_overlap=100,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)

# 用于切分测试知识库文档的文本切分器
knowledge_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=3500,
    chunk_overlap=800,
    model_name="gpt-3.5-turbo",
    separators=[
        "\n\n",
        "\n",
        " ",
        ".",
        ",",
        "\u200B",  # Zero-width space
        "\uff0c",  # Fullwidth comma
        "\u3001",  # Ideographic comma
        "\uff0e",  # Fullwidth full stop
        "\u3002",  # Ideographic full stop
        "",
    ],
)
