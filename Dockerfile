FROM python:3.12-alpine
LABEL authors="Lorem Ipsum"

RUN pip install --no-cache-dir uv --root-user-action=ignore

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]