# Reproducible environment for the SMC/ICT statistical edge study.
#
#   docker build -t smc-ict-research .
#   docker run --rm -v "$PWD/results:/app/results" smc-ict-research            # fast validation
#   docker run --rm -v "$PWD/results:/app/results" smc-ict-research full       # full run (hours)
#   docker run --rm smc-ict-research test                                      # test suite only
#
# The image ships the committed 50-ticker sample, so the fast path and the
# tests run with no network access. The full run downloads the S&P 500 from
# Yahoo Finance and therefore does need network.

FROM python:3.12-slim-bookworm

# Pinned so an image rebuild cannot silently change results through a
# transitive dependency bump.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONHASHSEED=0 \
    MPLBACKEND=Agg

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-ci.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-ci.txt

COPY . .

RUN chmod +x run_full_pipeline.sh run_fast_validation.sh 2>/dev/null || true

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["fast"]
