FROM python:3.11.8-alpine3.19

# Install uv
RUN --mount=type=cache,target=/root/.cache/pip pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml /pyproject.toml
COPY uv.lock /uv.lock

# Install dependencies before copying source code
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

# Create UV cache directory with proper permissions for non-root users
RUN mkdir -p /.cache/uv && chmod 777 /.cache/uv

# Copy application code and scripts
COPY app/ /app/
COPY run.sh /run.sh

EXPOSE 8000

ENTRYPOINT [ "/run.sh" ]
