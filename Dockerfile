# MCM C Research Lab — Railway / container image (no secrets baked in).
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app \
    PORT=8501 \
    APP_ENV=production \
    PROJECT_STORE_BACKEND=postgres \
    PROBLEM_ANALYST_USE_LLM=false \
    LITERATURE_LIVE_RETRIEVAL=false \
    RESEARCH_STRATEGY_USE_LLM=false \
    VALIDATION_USE_LLM=false \
    PAPER_USE_LLM=false \
    UPLOAD_DIR=/data/uploads \
    OUTPUT_DIR=/data/outputs \
    PROJECTS_DIR=/data/projects

WORKDIR /app

# Minimal build tooling for any wheel that needs a compiler; TeX is intentionally omitted
# (PDF compile remains optional / soft-fail).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY core ./core
COPY llm ./llm
COPY agents ./agents
COPY schemas ./schemas
COPY database ./database
COPY tools ./tools
COPY modeling ./modeling
COPY validation ./validation
COPY app ./app
COPY paper ./paper
COPY e2e ./e2e
COPY locales ./locales
COPY knowledge ./knowledge
COPY scripts ./scripts
COPY data/problem_fixtures ./data/problem_fixtures
COPY data/uploads/.gitkeep ./data/uploads/.gitkeep
COPY data/projects/.gitkeep ./data/projects/.gitkeep
COPY outputs/.gitkeep ./outputs/.gitkeep

RUN pip install --upgrade pip \
    && pip install -e .

# Runtime volume mount points (Railway Volume → /data recommended).
RUN mkdir -p /data/uploads /data/outputs /data/projects \
    && chmod -R 777 /data

EXPOSE 8501

# Railway injects PORT. Bind all interfaces; headless for container logs.
CMD ["sh", "-c", "streamlit run app/main.py --server.port=${PORT:-8501} --server.address=0.0.0.0 --server.headless=true --browser.gatherUsageStats=false"]
