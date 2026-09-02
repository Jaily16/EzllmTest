from infrastructure.llm.gateway import get_chat_model


def choose_llm_by_name(name: str, minimum_timeout_seconds: float = 0.0):
    return get_chat_model(name, minimum_timeout_seconds)
