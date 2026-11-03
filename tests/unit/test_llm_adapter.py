import pytest
from pydantic import SecretStr
from llm.providers.openai_compatible import OpenAICompatibleLLM
def test_llm_adapter_fails_clearly_without_api_key():
    adapter = OpenAICompatibleLLM(provider='deepseek', model='test-model', api_key=None, base_url='https://api.deepseek.com')
    with pytest.raises(RuntimeError, match='Missing API key'): adapter.invoke([{'role':'user','content':'hello'}])
def test_llm_adapter_accepts_configured_key():
    adapter = OpenAICompatibleLLM(provider='deepseek', model='test-model', api_key=SecretStr('test-key'), base_url='https://api.deepseek.com')
    assert adapter.provider == 'deepseek'
