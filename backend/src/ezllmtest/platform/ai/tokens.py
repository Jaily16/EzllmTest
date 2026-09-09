"""统一的离线 Token 计数规则，保持原 tokenizer 和结果。"""
import tiktoken
def num_tokens_from_string(text_str: str) -> int:
    # 获取指定编码的编码器
    """按固定 gpt-3.5-turbo tokenizer 离线估算 token，保持历史预算计数口径。"""
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    # encoding = tiktoken.get_encoding(encoding_name)
    # 将文本字符串编码为指定编码，并计算编码后的标记数量
    num_tokens = len(encoding.encode(text_str))
    # 返回标记数量
    return num_tokens
