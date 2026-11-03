from core.config import Settings
from llm.base import BaseLLM
from llm.providers.anthropic import AnthropicLLM
from llm.providers.openai_compatible import OpenAICompatibleLLM
class LLMFactory:
    @staticmethod
    def create(settings: Settings) -> BaseLLM:
        if settings.llm_provider in {'openai', 'deepseek'}: return OpenAICompatibleLLM(provider=settings.llm_provider, model=settings.llm_model, api_key=settings.provider_api_key(), base_url=settings.llm_base_url)
        if settings.llm_provider == 'anthropic': return AnthropicLLM(model=settings.llm_model, api_key=settings.provider_api_key())
        raise ValueError(f'Unsupported LLM provider: {settings.llm_provider}')
