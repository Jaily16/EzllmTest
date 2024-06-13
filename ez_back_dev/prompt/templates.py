from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# 用于提取单元测试中的相关信息
# 用于stuff链
UNIT_TEST_UNIT_INFO_STUFF_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名软件业务文档分析专家，你需要从用户向你提供的多份软件业务文档中找出业务中有关{unit}的全部信息，"
                   "你的输出结构为:1.{unit}的功能:提取出有关{unit}的功能信息，要求尽可能地详细和完整;2.{unit}的输入信息:"
                   "业务中向{unit}的输入是什么，例如在业务中要使用{unit}的功能需要怎样做等;3.{unit}的输入要求:向unit输入的信息"
                   "有何种限制，例如输入的边界值限制等;4.{unit}的输出信息:{unit}的输出是什么，即使用{unit}后使用者能够得到哪些"
                   "输出;5.{unit}的代码描述:提取出有关{unit}的全部代码描述，代码描述要忠于文档，且完整有注释，"
                   "注意如果文档中找不到相关的代码描述内容，请在对应输出结构的该项"
                   "输出找不到相关信息，请不要自行编造;6.{unit}的其他信息:除了以上5点外你能找到的有关于{unit}的全部其他信息。注意不要总结与{unit}无关的"
                   "信息，以上信息必须尽可能完整详实。"),
        ("human", "以下是我找到的多份业务文档信息:\n{docs}")
    ]
)

# 用于map-reduce链进行format成str即可
UNIT_TEST_UNIT_INFO_MAP_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，你需要从向你提供的业务文档中找出业务中有关{unit}的全部信息，业务文档会向你多次输入"
    "你只需要全部提取此次想你输入文档中有关{unit}的信息即可，例如{unit}的"
    "功能、输入输出、相关代码等信息。注意要完全保留有关{unit}的信息，且"
    "不要加入其他无关{unit}的无效信息，输出尽量在300字以内，以下为此次向你提供的业务文档的部分内容:\n\n"
)
UNIT_TEST_UNIT_INFO_REDUCE_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，你从根据你之前总结的业务文档信息中总结出业务中有关{unit}的全部信息，你"
    "现在需要将这些信息进行整合并且输出，你的输出结构为:1.{unit}的功能:提取出有关{unit}的功能信息，要求尽可能地详细和完整;2.{unit}的输入信息:"
    "业务中向{unit}的输入是什么，例如在业务中要使用{unit}的功能需要怎样做等;3.{unit}的输入要求:向unit输入的信息"
    "有何种限制，例如输入的边界值限制等;4.{unit}的输出信息:{unit}的输出是什么，即使用{unit}后使用者能够得到哪些"
    "输出;5.{unit}的代码描述:提取出有关{unit}的全部代码描述，代码描述要忠于文档，且完整有注释，注意如果文档中找不到相关的代码描述，请在对应输出结构的该项"
    "输出找不到相关信息;6.{unit}的其他信息:除了以上5点外你能找到的有关于{unit}的其他信息。注意不要总结与{unit}无关的"
    "信息，以上信息必须尽可能完整详实。\n\n"
)

# 用于 JSON chain 生成能否做黑白盒测试的判断
UNIT_TEST_TYPE_JSON_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件测试分析专家，请根据下面的软件业务中有关{unit}的描述内容，仅通过该{unit}的描述内容分析是否为其进行静态黑盒测试并设计用例，"
    "如果能，认为其可以进行静态黑盒测试；同时仅通过{unit}的代码相关描述内容分析是否能为其设计静态白盒测试用例，如果有相关代码描述并且该代码足够"
    "完整，通过该代码描述能够进行代码级别的白盒软件测试分析以及相关测试用例的设计，认为其可以进行静态白盒测试，"
    "否则不能。有关{unit}的内容如下: \n\n{content}"
)

