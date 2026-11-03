from pydantic import SecretStr
from llm.base import BaseLLM, LLMResponse
class AnthropicLLM(BaseLLM):
    def __init__(self, model: str, api_key: SecretStr | None): self.provider, self.model, self.api_key = 'anthropic', model, api_key
    def invoke(self, messages: list[dict[str, str]]) -> LLMResponse:
        if not self.api_key or not self.api_key.get_secret_value().strip(): raise RuntimeError("Missing API key for provider 'anthropic'. Set ANTHROPIC_API_KEY in .env.")
        try: from langchain_anthropic import ChatAnthropic
        except ImportError as exc: raise RuntimeError("Install optional dependency: pip install -e '.[anthropic]'") from exc
        result = ChatAnthropic(model=self.model, api_key=self.api_key.get_secret_value()).invoke(messages)
        return LLMResponse(content=str(result.content), provider=self.provider, model=self.model, usage=getattr(result, 'usage_metadata', None))
