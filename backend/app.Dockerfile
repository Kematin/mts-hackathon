FROM python:3.12-slim
ARG API_PORT
ENV API_PORT=$API_PORT

WORKDIR /app

RUN pip install uv --no-cache-dir

COPY pyproject.toml .
COPY uv.lock .

RUN uv sync --frozen

COPY app/ ./app/
EXPOSE $API_PORT
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port $API_PORT