# 生成最终测试用例的模板
UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名软件测试专家，善于分析软件业务和设计单元测试用例，以下为你学过的有关于单元测试的相关知识:\n{unit_test_knowledge}.\n"
                   "同时你还精通于使用{static_method}来对软件业务进行单元测试的分析，你学过的有关{static_method}的测试方法知识如下:\n"
                   "{unit_test_method_knowledge}."),
        ("system", "现在你需要根据用户输入的有关{unit}的软件业务文档信息，为{unit}设计一套覆盖全面、执行效率高的软件测试用例。"
                   "你需要结合你所学过的单元测试"
                   "相关知识，分别运用你学过的{static_method}中的各种测试方法的相关知识为{unit}生成测试用例，"
                   "最后再将这些用例去除冗余并且整合成一套完整的测试用例；"
                   "你的测试用例输出格式模板为:\n{case_template}.\n"
                   "你最终只需要按照输出格式，输出一套完整的测试用例即可，两个用例之间要换行输出，不需要对测试用例进行分类"),
        ("human", "以下是我提供的有关于{unit}的业务文档信息:\n{unit_info}")
    ]
)

# 用于测试不同的LLM生成单元测试用例
UNIT_TEST_GENERATE_TEST_CASE_TEMPLATE_2 = PromptTemplate.from_template(
    "你是一名软件测试专家，善于分析软件业务和设计单元测试用例，以下为你学过的有关于单元测试的相关知识:\n\n{unit_test_knowledge}.\n\n"
    "同时你还精通于使用{static_method}来对软件业务进行单元测试的分析，你学过的有关{static_method}的测试方法知识如下:\n\n"
    "{unit_test_method_knowledge}.\n\n"
    "现在你需要根据用户输入的有关{unit}的软件业务文档信息，为{unit}设计一套覆盖全面、执行效率高的软件测试用例。你需要结合你所学过的单元测试"
    "相关知识，分别运用你学过的{static_method}中的各种测试方法的相关知识为{unit}生成测试用例，最后再将这些用例去除冗余并且整合成一套完整的测试用例；"
    "你的测试用例输出格式模板为:\n{case_template}.\n"
    "你最终只需要按照输出格式，输出一套完整的测试用例即可，两个用例之间要换行输出，不需要对测试用例进行分类"
    "以下是我提供的有关于{unit}的业务文档信息:\n{unit_info}"
)

# 用于提取集成测试中的相关信息
# 子系统内集成
INTEGRATION_TEST_INFO_STUFF_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system", "你是一名软件业务文档分析专家，你需要从用户输入的一份到多份软件业务文档中需要找出所有有关该软件业务中"
                   "{integration_unit}内部的{unit_type}如何集成的相关信息。"
                   "你的具体输出结构要求为:1.{integration_unit}的功能:提取出有关{integration_unit}的功能信息，要求尽可能地详细和完整;"
                   "2.{integration_unit}包含的所有{unit_type}信息:{integration_unit}中包含的哪些{unit_type};"
                   "3.{integration_unit}的架构信息:{integration_unit}中的每个{unit_type}是通过何种架构/方式集成到{integration_unit}中的相关信息;"
                   "4.{integration_unit}中各个{unit_type}的协作信息:{integration_unit}中的各个{unit_type}是如何互相协作来实现"
                   "上述第1点中{integration_unit}的相关功能的相关信息；"
                   "5.{integration_unit}与其内部{unit_type}关系的其他信息:除了上述4点外有关{integration_unit}与其中包含的{unit_type}之间关系的其他全部信息。"
                   "注意不要总结其他与{integration_unit}内部的{unit_type}如何集成无关的"
                   "信息，请用中文输出且以上信息必须尽可能完整详实，字数不少于500字，建议在800字左右。"),
        ("human", "以下是我找到的业务文档信息:\n{docs}")
    ]
)

INTEGRATION_TEST_INFO_MAP_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要找出所有有关该软件业务中{integration_unit}内部的{unit_type}如何集成的相关信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。这是对你输入的某一部分该业务文档的内容，你需要提取出上述所说的相关信息，你的具体输出结构要求为:"
    "1.{integration_unit}的功能:提取出有关{integration_unit}的功能信息，要求尽可能地详细和完整，"
    "如果找不到或缺少相关信息请在输出结构的对应位置输出暂无描述；;"
    "2.{integration_unit}包含的所有{unit_type}信息:{integration_unit}中包含的哪些{unit_type}，"
    "如果找不到或缺少相关信息请在输出结构的对应位置输出暂无描述；;"
    "3.{integration_unit}的架构信息:{integration_unit}中的每个{unit_type}是通过何种架构/方式集成到{integration_unit}中的相关信息;"
    "如果找不到或缺少相关信息请在输出结构的对应位置输出暂无描述；;"
    "4.{integration_unit}中各个{unit_type}的协作信息:{integration_unit}中的各个{unit_type}是如何互相协作来实现"
    "上述第1点中{integration_unit}的功能的相关信息。如果找不到或缺少相关信息请在输出结构的对应位置输出暂无描述；"
    "5.{integration_unit}与其内部{unit_type}关系的其他信息:除了上述4点外有关{integration_unit}与其中包含的{unit_type}之间关系的其他全部信息。"
    "注意不要总结其他与{integration_unit}内部的{unit_type}如何集成无关的"
    "信息，请用中文输出且以上信息。要求输出仅保留关键信息，输出内容尽量不超过180个字，并且符合输出结构要求。你每次总结的输出开头为:'部分文档总结如下:'。"
    "不要加入其他无关信息，以下为此次向你提供的业务文档的部分内容:\n\n"
)

