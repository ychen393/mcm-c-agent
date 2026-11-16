def test_settings_create_runtime_directories(test_settings):
    assert test_settings.upload_dir.exists()
    assert test_settings.output_dir.exists()


def test_settings_provider_defaults(test_settings):
    assert test_settings.llm_provider == "deepseek"
    assert test_settings.llm_model == "test-model"


def test_settings_accepts_app_password_and_projects_dir(tmp_path):
    from pydantic import SecretStr

    from core.config import Settings

    projects = tmp_path / "projects"
    settings = Settings(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        upload_dir=tmp_path / "uploads",
        output_dir=tmp_path / "outputs",
        projects_dir=projects,
        app_password=SecretStr("from-env-only"),
    )
    assert projects.is_dir()
    assert settings.app_password.get_secret_value() == "from-env-only"

