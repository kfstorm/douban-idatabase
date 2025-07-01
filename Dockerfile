FROM python:3.11.8-alpine3.19

# Install uv
RUN pip install uv

# Copy dependency files first for better caching
COPY pyproject.toml /pyproject.toml
COPY uv.lock /uv.lock

# Install dependencies before copying source code
RUN uv sync --frozen

# Copy application code and scripts
COPY app/ /app/
COPY run.sh /run.sh

EXPOSE 8000

ENTRYPOINT [ "/run.sh" ]