INTEGRATION_TEST_INFO_REDUCE_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要找出所有有关该软件业务中{integration_unit}内部的{unit_type}如何集成的相关信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。你前面已经完成了多个部分文档的总结，"
    "此次你需要用中文将之前总结的全部内容进行合并。你具体输出结构要求为:"
    "1.{integration_unit}的功能:提取出有关{integration_unit}的功能信息，要求尽可能地详细和完整;"
    "2.{integration_unit}包含的所有{unit_type}信息:{integration_unit}中包含的哪些{unit_type};"
    "3.{integration_unit}的架构信息:{integration_unit}中的每个{unit_type}是通过何种架构/方式集成到{integration_unit}中的相关信息;"
    "4.{integration_unit}中各个{unit_type}的协作信息:{integration_unit}中的各个{unit_type}是如何互相协作来实现"
    "上述第1点中{integration_unit}的功能的相关信息；"
    "5.{integration_unit}与其内部{unit_type}关系的其他信息:除了上述4点外有关{integration_unit}与其中包含的{unit_type}之间关系的其他全部信息。"
    "注意不要总结其他与{integration_unit}内部的{unit_type}如何集成无关的"
    "信息，且用中文输出且以上信息。请你综合之前总结的全部内容，将此前每次总结中符合上述输出结构的部分合并填入相应的输出结构位置"
    "，同时注意删除明显不符合上述输出结构要求的信息，也要保留此前总结的信息完整性和结构性。"
    "输出结构仅包含上述四点信息即可。你之前的全部的文档总结如下:\n\n"
)

# 用于知识库中集成测试信息的查找
INTEGRATION_TEST_STRATEGY_KNOWLEDGE_TEMPLATE = PromptTemplate.from_template(
    "请用中文介绍一下集成测试中的{strategy}策略,内容包含该{strategy}策略的执行过程、优缺点等,字数为700-900字。"
)

# 生成最终集成测试用例的模板
INTEGRATION_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计集成测试用例，以下为你学过的有关于集成测试的相关知识:\n{integration_test_knowledge}."),
        ("system", "你还精通于使用{static_method}来对软件业务进行集成测试的分析，你学过的有关{static_method}的测试方法知识为:\n"
                   "{blackbox_knowledge}。"),
        ("system", "你还善于使用{strategy}集成测试策略，你学过该集成测试策略的知识如下:\n{strategy_knowledge}。"),
        ("system", "现在你需要根据用户输入的有关{integration_unit}的软件业务文档信息设计集成测试用例，现在假设文档中所提到的构成{integration_unit}的更小单元已经完成了单元测试，"
                   "并且各个单元的功能都能正常运行且符合业务开发设计的需求，请你据此为{integration_unit}设计一套覆盖全面、执行效率高、符合{strategy}策略逻辑"
                   "的集成测试用例。你需要结合你所学过的集成测试相关知识和{strategy}集成测试策略的相关知识，"
                   "采用{strategy}集成测试策略为{integration_unit}进行集成测试分析，同时分别运用你学过的{static_method}中的各种测试方法生成测试用例，"
                   "最后再将这些用例去除冗余并且整合成一套完整的测试用例；你的测试用例输出格式模板为:\n{case_template}.\n"
                   "你最终只需要按照输出格式，输出一套完整的测试用例即可。再次强调你输出的所有测试用例要体现出使用了{strategy}集成测试策略，"
                   "两个用例之间要换行输出,不需要对测试用例进行分类"),
        ("human", "以下是我提供的有关于{integration_unit}的业务文档信息:\n{integration_unit_info}")
    ]
)

