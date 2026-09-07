from langchain_core.prompts import PromptTemplate, format_document
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableLambda
from functools import partial
import json
from operator import itemgetter

from llm.provider import LLMOutputParsingError
from tools import documentTools


LEGACY_REDUCE_CONTEXT_TOKENS = 32_000
LEGACY_REDUCE_MAX_LEVELS = 8


def _partition_summaries_within_budget(summaries, *, max_tokens):
    """分组摘要within预算，并遵循现有调用契约。

    参数:
        `summaries`：调用方传入的现有参数。
        `max_tokens`：调用方传入的现有参数。

    异常:
        `ValueError`：输入、状态或下游结果不满足现有约束时抛出。"""

    batches = []
    current = []
    current_tokens = 0
    for summary in summaries:
        summary_tokens = documentTools.num_tokens_from_string(summary)
        if summary_tokens > max_tokens:
            raise ValueError("one map summary exceeds the reduce context budget")
        if current and current_tokens + summary_tokens > max_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(summary)
        current_tokens += summary_tokens
    if current:
        batches.append(current)
    return batches


# 用BasicChain类统一整合stuff、mapreduce和refine链,用于灵活调整大语言模型
class BasicChain:
    # 输入document进行stuff链提问
    @staticmethod
    def invoke_stuff_chain_get_str(demand_str, documents, llm):
        """调用stuff chainGET STR，并遵循现有调用契约。

        参数:
            `demand_str`：调用方传入的现有参数。
            `documents`：调用方传入的现有参数。
            `llm`：调用方传入的现有参数。

        副作用:
            可能按现有预算与模型选择发起 provider 或 embedding 调用。

        不变量:
            模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
        doc_str = " \n\n{content}"
        stuff_query = demand_str + doc_str
        template = PromptTemplate.from_template(stuff_query)
        document_prompt = PromptTemplate.from_template("{page_content}")
        stuff_chain = (
                {
                    "content": lambda docs: "\n\n".join(
                        format_document(doc, document_prompt) for doc in docs
                    )
                }
                | template
                | llm
                | StrOutputParser()
        )
        return stuff_chain.invoke(documents)

    # 灵活构建前提信息进行stuff链提问
    @staticmethod
    def invoke_stuff_chain_get_str_with_str(demand_str, info_str, llm):
        """基于STR构造invoke stuffchain GETSTR。

        参数:
            `demand_str`：调用方传入的现有参数。
            `info_str`：调用方传入的现有参数。
            `llm`：调用方传入的现有参数。

        副作用:
            可能按现有预算与模型选择发起 provider 或 embedding 调用。

        不变量:
            模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
        doc_str = " \n\n{content}"
        stuff_query = demand_str + doc_str
        template = PromptTemplate.from_template(stuff_query)
        stuff_chain = template | llm | StrOutputParser()
        return stuff_chain.invoke({"content": info_str})

    # 用于更个性化的定制一个stuff链
    @staticmethod
    def stuff_chain(template,llm):
        """处理stuff chain，并保持 `BasicChain` 的现有状态约束。"""
        stuff_chain = template | llm | StrOutputParser()
        return stuff_chain

    @staticmethod
    def invoke_map_reduce_chain_get_str(part_summary_str, total_summary_str, documents, llm, max_syn):
        """调用映射reduce chainGET STR，并遵循现有调用契约。

        参数:
            `part_summary_str`：调用方传入的现有参数。
            `total_summary_str`：调用方传入的现有参数。
            `documents`：调用方传入的现有参数。
            `llm`：调用方传入的现有参数。
            `max_syn`：调用方传入的现有参数。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按现有预算与模型选择发起 provider 或 embedding 调用。

        不变量:
            模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
        document_prompt = PromptTemplate.from_template("{page_content}")
        # partial 固定format_document的一个参数
        partial_format_document = partial(format_document, prompt=document_prompt)

        doc_str = " \n\n{content}"
        part_summary_template = PromptTemplate.from_template(part_summary_str + doc_str)
        total_summary_template = PromptTemplate.from_template(total_summary_str + doc_str)

        map_chain = (
                {"content": partial_format_document}
                | part_summary_template
                | llm
                | StrOutputParser()
        )

        reduce_chain = (
                {"content": lambda strs: "\n\n".join(strs)}
                | total_summary_template
                | llm
                | StrOutputParser()
        )

        summaries = map_chain.map().invoke(
            documents,
            config={"max_concurrency": max_syn},
        )
        for _ in range(LEGACY_REDUCE_MAX_LEVELS):
            combined = "\n\n".join(summaries)
            if documentTools.num_tokens_from_string(combined) <= LEGACY_REDUCE_CONTEXT_TOKENS:
                return reduce_chain.invoke(summaries)
            batches = _partition_summaries_within_budget(
                summaries,
                max_tokens=LEGACY_REDUCE_CONTEXT_TOKENS,
            )
            summaries = reduce_chain.batch(
                batches,
                config={"max_concurrency": max_syn},
            )
        raise ValueError("map-reduce summaries did not converge within the reduce budget")

    @staticmethod
    def invoke_refine_chain_get_str(first_summary_str, previous_summary_str, final_summary_str, documents, llm):
        """调用refine chainGET STR，并遵循现有调用契约。

        参数:
            `first_summary_str`：调用方传入的现有参数。
            `previous_summary_str`：调用方传入的现有参数。
            `final_summary_str`：调用方传入的现有参数。
            `documents`：调用方传入的现有参数。
            `llm`：调用方传入的现有参数。

        异常:
            `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

        副作用:
            可能按现有预算与模型选择发起 provider 或 embedding 调用。

        不变量:
            模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
        document_prompt = PromptTemplate.from_template("{page_content}")
        partial_format_document = partial(format_document, prompt=document_prompt)

        doc_str = " \n\n{content}"
        prev_str = " \n\n{prev_response}\n\n"

        first_prompt = PromptTemplate.from_template(first_summary_str + doc_str)
        context_chain = {"content": partial_format_document} | first_prompt | llm | StrOutputParser()

        refine_prompt = PromptTemplate.from_template(
            previous_summary_str + prev_str + final_summary_str + doc_str
        )

        refine_chain = (
                {
                    "prev_response": itemgetter("prev_response"),
                    "content": lambda x: partial_format_document(x["doc"]),
                }
                | refine_prompt
                | llm
                | StrOutputParser()
        )

        def refine_loop(docs):
            """处理refine LOOP，并保持 `BasicChain` 的现有状态约束。

            参数:
                `docs`：调用方传入的现有参数。

            异常:
                `ValueError`：输入、状态或下游结果不满足现有约束时抛出。

            副作用:
                可能按现有预算与模型选择发起 provider 或 embedding 调用。

            不变量:
                模型选择、Token 上限、取消与失败不覆盖有效结果的语义必须保持不变。"""
            if not docs:
                raise ValueError("Refine chain requires at least one document")
            summary = context_chain.invoke(docs[0])
            for i, doc in enumerate(docs[1:]):
                summary = refine_chain.invoke({"prev_response": summary, "doc": doc})
            return summary

        return refine_loop(documents)

    @staticmethod
    def json_chain(json_class, llm):
        """处理JSON chain，并保持 `BasicChain` 的现有状态约束。

        参数:
            `json_class`：调用方传入的现有参数。
            `llm`：调用方传入的现有参数。

        异常:
            `LLMOutputParsingError`：输入、状态或下游结果不满足现有约束时抛出。"""
        instructions_parser = JsonOutputParser(pydantic_object=json_class)
        prompt = PromptTemplate(
            template="请回答下面的问题: \n{query}\n\n{format_instructions}\n如果输出的是代码块，请不要包含首尾的```符号",
            input_variables=["query"],
            partial_variables={
                "format_instructions": instructions_parser.get_format_instructions()
            },
        )

        def parse_json_output(raw_output: str):
            """解析JSON输出，并遵循现有调用契约。

            参数:
                `raw_output`：沿用签名中 `str` 类型约束的输入。

            异常:
                `LLMOutputParsingError`：输入、状态或下游结果不满足现有约束时抛出。"""
            text = raw_output.strip()
            if text.startswith("```") and text.endswith("```"):
                text = text[3:-3].strip()
                if text.lower().startswith("json"):
                    text = text[4:].lstrip()
            try:
                parsed = json.loads(text)
                validated = json_class.model_validate(parsed)
            except Exception as exc:
                raise LLMOutputParsingError(
                    "The model returned invalid structured output"
                ) from exc
            return validated.model_dump()

        return prompt | llm | StrOutputParser() | RunnableLambda(parse_json_output)
