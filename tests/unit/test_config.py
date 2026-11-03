def test_settings_create_runtime_directories(test_settings):
    assert test_settings.upload_dir.exists()
    assert test_settings.output_dir.exists()
def test_settings_provider_defaults(test_settings):
    assert test_settings.llm_provider == 'deepseek'
    assert test_settings.llm_model == 'test-model'