# 用于提取业务文档中有关api接口的信息
API_TEST_INFO_TEMPLATE = PromptTemplate.from_template(
    ("你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{api_name}的全部信息。由于整体软件业务文档过大，现在只"
     "向你提供软件业务中出现了{api_name}的相关信息的文档部分，请你从这些文档中完整提取出该软件业务中{api_name}的详细描述。要求完整保留文档中有{api_name}的详细描述。"
     "但是不允许输出与{api_name}无关的信息，该软件业务中含有{api_name}信息的多个相关文档内容如下:\n{docs}")
)

API_TEST_INFO_MAP_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{api_name}的全部信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。这是对你输入的某一部分该业务文档的内容，请你从此次输入的文档中完整提取出该软件业务中{api_name}的详细描述。"
    "请用中文输出且以上信息。要求输出仅保留关键信息，输出内容尽量不超过270个字，你每次总结的输出开头为:'部分文档总结如下:'。"
    "不要加入其他无关信息，以下为此次向你提供的业务文档的部分内容:\n\n"
)

API_TEST_INFO_MAP_REDUCE_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{api_name}的全部信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。你前面已经完成了多个部分文档的信息总结，"
    "此次你需要用中文将之前总结的全部内容进行合并，且用中文输出且以上信息。请你综合之前总结的全部内容，"
    "，同时注意去除冗余和保留此前总结的信息完整性和结构性。你之前的全部的文档总结如下:\n\n"
)

# 生成最终api接口测试用例的模板
APIS_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计api接口测试用例，以下为你学过的有关于api接口测试的相关知识:\n{api_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关该业务中所有api接口的软件业务文档信息设计api接口测试用例。"
                   "请你结合所学过的api接口测试的相关知识，设计一套能全面覆盖文档中所有api接口、执行效率高、且能够采用常见的api接口测试工具进行测试的api接口测试用例。"
                   "你的输出格式为:\n1.api接口测试工具:给出使用何种api接口测试工具对这些api进行测试，并且给出该工具的简介和使用方法；2.api接口测试用例；"
                   "在上述第2点中，你的每个api接口测试用例输出格式模板为:\n{case_template}.\n"
                   "注意你的测试用例要能够使用上述第1点的api接口测试工具进行直接测试，两个用例之间要换行输出，请对api接口生成相应的用例再合并输出。"
                   "不准输出（更多测试用例请见下文）等要多次输出的提示，请一次输出全部测试用例"),
        ("human", "以下是我提供的有关于业务全部api接口的业务文档信息:\n{content}")
    ]
)

API_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计api接口测试用例，以下为你学过的有关于api接口测试的相关知识:\n{api_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关{api_name}的软件业务文档信息设计该api接口的测试用例。"
                   "请你结合所学过的api接口测试的相关知识，设计一套覆盖率好、执行效率高、且能够采用常见的api接口测试工具进行测试的api接口测试用例。"
                   "你的输出格式为:\n1.api接口测试工具:给出使用何种api接口测试工具对这些api进行测试，并且给出该工具的简介和使用方法；2.api接口测试用例；"
                   "3.在测试工具中的对应用例:将上述第2点中的所有测试用例按照使用上述第1点提到的api接口测试工具进行测试时的相应测试用例格式进行输出。\n"
                   "在上述第2点中，你的每个api接口测试用例输出格式模板为:\n{case_template}.\n"
                   "注意你的测试用例要能够使用上述第1点的api接口测试工具进行直接测试，两个用例之间要换行输出"),
        ("human", "以下是我提供的有关于{api_name}的业务文档信息:\n{content}")
    ]
)

# 生成最终前端UI测试用例的模板
UI_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计前端UI测试用例，以下为你学过的有关于前端UI测试的相关知识:\n{ui_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关该业务中所有前端UI设计的详细描述信息,结合所学过的有关于前端UI测试的相关知识"
                   "设计一套优秀的且能够采用常见的前端UI测试工具进行测试的前端UI测试用例。"
                   "你的输出格式为:\n1.前端UI测试工具:给出使用何种前端UI测试工具对这些UI进行测试，并且给出该工具的简介和使用方法；2.前端UI测试用例:"
                   "使用上述第1点提到的前端UI测试工具的相关UI测试用例，用例格式符合该UI测试工具的相应测试用例格式，每个测试用例要有对应的唯一id，"
                   "且最好有十分具体的描述或具体数据；"
                   "注意你的前端UI测试用例要能够使用上述第1点的前端UI工具进行直接测试，两个用例之间要换行输出"),
        ("human", "以下是我提供的有关于业务中前端UI设计的全部业务文档信息:\n{content}")
    ]
)

