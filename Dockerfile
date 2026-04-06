FROM python:3.12-slim

WORKDIR /app

# Copy source first so setuptools can find the src/ directory
COPY pyproject.toml .
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

RUN pip install --no-cache-dir .

RUN useradd -r -s /bin/false app
USER app

EXPOSE 8000

CMD ["uvicorn", "pco_mcp.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
