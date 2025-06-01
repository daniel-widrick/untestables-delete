# Stage 1: Build environment
FROM python:3.11-slim-bookworm AS builder

RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /home/app

# Copy only requirements to cache them in docker layer
COPY --chown=app:app pyproject.toml poetry.lock* ./

# Add pipx binaries to PATH
ENV PATH="/root/.local/bin:/home/app/.local/bin:${PATH}"

# Install pipx
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libffi-dev curl && \
    python -m pip install --upgrade pip && \
    python -m pip install pipx && \
    pipx ensurepath

# Install Poetry
RUN pipx install poetry && \
    poetry config virtualenvs.create true && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-interaction --no-ansi --no-root

# Copying the rest of the project
COPY --chown=app:app . .

ENV PATH="/home/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/home/app/.venv/lib/python3.11/site-packages/"

ENV DATABASE_URL="sqlite:///:memory:"
ENV GITHUB_TOKEN="dummy_token"
ENV ABS_MIN_STARS=10
ENV ABS_MAX_STARS=1000000
ENV DEFAULT_CHUNK_SIZE=100

ENTRYPOINT ["poetry", "run", "tests"]
CMD [""]