# 生成最终数据库测试用例的模板
DATABASE_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计数据库测试用例，以下为你学过的有关于数据库测试的相关知识:\n{db_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关该业务中所有数据库设计的详细描述信息, 结合所学过的有关于数据库测试的相关知识"
                   "设计一套优秀的且能够采用常见的数据库测试工具进行测试的数据库测试用例。"
                   "你的输出格式为:\n1.数据库测试工具:给出使用何种数据库测试工具对文档中的数据库进行测试，要求该工具要与业务中使用的数据库相配套，"
                   "并且给出该工具的简介和使用方法；2.数据库测试用例:"
                   "使用上述第1点提到的数据库工具的相关数据库测试用例，用例格式符合该数据库测试工具的相应测试用例格式，每个测试用例要有对应的唯一id；"
                   "且最好有十分具体的描述或具体数据；并且用例要覆盖数据库中的所有表。"
                   "注意你的数据库测试用例要能够使用上述第1点的数据库工具进行直接测试，两个用例之间要换行输出"),
        ("human", "以下是我提供的有关于业务中数据库设计的全部业务文档信息:\n{content}")
    ]
)

# 用于提取业务文档中某个用例的信息
USE_CASE_INFO_TEMPLATE = PromptTemplate.from_template(
    ("你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{use_case_name}的全部信息。由于整体软件业务文档过大，现在只"
     "向你提供软件业务中有关于{use_case_name}的相关文档部分，请你从这些文档中完整提取出该软件业务中{use_case_name}的详细描述。"
     "该软件业务中有关{use_case_name}的一到多个相关文档内容如下:\n{docs}")
)

USE_CASE_INFO_MAP_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{use_case_name}的全部信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。这是对你输入的某一部分该业务文档的内容，请你从此次输入的文档中完整提取出该软件业务中{use_case_name}的详细描述。"
    "请用中文输出且以上信息。要求输出仅保留关键信息，输出内容尽量不超过800个字，你每次总结的输出开头为:'部分文档总结如下:'。"
    "不要加入其他无关信息，以下为此次向你提供的业务文档的部分内容:\n\n"
)

USE_CASE_INFO_MAP_REDUCE_TEMPLATE = PromptTemplate.from_template(
    "你是一名软件业务文档分析专家，现在有一个软件业务需要提取出该业务中{use_case_name}的全部信息。"
    "业务开发文档会划分成多个部分并为你提供多次输入。你前面已经完成了多个部分文档的信息总结，"
    "此次你需要用中文将之前总结的全部内容进行合并，且用中文输出且以上信息。请你综合之前总结的全部内容，"
    "，同时注意去除冗余和保留此前总结的信息完整性和结构性。你之前的全部的文档总结如下:\n\n"
)

# 生成最终功能性测试接口测试用例的模板
FUNCTIONAL_TEST_GENERATE_ALL_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计系统功能性测试用例，以下为你学过的有关于功能性测试的相关知识:\n{functional_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关该业务中所有用例的软件业务文档信息设计系统功能性测试用例。"
                   "请你请你结合学过的有关于功能性测试的相关知识，设计一套能全面覆盖文档中所有用例、执行效率高的系统功能性测试用例。"
                   "你的测试用例输出格式模板为:\n{case_template}.\n"
                   "你最终只需要按照输出格式，输出一套完整的测试用例即可，两个用例之间要换行输出。"),
        ("human", "以下是我提供的有关于业务全部用例描述的业务文档信息:\n{content}")
    ]
)

FUNCTIONAL_TEST_GENERATE_ONE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计系统功能性测试用例，以下为你学过的有关于功能性测试的相关知识:\n{functional_test_knowledge}."),
        ("system", "现在你需要根据用户输入的有关用例{use_case}的软件业务文档信息设计该用例的系统功能性测试用例。"
                   "请你结合学过的有关于功能性测试的相关知识，设计一套能覆盖该用例的所有执行流并且执行效率高的测试用例。"
                   "你的测试用例输出格式模板为:\n{case_template}.\n"
                   "你最终只需要按照输出格式，输出一套完整的测试用例即可，两个用例之间要换行输出。"),
        ("human", "以下是我提供的有关于业务中用例{use_case}的全部业务文档信息:\n{content}")
    ]
)

