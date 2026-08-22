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
    """Group every summary in order without silently truncating reduce input."""

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
        doc_str = " \n\n{content}"
        stuff_query = demand_str + doc_str
        template = PromptTemplate.from_template(stuff_query)
        stuff_chain = template | llm | StrOutputParser()
        return stuff_chain.invoke({"content": info_str})

    # 用于更个性化的定制一个stuff链
    @staticmethod
    def stuff_chain(template,llm):
        stuff_chain = template | llm | StrOutputParser()
        return stuff_chain

    @staticmethod
    def invoke_map_reduce_chain_get_str(part_summary_str, total_summary_str, documents, llm, max_syn):
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
            if not docs:
                raise ValueError("Refine chain requires at least one document")
            summary = context_chain.invoke(docs[0])
            for i, doc in enumerate(docs[1:]):
                summary = refine_chain.invoke({"prev_response": summary, "doc": doc})
            return summary

        return refine_loop(documents)

    @staticmethod
    def json_chain(json_class, llm):
        instructions_parser = JsonOutputParser(pydantic_object=json_class)
        prompt = PromptTemplate(
            template="请回答下面的问题: \n{query}\n\n{format_instructions}\n如果输出的是代码块，请不要包含首尾的```符号",
            input_variables=["query"],
            partial_variables={
                "format_instructions": instructions_parser.get_format_instructions()
            },
        )

        def parse_json_output(raw_output: str):
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
