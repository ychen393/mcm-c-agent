import pytest
from core.config import Settings
@pytest.fixture
def test_settings(tmp_path):
    return Settings(app_env='test', llm_provider='deepseek', llm_model='test-model', llm_base_url='https://api.deepseek.com', upload_dir=tmp_path/'uploads', output_dir=tmp_path/'outputs')
