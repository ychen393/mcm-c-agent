from pydantic import SecretStr
from llm.base import BaseLLM, LLMResponse
class OpenAICompatibleLLM(BaseLLM):
    def __init__(self, provider: str, model: str, api_key: SecretStr | None, base_url: str | None = None): self.provider, self.model, self.api_key, self.base_url = provider, model, api_key, base_url
    def invoke(self, messages: list[dict[str, str]]) -> LLMResponse:
        if not self.api_key or not self.api_key.get_secret_value().strip(): raise RuntimeError(f"Missing API key for provider '{self.provider}'. Set the matching key in .env.")
        try: from langchain_openai import ChatOpenAI
        except ImportError as exc: raise RuntimeError('Install the project dependencies first.') from exc
        result = ChatOpenAI(model=self.model, api_key=self.api_key.get_secret_value(), base_url=self.base_url).invoke(messages)
        return LLMResponse(content=str(result.content), provider=self.provider, model=self.model, usage=getattr(result, 'usage_metadata', None))
