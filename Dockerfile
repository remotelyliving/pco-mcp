FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source (changes more often)
COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

# Re-install in case src changed entry points
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000

CMD ["uvicorn", "pco_mcp.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
