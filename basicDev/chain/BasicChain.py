from langchain_core.prompts import PromptTemplate, format_document
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from functools import partial
from operator import itemgetter


# 用BasicChain类统一整合stuff、mapreduce和refine链
class BasicChain:
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

    @staticmethod
    def invoke_stuff_chain_get_str_with_str(demand_str, str, llm):
        doc_str = " \n\n{content}"
        stuff_query = demand_str + doc_str
        template = PromptTemplate.from_template(stuff_query)
        stuff_chain = template | llm | StrOutputParser()
        return stuff_chain.invoke({"content": str})

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

        map_reduce = map_chain.map() | reduce_chain
        return map_reduce.invoke(documents, config={"max_concurrency": max_syn})

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
            summary = context_chain.invoke(docs[0])
            for i, doc in enumerate(docs[1:]):
                summary = refine_chain.invoke({"prev_response": summary, "doc": doc})
            return summary

        return refine_loop(documents)

    @staticmethod
    def json_chain(json_class, llm):
        parser = JsonOutputParser(pydantic_object=json_class)
        prompt = PromptTemplate(
            template="请回答下面的问题: \n{query}\n\n{format_instructions}\n如果输出的是代码块，请不要包含首尾的```符号",
            input_variables=["query"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )
        chain = prompt | llm | parser
        return chain
