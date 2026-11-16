"""Corpus registry + ingest + embedding retrieval (CI-safe hash provider)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.literature_evidence import gather_literature_evidence
from agents.problem_analyst import analyze_problem
from tools.corpus_ingest import chunk_text, ingest_registry
from tools.corpus_registry import (
    DEFAULT_REGISTRY_PATH,
    copyright_gate_errors,
    load_corpus_registry,
)
from tools.corpus_vector_store import InMemoryVectorStore
from tools.embeddings import HashEmbeddingProvider, cosine_similarity
from tools.literature_corpus import (
    retrieve_similar_chunks,
    search_with_embeddings_fallback,
)
from tools.problem_spec_2022_c import load_2022_c_fixture

REPO = Path(__file__).resolve().parents[2]


def test_corpus_registry_loads_fixture_rows():
    rows = load_corpus_registry(DEFAULT_REGISTRY_PATH)
    assert len(rows) >= 6
    ids = {row.source_id for row in rows}
    assert "fx_txn_cost_portfolio" in ids
    assert "fx_paper_structure" in ids
    assert "fx_sensitivity_methods" in ids
    for row in rows:
        assert row.acquisition_method == "fixture"
        assert not copyright_gate_errors(row)
        assert row.local_path
        assert (REPO / row.local_path).is_file()


def test_hash_embeddings_are_deterministic_and_normalized():
    provider = HashEmbeddingProvider(dim=64)
    a = provider.embed(["transaction costs gold bitcoin"])[0]
    b = provider.embed(["transaction costs gold bitcoin"])[0]
    assert a == b
    assert abs(sum(x * x for x in a) - 1.0) < 1e-6
    other = provider.embed(["unrelated gardening tips"])[0]
    assert cosine_similarity(a, b) > cosine_similarity(a, other)


def test_chunk_text_overlaps():
    text = "word " * 200
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) >= 2
    assert all(chunk for chunk in chunks)


def test_ingest_then_retrieve_relevant_chunk():
    store = InMemoryVectorStore()
    report = ingest_registry(
        registry_path=DEFAULT_REGISTRY_PATH,
        store=store,
        embedder=HashEmbeddingProvider(dim=384),
        clear=True,
    )
    assert report.sources_ingested >= 6
    assert report.chunks_upserted >= 6
    assert store.count() == report.chunks_upserted

    hits = retrieve_similar_chunks(
        "transaction costs rebalancing gold bitcoin portfolio alpha",
        limit=5,
        store=store,
        min_score=0.01,
    )
    assert hits
    source_ids = {hit.chunk.source_id for hit in hits}
    assert "fx_txn_cost_portfolio" in source_ids or "fx_multiobjective_portfolio" in source_ids

    sens = retrieve_similar_chunks(
        "sensitivity analysis sweep alpha gold bitcoin robustness",
        limit=5,
        store=store,
        min_score=0.01,
    )
    assert sens
    assert any(hit.chunk.source_id == "fx_sensitivity_methods" for hit in sens[:3])


def test_search_fallback_uses_embeddings_when_index_ready():
    store = InMemoryVectorStore()
    ingest_registry(
        store=store,
        embedder=HashEmbeddingProvider(dim=384),
        clear=True,
    )
    sources, backend = search_with_embeddings_fallback(
        query_text="excellent paper structure summary sheet validation sensitivity",
        limit=4,
        store=store,
    )
    assert backend == "fixture_embeddings"
    assert sources
    assert sources[0]["source_id"]
    assert sources[0]["_retrieval"]["score"] >= 0.0


def test_search_fallback_to_keyword_when_store_empty():
    store = InMemoryVectorStore()
    sources, backend = search_with_embeddings_fallback(
        query_text="transaction costs gold bitcoin portfolio",
        research_question_ids=["rq_daily_strategy"],
        limit=3,
        store=store,
    )
    assert backend == "fixture_corpus"
    assert sources
    assert sources[0]["source_id"] in {
        "fx_txn_cost_portfolio",
        "fx_past_price_only",
        "fx_calendar_assets",
        "fx_multiobjective_portfolio",
        "fx_sensitivity_methods",
        "fx_paper_structure",
    }


def test_literature_agent_uses_embedding_backend_when_ingested():
    store = InMemoryVectorStore()
    ingest_registry(
        store=store,
        embedder=HashEmbeddingProvider(dim=384),
        clear=True,
    )
    spec = analyze_problem(load_2022_c_fixture(), use_llm=False)
    report = gather_literature_evidence(
        problem_specification=spec,
        use_live=False,
        vector_store=store,
        limit=6,
    )
    assert report.invented_sources is False
    assert report.retrieval_backend == "fixture_embeddings"
    assert report.strategy == "hybrid"
    assert report.cards
    for card in report.cards:
        assert card.invented is False
        assert card.source.source_id
        assert card.snippets


def test_copyright_gate_blocks_unapproved_owner_provided(tmp_path: Path):
    csv_path = tmp_path / "registry.csv"
    text_path = tmp_path / "private.txt"
    text_path.write_text("owner excerpt about gold trading.", encoding="utf-8")
    csv_path.write_text(
        "source_id,title,author_or_org,year,original_url,acquired_at,publisher,"
        "license_or_rights_statement,terms_url,acquisition_method,allowed_operations,"
        "full_text_storage_allowed,excerpt_allowed,redistribution_allowed,"
        "external_llm_upload_allowed,review_status,reviewer,reviewed_at,notes,local_path\n"
        "own_demo,Owner demo,Owner,2022,,,,"
        "all rights reserved,,owner_provided,excerpt_quote,yes,yes,no,no,"
        "pending,,,demo,"
        f"{text_path.as_posix()}\n",
        encoding="utf-8",
    )
    store = InMemoryVectorStore()
    report = ingest_registry(
        registry_path=csv_path,
        store=store,
        embedder=HashEmbeddingProvider(dim=64),
        clear=True,
        repo_root=tmp_path,
    )
    assert report.sources_ingested == 0
    assert any("approved" in item for item in report.skipped)