# 搜索非功能性测试中某一种测试的模板
NONFUNCTIONAL_TEST_KNOWLEDGE_TEMPLATE = PromptTemplate.from_template(
    "请用中文详细解释一下软件测试中的{test_name}，包括{test_name}的介绍、{test_name}的方法技巧、{test_name}的用途等，字数为600-800字。"
)

NONFUNCTIONAL_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计{test_name}用例，以下为你学过的有关于{test_name}的相关知识:\n{knowledge}."),
        ("system", "现在你需要根据用户输入的有关该业务中所有非功能性需求的详细描述信息设计{test_name}的测试用例。"
                   "请你结合学过的{test_name}的相关知识进行相应测试用例的设计，要求每个测试用例有独立的id，两个用例之间要换行输出"),
        ("human", "以下是我提供的有关于业务中非功能性需求的全部业务文档信息:\n{content}")
    ]
)

# 生成最终验收测试用例的模板
ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和设计验收测试用例，以下为你学过的有关于验收测试的相关知识:\n{acceptance_test_knowledge}."),
        ("system", "现在你需要根据用户输入的软件业务的详细描述信息,结合所学过的有关于验收测试的相关知识"
                   "设计一套优秀的验收测试用例。你的验收测试用例要能完全测试到这个软件业务的各个方面，"
                   "用例格式符合验收测试的相应测试用例格式，每个测试用例要有对应的唯一id，"
                   "且最好有十分具体的描述或具体数据；两个用例之间要换行输出"),
        ("human", "以下是我提供的软件业务的相关信息:\n{content}")
    ]
)

ACCEPTANCE_TEST_GENERATE_TEST_CASE_TEMPLATE_2 = PromptTemplate.from_template(
    "你是一名软件测试专家，善于分析软件业务和设计验收测试用例，以下为你学过的有关于验收测试的相关知识:\n{acceptance_test_knowledge}\n."
    "现在你需要根据用户输入的软件业务的详细描述信息,结合所学过的有关于验收测试的相关知识"
    "设计一套优秀的验收测试用例。你的验收测试用例要能完全测试到这个软件业务的各个方面，"
    "用例格式符合验收测试的相应测试用例格式，每个测试用例要有对应的唯一id，"
    "且最好有十分具体的描述或具体数据；两个用例之间要换行输出"
    "以下是我提供的软件业务的相关信息:\n{content}"
)

# 生成测试计划模板
GENERATE_TEST_PLAN_TEMPLATE = ChatPromptTemplate.from_messages(
    [
        ("system",
         "你是一名软件测试专家，善于分析软件业务和制定软件测试计划，以下为你学过的有关于制定软件测试计划的相关知识:\n{test_plan_knowledge}."),
        ("system", "现在你需要根据用户输入的软件业务的详细描述信息,结合所学过的制定软件测试计划的相关知识"
                   "设计一套优秀的软件测试计划。你的软件测试计划需要包括以下内容:\n\n 1.简介 1.1目的 1.2背景 1.3 范围 \n"
                   "2.测试参考文档和测试提交文档 2.1测试参考文档 2.2测试提交文档 \n 3.测试进度 \n"
                   "4.测试资源 4.1人力资源 4.2测试环境 4.3测试工具\n 5.系统风险、优先级 \n "
                   "6.测试策略 6.1数据和数据库完整性测试 6.2接口测试 6.3 集成测试 6.4 功能测试 6.5 用户界面测试 6.6 性能评测 6.7 容量测试"
                   "6.8 安全性和访问控制测试 6.9 故障转移和恢复测试 6.10 配置测试 6.11安装测试\n 7.问题严重度描述 \n 8.与测试有关的任务 \n\n"
                   "请你按照上述内容进行分点输出，为该软件业务生成一份的软件测试计划。注意输入的业务文档信息可能不够具体，但你可以自由发挥，只需要根据向你提供的"
                   "软件业务的相关信息生成一份言之有理的软件测试计划即可。"),
        ("human", "以下是我提供的软件业务的相关信息:\n{content}")
    ]
)
