"""Persistence path / backend config regression for Railway Volume prep."""

from __future__ import annotations

from pathlib import Path

from pydantic import SecretStr

from core.config import Settings
from database.repositories import build_project_store


def test_configurable_dirs_created(tmp_path):
    upload = tmp_path / "vol" / "uploads"
    output = tmp_path / "vol" / "outputs"
    projects = tmp_path / "vol" / "projects"
    settings = Settings(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        upload_dir=upload,
        output_dir=output,
        projects_dir=projects,
        project_store_backend="local",
    )
    assert upload.is_dir()
    assert output.is_dir()
    assert projects.is_dir()
    assert settings.resolved_projects_dir() == projects.resolve() or settings.resolved_projects_dir() == projects


def test_resolved_projects_dir_defaults_beside_uploads(tmp_path):
    upload = tmp_path / "data" / "uploads"
    output = tmp_path / "outputs"
    settings = Settings(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        upload_dir=upload,
        output_dir=output,
        projects_dir=None,
        project_store_backend="local",
    )
    root = settings.resolved_projects_dir()
    assert root == (upload.resolve().parent / "projects")


def test_build_project_store_honors_projects_dir(tmp_path):
    upload = tmp_path / "uploads"
    output = tmp_path / "outputs"
    projects = tmp_path / "custom-projects"
    settings = Settings(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        upload_dir=upload,
        output_dir=output,
        projects_dir=projects,
        project_store_backend="local",
        app_password=SecretStr("unused"),
    )
    store = build_project_store(settings)
    assert Path(store.root).resolve() == projects.resolve()


def test_llm_flags_default_off_for_demo(tmp_path):
    settings = Settings(
        app_env="test",
        llm_provider="deepseek",
        llm_model="test-model",
        upload_dir=tmp_path / "u",
        output_dir=tmp_path / "o",
    )
    assert settings.problem_analyst_use_llm is False
    assert settings.literature_live_retrieval is False
    assert settings.research_strategy_use_llm is False
    assert settings.validation_use_llm is False
    assert settings.paper_use_llm is False
