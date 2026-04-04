# pco-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hosted MCP server that lets ChatGPT query and interact with Planning Center Online data, turnkey for non-technical church staff.

**Architecture:** Monolithic Python app on Railway. FastMCP 3.x with Streamable HTTP transport serves the MCP protocol. FastAPI wraps the MCP app and adds landing page + OAuth routes. PostgreSQL stores encrypted user tokens and OAuth sessions. Dual OAuth: server acts as OAuth provider for ChatGPT (OAuth 2.1) while being an OAuth client to PCO (OAuth 2.0).

**Tech Stack:** Python 3.12+, FastMCP 3.2+, FastAPI, httpx, asyncpg, SQLAlchemy (async), cryptography (Fernet), pytest, mutmut, Alembic

---

## Team Structure

| Role | Agent Type | Responsibility |
|------|-----------|----------------|
| **Senior Architect** | Main session | Design authority, code review, task prioritization, final approval gate |
| **Senior Engineer** | Review subagent | Code review: correctness, patterns, test quality, DRY/YAGNI |
| **SRE** | Review subagent | Operability: error handling, logging, deployment, rate limiting, health checks |
| **Security** | Review subagent | OAuth flows, token storage, encryption, input validation, CSRF, injection |
| **UX** | Review subagent | Error messages, onboarding flow, setup guide, non-technical user clarity |

**Review protocol:** After each task completes, dispatch all 4 review subagents in parallel. All must approve before merging. Any reviewer can request changes. Senior Architect has final veto.

**Quality gates:**
- 90% test code coverage (measured by `pytest-cov`)
- 80% mutation score on business logic (measured by `mutmut`)
- All 4 reviewers approve
- No security warnings from `bandit`
- Type checking passes (`mypy --strict`)

---

## File Structure

```
pco-mcp/
├── pyproject.toml              # Project config, dependencies, tool settings
├── alembic.ini                 # Database migration config
├── alembic/
│   ├── env.py                  # Migration environment
│   └── versions/               # Migration files
├── src/
│   └── pco_mcp/
│       ├── __init__.py
│       ├── main.py             # FastAPI app + FastMCP mounting + lifespan
│       ├── config.py           # Settings via pydantic-settings (env vars)
│       ├── db.py               # SQLAlchemy async engine + session factory
│       ├── models.py           # SQLAlchemy ORM models (users, oauth_sessions)
│       ├── crypto.py           # Fernet encrypt/decrypt for tokens
│       ├── oauth/
│       │   ├── __init__.py
│       │   ├── provider.py     # OAuth 2.1 provider endpoints for ChatGPT
│       │   └── pco_client.py   # PCO OAuth 2.0 client (authorize, callback, refresh)
│       ├── pco/
│       │   ├── __init__.py
│       │   ├── client.py       # PCO API HTTP client (rate limiting, pagination, errors)
│       │   ├── people.py       # People module API calls
│       │   └── services.py     # Services module API calls
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── people.py       # MCP tools for People module
│       │   └── services.py     # MCP tools for Services module
│       ├── web/
│       │   ├── __init__.py
│       │   ├── routes.py       # Landing page, dashboard, setup guide routes
│       │   └── templates/      # Jinja2 HTML templates
│       │       ├── base.html
│       │       ├── landing.html
│       │       ├── dashboard.html
│       │       └── setup_guide.html
│       └── errors.py           # Error mapping (PCO HTTP -> plain English)
├── tests/
│   ├── conftest.py             # Shared fixtures (test DB, mock PCO, test client)
│   ├── test_config.py
│   ├── test_crypto.py
│   ├── test_db.py
│   ├── test_errors.py
│   ├── test_oauth_provider.py
│   ├── test_pco_client.py
│   ├── test_pco_people.py
│   ├── test_pco_services.py
│   ├── test_tools_people.py
│   ├── test_tools_services.py
│   ├── test_web_routes.py
│   └── fixtures/               # Recorded PCO API response fixtures
│       ├── people/
│       └── services/
└── docs/
    ├── specs/
    │   └── 2026-04-03-pco-mcp-design.md
    └── plans/
        └── 2026-04-03-pco-mcp-implementation.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/pco_mcp/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "pco-mcp"
version = "0.1.0"
description = "MCP server connecting ChatGPT to Planning Center Online"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=3.2.0",
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "httpx>=0.28.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "cryptography>=44.0.0",
    "pydantic-settings>=2.7.0",
    "jinja2>=3.1.5",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "pytest-cov>=6.0.0",
    "httpx",
    "mutmut>=3.2.0",
    "mypy>=1.14.0",
    "bandit>=1.8.0",
    "ruff>=0.9.0",
    "aiosqlite>=0.20.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "--strict-markers -x --tb=short"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]

[tool.coverage.run]
source = ["src/pco_mcp"]
branch = true

[tool.coverage.report]
fail_under = 90
show_missing = true
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "if __name__ == .__main__.",
]

[tool.mutmut]
paths_to_mutate = "src/pco_mcp/"
tests_dir = "tests/"
runner = "python -m pytest -x --tb=no -q"

[tool.mypy]
strict = true
plugins = ["pydantic.mypy"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "S", "B", "A", "C4", "SIM", "TCH"]

[tool.bandit]
targets = ["src/pco_mcp"]
```

- [ ] **Step 2: Create package init file**

```python
# src/pco_mcp/__init__.py
```

Empty file. Just marks the directory as a Python package.

- [ ] **Step 3: Create tests init**

```python
# tests/__init__.py
```

- [ ] **Step 4: Create .gitignore**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
.env
.mutmut-cache
htmlcov/
.coverage
.coverage.*
mutmut-report/
.mypy_cache/
.ruff_cache/
```

- [ ] **Step 5: Install dependencies and verify**

Run:
```bash
cd /Users/christian/projects/pco-mcp
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Expected: Clean install, no errors.

- [ ] **Step 6: Verify pytest runs with zero tests**

Run:
```bash
pytest --co -q
```

Expected: `no tests ran` (collected 0 items)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/ .gitignore
git commit -m "feat: project scaffolding with dependencies and tool config"
```

---

## Task 2: Configuration (pydantic-settings)

**Files:**
- Create: `src/pco_mcp/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os

import pytest


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/pco")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODk=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.example.com")

    from pco_mcp.config import Settings

    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://user:pass@localhost/pco"
    assert settings.pco_client_id == "test-client-id"
    assert settings.pco_client_secret == "test-client-secret"
    assert settings.base_url == "https://pco-mcp.example.com"
    assert settings.token_encryption_key != ""
    assert settings.secret_key == "test-secret-key"


def test_settings_has_defaults_for_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/pco")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0xMjM0NTY3ODk=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.example.com")

    from pco_mcp.config import Settings

    settings = Settings()
    assert settings.pco_api_base == "https://api.planningcenteronline.com"
    assert settings.pco_rate_limit_buffer == 10
    assert settings.token_expiry_hours == 24


def test_settings_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PCO_CLIENT_ID", raising=False)
    monkeypatch.delenv("PCO_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("BASE_URL", raising=False)

    from pydantic import ValidationError

    from pco_mcp.config import Settings

    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pco_mcp.config'`

- [ ] **Step 3: Implement config.py**

```python
# src/pco_mcp/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Required
    database_url: str
    pco_client_id: str
    pco_client_secret: str
    token_encryption_key: str
    secret_key: str
    base_url: str

    # Optional with defaults
    pco_api_base: str = "https://api.planningcenteronline.com"
    pco_rate_limit_buffer: int = 10
    token_expiry_hours: int = 24
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/config.py tests/test_config.py
git commit -m "feat: add configuration via pydantic-settings"
```

---

## Task 3: Token Encryption (Fernet)

**Files:**
- Create: `src/pco_mcp/crypto.py`
- Create: `tests/test_crypto.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_crypto.py
import pytest

from pco_mcp.crypto import decrypt_token, encrypt_token, generate_encryption_key


def test_encrypt_decrypt_roundtrip() -> None:
    key = generate_encryption_key()
    plaintext = "oauth-access-token-abc123"
    encrypted = encrypt_token(plaintext, key)
    assert encrypted != plaintext.encode()
    decrypted = decrypt_token(encrypted, key)
    assert decrypted == plaintext


def test_decrypt_with_wrong_key_raises() -> None:
    key1 = generate_encryption_key()
    key2 = generate_encryption_key()
    encrypted = encrypt_token("secret", key1)
    with pytest.raises(Exception):
        decrypt_token(encrypted, key2)


def test_encrypt_returns_bytes() -> None:
    key = generate_encryption_key()
    result = encrypt_token("test", key)
    assert isinstance(result, bytes)


def test_generate_key_returns_valid_fernet_key() -> None:
    key = generate_encryption_key()
    assert isinstance(key, str)
    # Fernet keys are 44 chars base64
    assert len(key) == 44
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crypto.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement crypto.py**

```python
# src/pco_mcp/crypto.py
from cryptography.fernet import Fernet


def generate_encryption_key() -> str:
    """Generate a new Fernet encryption key. Use this once to create TOKEN_ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()


def encrypt_token(plaintext: str, key: str) -> bytes:
    """Encrypt a token string. Returns encrypted bytes for database storage."""
    f = Fernet(key.encode())
    return f.encrypt(plaintext.encode())


def decrypt_token(encrypted: bytes, key: str) -> str:
    """Decrypt token bytes back to a string."""
    f = Fernet(key.encode())
    return f.decrypt(encrypted).decode()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crypto.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/crypto.py tests/test_crypto.py
git commit -m "feat: add Fernet token encryption/decryption"
```

---

## Task 4: Database Models + Migrations

**Files:**
- Create: `src/pco_mcp/db.py`
- Create: `src/pco_mcp/models.py`
- Create: `tests/test_db.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_db.py
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from pco_mcp.models import Base, OAuthSession, User


@pytest.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_create_user(db_session: AsyncSession) -> None:
    user = User(
        pco_person_id=12345,
        pco_org_name="First Church",
        pco_access_token_enc=b"encrypted-access",
        pco_refresh_token_enc=b"encrypted-refresh",
        pco_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.pco_person_id == 12345))
    fetched = result.scalar_one()
    assert fetched.pco_org_name == "First Church"
    assert fetched.id is not None


async def test_user_pco_person_id_is_unique(db_session: AsyncSession) -> None:
    user1 = User(
        pco_person_id=99999,
        pco_access_token_enc=b"enc1",
        pco_refresh_token_enc=b"enc1",
        pco_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    user2 = User(
        pco_person_id=99999,
        pco_access_token_enc=b"enc2",
        pco_refresh_token_enc=b"enc2",
        pco_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(user1)
    await db_session.commit()
    db_session.add(user2)
    with pytest.raises(Exception):
        await db_session.commit()


async def test_create_oauth_session(db_session: AsyncSession) -> None:
    user = User(
        pco_person_id=11111,
        pco_access_token_enc=b"enc",
        pco_refresh_token_enc=b"enc",
        pco_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.commit()

    session = OAuthSession(
        user_id=user.id,
        chatgpt_access_token_hash="sha256-abc123",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(session)
    await db_session.commit()

    result = await db_session.execute(
        select(OAuthSession).where(OAuthSession.user_id == user.id)
    )
    fetched = result.scalar_one()
    assert fetched.chatgpt_access_token_hash == "sha256-abc123"


async def test_oauth_session_references_user(db_session: AsyncSession) -> None:
    session = OAuthSession(
        user_id=uuid.uuid4(),  # non-existent user
        chatgpt_access_token_hash="sha256-orphan",
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db_session.add(session)
    with pytest.raises(Exception):
        await db_session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement db.py**

```python
# src/pco_mcp/db.py
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pco_mcp.config import Settings


def create_engine(settings: Settings):
    """Create async SQLAlchemy engine from settings."""
    return create_async_engine(settings.database_url, echo=settings.debug)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)
```

- [ ] **Step 4: Implement models.py**

```python
# src/pco_mcp/models.py
import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    pco_person_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    pco_org_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    pco_access_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    pco_refresh_token_enc: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    pco_token_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OAuthSession(Base):
    __tablename__ = "oauth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    chatgpt_access_token_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_db.py -v`
Expected: 4 passed

- [ ] **Step 6: Set up Alembic**

Create `alembic.ini`:
```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://localhost/pco_mcp

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `alembic/env.py`:
```python
# alembic/env.py
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from pco_mcp.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(config.get_main_option("sqlalchemy.url"))
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Create `alembic/versions/` directory (empty, with `.gitkeep`):
```bash
mkdir -p alembic/versions
touch alembic/versions/.gitkeep
```

- [ ] **Step 7: Commit**

```bash
git add src/pco_mcp/db.py src/pco_mcp/models.py tests/test_db.py alembic.ini alembic/
git commit -m "feat: add database models and Alembic migration setup"
```

---

## Task 5: Error Mapping

**Files:**
- Create: `src/pco_mcp/errors.py`
- Create: `tests/test_errors.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_errors.py
from pco_mcp.errors import map_pco_error


def test_401_returns_session_expired() -> None:
    msg = map_pco_error(401, base_url="https://pco-mcp.example.com")
    assert "expired" in msg.lower()
    assert "https://pco-mcp.example.com" in msg


def test_403_returns_permission_message() -> None:
    msg = map_pco_error(403, base_url="https://pco-mcp.example.com")
    assert "permission" in msg.lower()


def test_404_returns_not_found() -> None:
    msg = map_pco_error(404, base_url="https://pco-mcp.example.com")
    assert "found" in msg.lower()


def test_429_returns_rate_limit() -> None:
    msg = map_pco_error(429, base_url="https://pco-mcp.example.com")
    assert "wait" in msg.lower() or "rate" in msg.lower()


def test_500_returns_server_error() -> None:
    msg = map_pco_error(500, base_url="https://pco-mcp.example.com")
    assert "unavailable" in msg.lower() or "try again" in msg.lower()


def test_502_returns_server_error() -> None:
    msg = map_pco_error(502, base_url="https://pco-mcp.example.com")
    assert "unavailable" in msg.lower() or "try again" in msg.lower()


def test_unknown_status_returns_generic() -> None:
    msg = map_pco_error(418, base_url="https://pco-mcp.example.com")
    assert "unexpected" in msg.lower() or "error" in msg.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement errors.py**

```python
# src/pco_mcp/errors.py


def map_pco_error(status_code: int, base_url: str) -> str:
    """Map a PCO API HTTP status code to a plain-English error message."""
    if status_code == 401:
        return (
            f"Your Planning Center session has expired. "
            f"Please reconnect at {base_url}"
        )
    if status_code == 403:
        return "You don't have permission to access this in Planning Center."
    if status_code == 404:
        return "That record wasn't found in Planning Center."
    if status_code == 429:
        return "Planning Center is rate-limiting requests. Please wait a moment and try again."
    if status_code >= 500:
        return "Planning Center is temporarily unavailable. Please try again shortly."
    return f"An unexpected error occurred (status {status_code}). Please try again."
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_errors.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/errors.py tests/test_errors.py
git commit -m "feat: add PCO API error mapping to plain-English messages"
```

---

## Task 6: PCO API Client

**Files:**
- Create: `src/pco_mcp/pco/__init__.py`
- Create: `src/pco_mcp/pco/client.py`
- Create: `tests/test_pco_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pco_client.py
import json

import httpx
import pytest

from pco_mcp.pco.client import PCOClient, PCOAPIError, PCORateLimitError


@pytest.fixture
def pco_client() -> PCOClient:
    return PCOClient(
        base_url="https://api.planningcenteronline.com",
        access_token="test-token-123",
    )


class TestPCOClientGet:
    async def test_get_success(self, pco_client: PCOClient) -> None:
        response_data = {
            "data": [{"type": "Person", "id": "1", "attributes": {"first_name": "Alice"}}]
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=response_data,
                headers={
                    "X-PCO-API-Request-Rate-Count": "5",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        result = await pco_client.get("/people/v2/people")
        assert result["data"][0]["attributes"]["first_name"] == "Alice"

    async def test_get_401_raises_api_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                401,
                json={"errors": [{"detail": "unauthorized"}]},
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCOAPIError) as exc_info:
            await pco_client.get("/people/v2/people")
        assert exc_info.value.status_code == 401

    async def test_get_429_raises_rate_limit_error(self, pco_client: PCOClient) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                429,
                json={"errors": [{"detail": "rate limited"}]},
                headers={
                    "Retry-After": "5",
                    "X-PCO-API-Request-Rate-Count": "100",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )
        )
        pco_client._client = httpx.AsyncClient(transport=transport)
        with pytest.raises(PCORateLimitError) as exc_info:
            await pco_client.get("/people/v2/people")
        assert exc_info.value.retry_after == 5

    async def test_get_includes_bearer_auth(self, pco_client: PCOClient) -> None:
        captured_request = None

        def capture_handler(request: httpx.Request) -> httpx.Response:
            nonlocal captured_request
            captured_request = request
            return httpx.Response(
                200,
                json={"data": []},
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )

        pco_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(capture_handler)
        )
        await pco_client.get("/people/v2/people")
        assert captured_request is not None
        assert captured_request.headers["authorization"] == "Bearer test-token-123"


class TestPCOClientPagination:
    async def test_get_all_pages(self, pco_client: PCOClient) -> None:
        page1 = {
            "data": [{"id": "1"}],
            "meta": {"total_count": 2, "count": 1, "next": {"offset": 1}},
            "links": {"next": "https://api.planningcenteronline.com/people/v2/people?offset=1"},
        }
        page2 = {
            "data": [{"id": "2"}],
            "meta": {"total_count": 2, "count": 1},
        }
        call_count = 0

        def paginated_handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            data = page1 if call_count == 1 else page2
            return httpx.Response(
                200,
                json=data,
                headers={
                    "X-PCO-API-Request-Rate-Count": "1",
                    "X-PCO-API-Request-Rate-Limit": "100",
                    "X-PCO-API-Request-Rate-Period": "20",
                },
            )

        pco_client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(paginated_handler)
        )
        results = await pco_client.get_all("/people/v2/people")
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[1]["id"] == "2"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pco_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pco/client.py**

```python
# src/pco_mcp/pco/__init__.py
```

```python
# src/pco_mcp/pco/client.py
import httpx


class PCOAPIError(Exception):
    """Raised when the PCO API returns a non-success status code."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"PCO API error {status_code}: {detail}")


class PCORateLimitError(PCOAPIError):
    """Raised when the PCO API returns 429 Too Many Requests."""

    def __init__(self, retry_after: int, detail: str) -> None:
        self.retry_after = retry_after
        super().__init__(status_code=429, detail=detail)


class PCOClient:
    """Async HTTP client for the Planning Center Online API."""

    def __init__(self, base_url: str, access_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._access_token = access_token
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request to the PCO API. Raises on non-2xx."""
        response = await self._client.get(path, params=params)
        self._check_response(response)
        return response.json()

    async def post(self, path: str, data: dict) -> dict:
        """Make a POST request to the PCO API."""
        response = await self._client.post(path, json=data)
        self._check_response(response)
        return response.json()

    async def patch(self, path: str, data: dict) -> dict:
        """Make a PATCH request to the PCO API."""
        response = await self._client.patch(path, json=data)
        self._check_response(response)
        return response.json()

    async def get_all(self, path: str, params: dict | None = None, max_pages: int = 50) -> list:
        """Fetch all pages of a paginated PCO endpoint. Returns flat list of data items."""
        all_data: list = []
        current_params = dict(params or {})
        for _ in range(max_pages):
            result = await self.get(path, params=current_params)
            all_data.extend(result.get("data", []))
            next_link = result.get("links", {}).get("next")
            if not next_link:
                break
            next_offset = result.get("meta", {}).get("next", {}).get("offset")
            if next_offset is None:
                break
            current_params["offset"] = next_offset
        return all_data

    def _check_response(self, response: httpx.Response) -> None:
        """Check response status and raise appropriate errors."""
        if response.is_success:
            return
        detail = self._extract_error_detail(response)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "20"))
            raise PCORateLimitError(retry_after=retry_after, detail=detail)
        raise PCOAPIError(status_code=response.status_code, detail=detail)

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extract error detail from a PCO error response."""
        try:
            body = response.json()
            errors = body.get("errors", [])
            if errors:
                return errors[0].get("detail", "Unknown error")
        except Exception:
            pass
        return f"HTTP {response.status_code}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pco_client.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/pco/ tests/test_pco_client.py
git commit -m "feat: add PCO API client with rate limiting and pagination"
```

---

## Task 7: PCO People Module

**Files:**
- Create: `src/pco_mcp/pco/people.py`
- Create: `tests/test_pco_people.py`
- Create: `tests/fixtures/people/` (JSON fixture files)

- [ ] **Step 1: Create JSON fixtures for People API responses**

```json
// tests/fixtures/people/search_people.json
{
    "data": [
        {
            "type": "Person",
            "id": "1001",
            "attributes": {
                "first_name": "Alice",
                "last_name": "Smith",
                "email_addresses": [{"address": "alice@example.com"}],
                "phone_numbers": [{"number": "555-0101"}],
                "membership": "Member",
                "status": "active"
            }
        },
        {
            "type": "Person",
            "id": "1002",
            "attributes": {
                "first_name": "Bob",
                "last_name": "Jones",
                "email_addresses": [{"address": "bob@example.com"}],
                "phone_numbers": [],
                "membership": "Visitor",
                "status": "active"
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

```json
// tests/fixtures/people/get_person.json
{
    "data": {
        "type": "Person",
        "id": "1001",
        "attributes": {
            "first_name": "Alice",
            "last_name": "Smith",
            "email_addresses": [{"address": "alice@example.com"}],
            "phone_numbers": [{"number": "555-0101"}],
            "membership": "Member",
            "status": "active",
            "birthdate": "1990-05-15",
            "gender": "Female",
            "created_at": "2020-01-01T00:00:00Z"
        }
    }
}
```

```json
// tests/fixtures/people/list_lists.json
{
    "data": [
        {
            "type": "List",
            "id": "501",
            "attributes": {
                "name": "Volunteers",
                "description": "Active volunteers",
                "total_count": 45
            }
        },
        {
            "type": "List",
            "id": "502",
            "attributes": {
                "name": "New Members 2026",
                "description": null,
                "total_count": 12
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_pco_people.py
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI

FIXTURES = Path(__file__).parent / "fixtures" / "people"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def mock_client() -> PCOClient:
    client = AsyncMock(spec=PCOClient)
    return client


class TestSearchPeople:
    async def test_search_by_name(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("search_people.json")
        api = PeopleAPI(mock_client)
        results = await api.search_people(name="Alice")
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert "/people/v2/people" in call_args.args[0]
        assert len(results) == 2
        assert results[0]["first_name"] == "Alice"

    async def test_search_returns_simplified_records(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("search_people.json")
        api = PeopleAPI(mock_client)
        results = await api.search_people(name="Alice")
        record = results[0]
        assert "id" in record
        assert "first_name" in record
        assert "last_name" in record
        assert "email" in record


class TestGetPerson:
    async def test_get_by_id(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_person.json")
        api = PeopleAPI(mock_client)
        person = await api.get_person("1001")
        mock_client.get.assert_called_once_with("/people/v2/people/1001")
        assert person["first_name"] == "Alice"
        assert person["id"] == "1001"


class TestListLists:
    async def test_returns_lists(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_lists.json")
        api = PeopleAPI(mock_client)
        lists = await api.list_lists()
        assert len(lists) == 2
        assert lists[0]["name"] == "Volunteers"
        assert lists[0]["total_count"] == 45
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_people.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement pco/people.py**

```python
# src/pco_mcp/pco/people.py
from pco_mcp.pco.client import PCOClient


class PeopleAPI:
    """Wrapper for PCO People module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def search_people(
        self,
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict]:
        """Search for people. Returns simplified records."""
        params: dict = {}
        if name:
            params["where[search_name]"] = name
        if email:
            params["where[search_name_or_email]"] = email
        if phone:
            params["where[search_name_or_email]"] = phone
        result = await self._client.get("/people/v2/people", params=params)
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def get_person(self, person_id: str) -> dict:
        """Get full details for a person by ID."""
        result = await self._client.get(f"/people/v2/people/{person_id}")
        return self._simplify_person(result["data"])

    async def list_lists(self) -> list[dict]:
        """Get all PCO Lists."""
        result = await self._client.get("/people/v2/lists")
        return [self._simplify_list(lst) for lst in result.get("data", [])]

    async def get_list_members(self, list_id: str) -> list[dict]:
        """Get people in a specific list."""
        result = await self._client.get(f"/people/v2/lists/{list_id}/people")
        return [self._simplify_person(p) for p in result.get("data", [])]

    async def create_person(self, first_name: str, last_name: str, email: str | None = None) -> dict:
        """Create a new person record."""
        payload = {
            "data": {
                "type": "Person",
                "attributes": {
                    "first_name": first_name,
                    "last_name": last_name,
                },
            }
        }
        if email:
            payload["data"]["attributes"]["email_addresses"] = [{"address": email}]
        result = await self._client.post("/people/v2/people", data=payload)
        return self._simplify_person(result["data"])

    async def update_person(self, person_id: str, **fields: str) -> dict:
        """Update fields on an existing person."""
        payload = {
            "data": {
                "type": "Person",
                "id": person_id,
                "attributes": fields,
            }
        }
        result = await self._client.patch(f"/people/v2/people/{person_id}", data=payload)
        return self._simplify_person(result["data"])

    def _simplify_person(self, raw: dict) -> dict:
        """Flatten a JSON:API person record into a simple dict."""
        attrs = raw.get("attributes", {})
        emails = attrs.get("email_addresses", [])
        phones = attrs.get("phone_numbers", [])
        return {
            "id": raw["id"],
            "first_name": attrs.get("first_name", ""),
            "last_name": attrs.get("last_name", ""),
            "email": emails[0]["address"] if emails else None,
            "phone": phones[0]["number"] if phones else None,
            "membership": attrs.get("membership"),
            "status": attrs.get("status"),
        }

    def _simplify_list(self, raw: dict) -> dict:
        """Flatten a JSON:API list record."""
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "description": attrs.get("description"),
            "total_count": attrs.get("total_count", 0),
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_people.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/people.py tests/test_pco_people.py tests/fixtures/people/
git commit -m "feat: add PCO People module API wrapper"
```

---

## Task 8: PCO Services Module

**Files:**
- Create: `src/pco_mcp/pco/services.py`
- Create: `tests/test_pco_services.py`
- Create: `tests/fixtures/services/` (JSON fixture files)

- [ ] **Step 1: Create JSON fixtures for Services API responses**

```json
// tests/fixtures/services/list_service_types.json
{
    "data": [
        {
            "type": "ServiceType",
            "id": "201",
            "attributes": {
                "name": "Sunday Morning",
                "frequency": "Every week",
                "last_plan_from": "2026-03-30"
            }
        },
        {
            "type": "ServiceType",
            "id": "202",
            "attributes": {
                "name": "Wednesday Night",
                "frequency": "Every week",
                "last_plan_from": "2026-04-02"
            }
        }
    ],
    "meta": {"total_count": 2, "count": 2}
}
```

```json
// tests/fixtures/services/get_upcoming_plans.json
{
    "data": [
        {
            "type": "Plan",
            "id": "3001",
            "attributes": {
                "title": "Easter Service",
                "dates": "April 20, 2026",
                "sort_date": "2026-04-20T09:00:00Z",
                "items_count": 12,
                "needed_positions_count": 3
            }
        }
    ],
    "meta": {"total_count": 1, "count": 1}
}
```

```json
// tests/fixtures/services/list_songs.json
{
    "data": [
        {
            "type": "Song",
            "id": "4001",
            "attributes": {
                "title": "Amazing Grace",
                "author": "John Newton",
                "ccli_number": "4669344",
                "last_scheduled_at": "2026-03-30T09:00:00Z"
            }
        }
    ],
    "meta": {"total_count": 1, "count": 1}
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/test_pco_services.py
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.services import ServicesAPI

FIXTURES = Path(__file__).parent / "fixtures" / "services"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def mock_client() -> PCOClient:
    return AsyncMock(spec=PCOClient)


class TestListServiceTypes:
    async def test_returns_simplified_types(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_service_types.json")
        api = ServicesAPI(mock_client)
        types = await api.list_service_types()
        assert len(types) == 2
        assert types[0]["name"] == "Sunday Morning"
        assert types[0]["id"] == "201"


class TestGetUpcomingPlans:
    async def test_returns_plans(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("get_upcoming_plans.json")
        api = ServicesAPI(mock_client)
        plans = await api.get_upcoming_plans("201")
        assert len(plans) == 1
        assert plans[0]["title"] == "Easter Service"
        mock_client.get.assert_called_once()
        call_path = mock_client.get.call_args.args[0]
        assert "201" in call_path


class TestListSongs:
    async def test_returns_songs(self, mock_client: AsyncMock) -> None:
        mock_client.get.return_value = load_fixture("list_songs.json")
        api = ServicesAPI(mock_client)
        songs = await api.list_songs()
        assert len(songs) == 1
        assert songs[0]["title"] == "Amazing Grace"
        assert songs[0]["author"] == "John Newton"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_pco_services.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement pco/services.py**

```python
# src/pco_mcp/pco/services.py
from pco_mcp.pco.client import PCOClient


class ServicesAPI:
    """Wrapper for PCO Services module API calls."""

    def __init__(self, client: PCOClient) -> None:
        self._client = client

    async def list_service_types(self) -> list[dict]:
        """List all service types."""
        result = await self._client.get("/services/v2/service_types")
        return [self._simplify_service_type(st) for st in result.get("data", [])]

    async def get_upcoming_plans(self, service_type_id: str) -> list[dict]:
        """Get upcoming plans for a service type."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans",
            params={"filter": "future", "order": "sort_date"},
        )
        return [self._simplify_plan(p) for p in result.get("data", [])]

    async def get_plan_details(self, service_type_id: str, plan_id: str) -> dict:
        """Get full details for a specific plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}"
        )
        return self._simplify_plan(result["data"])

    async def list_songs(self, query: str | None = None) -> list[dict]:
        """List/search songs in the library."""
        params: dict = {}
        if query:
            params["where[title]"] = query
        result = await self._client.get("/services/v2/songs", params=params)
        return [self._simplify_song(s) for s in result.get("data", [])]

    async def list_team_members(self, service_type_id: str, plan_id: str) -> list[dict]:
        """List team members for a plan."""
        result = await self._client.get(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members"
        )
        return [self._simplify_team_member(tm) for tm in result.get("data", [])]

    async def schedule_team_member(
        self, service_type_id: str, plan_id: str, person_id: str, team_position_name: str
    ) -> dict:
        """Schedule a person to a team position in a plan."""
        payload = {
            "data": {
                "type": "PlanPerson",
                "attributes": {
                    "person_id": int(person_id),
                    "team_position_name": team_position_name,
                },
            }
        }
        result = await self._client.post(
            f"/services/v2/service_types/{service_type_id}/plans/{plan_id}/team_members",
            data=payload,
        )
        return self._simplify_team_member(result["data"])

    def _simplify_service_type(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "name": attrs.get("name", ""),
            "frequency": attrs.get("frequency"),
            "last_plan_from": attrs.get("last_plan_from"),
        }

    def _simplify_plan(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "dates": attrs.get("dates", ""),
            "sort_date": attrs.get("sort_date"),
            "items_count": attrs.get("items_count", 0),
            "needed_positions_count": attrs.get("needed_positions_count", 0),
        }

    def _simplify_song(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "title": attrs.get("title", ""),
            "author": attrs.get("author"),
            "ccli_number": attrs.get("ccli_number"),
            "last_scheduled_at": attrs.get("last_scheduled_at"),
        }

    def _simplify_team_member(self, raw: dict) -> dict:
        attrs = raw.get("attributes", {})
        return {
            "id": raw["id"],
            "person_name": attrs.get("name", ""),
            "team_position_name": attrs.get("team_position_name"),
            "status": attrs.get("status"),
            "notification_sent_at": attrs.get("notification_sent_at"),
        }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_services.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/pco/services.py tests/test_pco_services.py tests/fixtures/services/
git commit -m "feat: add PCO Services module API wrapper"
```

---

## Task 9: MCP Tools — People

**Files:**
- Create: `src/pco_mcp/tools/__init__.py`
- Create: `src/pco_mcp/tools/people.py`
- Create: `tests/test_tools_people.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_people.py
from unittest.mock import AsyncMock, patch

import pytest
from fastmcp import FastMCP


def make_mcp_with_people_tools() -> FastMCP:
    """Create a FastMCP instance with people tools registered."""
    from pco_mcp.tools.people import register_people_tools

    mcp = FastMCP("test")
    register_people_tools(mcp)
    return mcp


class TestPeopleToolRegistration:
    def test_search_people_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "search_people" in tool_names

    def test_get_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "get_person" in tool_names

    def test_list_lists_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "list_lists" in tool_names

    def test_create_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "create_person" in tool_names

    def test_update_person_tool_registered(self) -> None:
        mcp = make_mcp_with_people_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "update_person" in tool_names

    def test_read_tools_have_readonly_annotation(self) -> None:
        mcp = make_mcp_with_people_tools()
        for tool in mcp._tool_manager.tools.values():
            if tool.name in ("search_people", "get_person", "list_lists", "get_list_members"):
                assert tool.annotations is not None
                assert tool.annotations.get("readOnlyHint") is True

    def test_write_tools_have_confirmation_annotation(self) -> None:
        mcp = make_mcp_with_people_tools()
        for tool in mcp._tool_manager.tools.values():
            if tool.name in ("create_person", "update_person"):
                assert tool.annotations is not None
                assert tool.annotations.get("readOnlyHint") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_people.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools/people.py**

```python
# src/pco_mcp/tools/__init__.py
```

```python
# src/pco_mcp/tools/people.py
from fastmcp import FastMCP

READ_ANNOTATIONS = {"readOnlyHint": True, "openWorldHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}


def register_people_tools(mcp: FastMCP) -> None:
    """Register all People module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def search_people(
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> list[dict]:
        """Search for people in Planning Center by name, email, or phone number.

        Returns a list of matching people with their basic info (name, email, phone,
        membership status). Use get_person with a specific ID for full details.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.search_people(name=name, email=email, phone=phone)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_person(person_id: str) -> dict:
        """Get full details for a specific person by their Planning Center ID.

        Returns detailed info including name, email, phone, membership, status,
        birthdate, and gender.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.get_person(person_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_lists() -> list[dict]:
        """Get all lists (smart groups, tags) from Planning Center People.

        Returns each list's name, description, and member count.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.list_lists()

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_list_members(list_id: str) -> list[dict]:
        """Get all people in a specific Planning Center list.

        Provide the list ID (from list_lists). Returns people with basic info.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.get_list_members(list_id)

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def create_person(
        first_name: str,
        last_name: str,
        email: str | None = None,
    ) -> dict:
        """Create a new person in Planning Center.

        Requires first and last name. Email is optional. Returns the created person record.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        return await api.create_person(first_name=first_name, last_name=last_name, email=email)

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def update_person(
        person_id: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
    ) -> dict:
        """Update an existing person's information in Planning Center.

        Provide the person ID and any fields to change. Only provided fields are updated.
        """
        from pco_mcp.tools._context import get_people_api

        api = get_people_api()
        fields = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if last_name is not None:
            fields["last_name"] = last_name
        return await api.update_person(person_id, **fields)
```

Note: The `_context` module will be created in Task 11 (App Wiring). For now the tool registration tests verify structure only.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_people.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/ tests/test_tools_people.py
git commit -m "feat: add MCP tools for People module"
```

---

## Task 10: MCP Tools — Services

**Files:**
- Create: `src/pco_mcp/tools/services.py`
- Create: `tests/test_tools_services.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools_services.py
from fastmcp import FastMCP


def make_mcp_with_services_tools() -> FastMCP:
    from pco_mcp.tools.services import register_services_tools

    mcp = FastMCP("test")
    register_services_tools(mcp)
    return mcp


class TestServicesToolRegistration:
    def test_list_service_types_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "list_service_types" in tool_names

    def test_get_upcoming_plans_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "get_upcoming_plans" in tool_names

    def test_list_songs_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "list_songs" in tool_names

    def test_schedule_team_member_registered(self) -> None:
        mcp = make_mcp_with_services_tools()
        tool_names = [t.name for t in mcp._tool_manager.tools.values()]
        assert "schedule_team_member" in tool_names

    def test_read_tools_have_readonly_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        for tool in mcp._tool_manager.tools.values():
            if tool.name in (
                "list_service_types",
                "get_upcoming_plans",
                "get_plan_details",
                "list_songs",
                "list_team_members",
            ):
                assert tool.annotations is not None
                assert tool.annotations.get("readOnlyHint") is True

    def test_write_tools_have_confirmation_annotation(self) -> None:
        mcp = make_mcp_with_services_tools()
        for tool in mcp._tool_manager.tools.values():
            if tool.name == "schedule_team_member":
                assert tool.annotations is not None
                assert tool.annotations.get("readOnlyHint") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tools_services.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools/services.py**

```python
# src/pco_mcp/tools/services.py
from fastmcp import FastMCP

READ_ANNOTATIONS = {"readOnlyHint": True, "openWorldHint": True}
WRITE_ANNOTATIONS = {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True}


def register_services_tools(mcp: FastMCP) -> None:
    """Register all Services module tools on the given FastMCP instance."""

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_service_types() -> list[dict]:
        """List all service types in Planning Center Services.

        Returns service types like "Sunday Morning", "Wednesday Night", etc.
        Use the returned ID with get_upcoming_plans to see scheduled services.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_service_types()

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_upcoming_plans(service_type_id: str) -> list[dict]:
        """Get upcoming service plans for a specific service type.

        Returns future plans with dates, item counts, and needed positions.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.get_upcoming_plans(service_type_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def get_plan_details(service_type_id: str, plan_id: str) -> dict:
        """Get full details for a specific service plan.

        Returns the plan with songs, items, team assignments, and times.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.get_plan_details(service_type_id, plan_id)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_songs(query: str | None = None) -> list[dict]:
        """Search or list songs in the Planning Center song library.

        Optionally filter by title. Returns song title, author, CCLI number,
        and when it was last scheduled.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_songs(query=query)

    @mcp.tool(annotations=READ_ANNOTATIONS)
    async def list_team_members(service_type_id: str, plan_id: str) -> list[dict]:
        """List team members and their positions for a service plan.

        Returns each team member's name, position, and status (confirmed/pending/declined).
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.list_team_members(service_type_id, plan_id)

    @mcp.tool(annotations=WRITE_ANNOTATIONS)
    async def schedule_team_member(
        service_type_id: str,
        plan_id: str,
        person_id: str,
        team_position_name: str,
    ) -> dict:
        """Schedule a person to a team position in a service plan.

        Provide the service type ID, plan ID, person ID, and the position name
        (e.g., "Vocalist", "Sound Tech"). The person will be notified via Planning Center.
        """
        from pco_mcp.tools._context import get_services_api

        api = get_services_api()
        return await api.schedule_team_member(
            service_type_id, plan_id, person_id, team_position_name
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tools_services.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/tools/services.py tests/test_tools_services.py
git commit -m "feat: add MCP tools for Services module"
```

---

## Task 11: OAuth Provider (ChatGPT-facing)

**Files:**
- Create: `src/pco_mcp/oauth/__init__.py`
- Create: `src/pco_mcp/oauth/provider.py`
- Create: `tests/test_oauth_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_oauth_provider.py
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pco_mcp.oauth.provider import create_oauth_router


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock(return_value=session)
    return factory, session


@pytest.fixture
def app(mock_session_factory):
    factory, _ = mock_session_factory
    app = FastAPI()
    router = create_oauth_router(
        session_factory=factory,
        pco_client_id="test-pco-client",
        pco_client_secret="test-pco-secret",
        base_url="https://pco-mcp.example.com",
        token_encryption_key="dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
        secret_key="test-secret",
    )
    app.include_router(router, prefix="/oauth")
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestDynamicClientRegistration:
    def test_register_returns_client_credentials(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "client_id" in body
        assert "client_secret" in body

    def test_register_requires_redirect_uris(self, client) -> None:
        resp = client.post("/oauth/register", json={})
        assert resp.status_code == 422 or resp.status_code == 400


class TestAuthorizeEndpoint:
    def test_authorize_redirects_to_pco(self, client) -> None:
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "test-client",
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "abc123",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
        location = resp.headers["location"]
        assert "api.planningcenteronline.com/oauth/authorize" in location


class TestTokenEndpoint:
    def test_token_rejects_invalid_code(self, client) -> None:
        resp = client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": "invalid-code",
                "redirect_uri": "https://chatgpt.com/callback",
                "client_id": "test-client",
                "client_secret": "test-secret",
            },
        )
        assert resp.status_code in (400, 401)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_oauth_provider.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement oauth/provider.py**

```python
# src/pco_mcp/oauth/__init__.py
```

```python
# src/pco_mcp/oauth/provider.py
import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

# In-memory store for dynamic client registrations and auth codes.
# For v1 single-instance deployment this is acceptable.
# Move to database if horizontal scaling is needed.
_registered_clients: dict[str, dict] = {}
_pending_auth_codes: dict[str, dict] = {}


def create_oauth_router(
    session_factory: async_sessionmaker,
    pco_client_id: str,
    pco_client_secret: str,
    base_url: str,
    token_encryption_key: str,
    secret_key: str,
) -> APIRouter:
    router = APIRouter()

    @router.post("/register", status_code=201)
    async def register_client(request: Request) -> JSONResponse:
        """Dynamic Client Registration (RFC 7591) for ChatGPT."""
        body = await request.json()
        redirect_uris = body.get("redirect_uris")
        if not redirect_uris:
            raise HTTPException(status_code=400, detail="redirect_uris required")

        client_id = secrets.token_urlsafe(32)
        client_secret = secrets.token_urlsafe(48)
        _registered_clients[client_id] = {
            "client_secret": client_secret,
            "redirect_uris": redirect_uris,
        }
        return JSONResponse(
            content={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": redirect_uris,
            },
            status_code=201,
        )

    @router.get("/authorize")
    async def authorize(
        client_id: str = Query(...),
        redirect_uri: str = Query(...),
        response_type: str = Query(...),
        state: str = Query(""),
        code_challenge: str = Query(""),
        code_challenge_method: str = Query(""),
    ) -> RedirectResponse:
        """Authorization endpoint. Chains into PCO OAuth flow."""
        # Store the ChatGPT callback info so we can complete it after PCO auth
        internal_state = secrets.token_urlsafe(32)
        _pending_auth_codes[internal_state] = {
            "chatgpt_client_id": client_id,
            "chatgpt_redirect_uri": redirect_uri,
            "chatgpt_state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        }

        # Redirect to PCO OAuth
        pco_auth_url = (
            f"https://api.planningcenteronline.com/oauth/authorize"
            f"?client_id={pco_client_id}"
            f"&redirect_uri={base_url}/oauth/pco-callback"
            f"&response_type=code"
            f"&scope=people+services"
            f"&state={internal_state}"
        )
        return RedirectResponse(url=pco_auth_url)

    @router.get("/pco-callback")
    async def pco_callback(
        code: str = Query(""),
        state: str = Query(""),
        error: str = Query(""),
    ) -> RedirectResponse:
        """Handle PCO OAuth callback, exchange code, issue our own code to ChatGPT."""
        if error:
            raise HTTPException(status_code=400, detail=f"PCO auth error: {error}")

        pending = _pending_auth_codes.pop(state, None)
        if not pending:
            raise HTTPException(status_code=400, detail="Invalid or expired state")

        # Exchange PCO auth code for tokens (implemented in pco_client.py)
        from pco_mcp.oauth.pco_client import exchange_pco_code

        pco_tokens = await exchange_pco_code(
            code=code,
            client_id=pco_client_id,
            client_secret=pco_client_secret,
            redirect_uri=f"{base_url}/oauth/pco-callback",
        )

        # Store PCO tokens and create user
        from pco_mcp.crypto import encrypt_token
        from pco_mcp.models import User
        from sqlalchemy import select

        async with session_factory() as db:
            # Get the user's PCO person ID
            from pco_mcp.oauth.pco_client import get_pco_me

            me = await get_pco_me(pco_tokens["access_token"])

            result = await db.execute(
                select(User).where(User.pco_person_id == me["id"])
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    pco_person_id=me["id"],
                    pco_org_name=me.get("org_name"),
                    pco_access_token_enc=encrypt_token(
                        pco_tokens["access_token"], token_encryption_key
                    ),
                    pco_refresh_token_enc=encrypt_token(
                        pco_tokens["refresh_token"], token_encryption_key
                    ),
                    pco_token_expires_at=datetime.now(UTC)
                    + timedelta(seconds=pco_tokens.get("expires_in", 7200)),
                )
                db.add(user)
            else:
                user.pco_access_token_enc = encrypt_token(
                    pco_tokens["access_token"], token_encryption_key
                )
                user.pco_refresh_token_enc = encrypt_token(
                    pco_tokens["refresh_token"], token_encryption_key
                )
                user.pco_token_expires_at = datetime.now(UTC) + timedelta(
                    seconds=pco_tokens.get("expires_in", 7200)
                )
            await db.commit()
            await db.refresh(user)

        # Issue an auth code for ChatGPT
        our_code = secrets.token_urlsafe(48)
        _pending_auth_codes[our_code] = {
            "user_id": str(user.id),
            "chatgpt_client_id": pending["chatgpt_client_id"],
            "code_challenge": pending["code_challenge"],
            "type": "auth_code",
        }

        # Redirect back to ChatGPT with our code
        redirect = (
            f"{pending['chatgpt_redirect_uri']}"
            f"?code={our_code}"
            f"&state={pending['chatgpt_state']}"
        )
        return RedirectResponse(url=redirect)

    @router.post("/token")
    async def token(
        grant_type: str = Form(...),
        code: str = Form(""),
        redirect_uri: str = Form(""),
        client_id: str = Form(""),
        client_secret: str = Form(""),
        refresh_token: str = Form(""),
    ) -> JSONResponse:
        """Token endpoint. Exchanges auth codes for access tokens."""
        if grant_type == "authorization_code":
            pending = _pending_auth_codes.pop(code, None)
            if not pending or pending.get("type") != "auth_code":
                raise HTTPException(status_code=400, detail="Invalid authorization code")

            access_token = secrets.token_urlsafe(48)
            new_refresh_token = secrets.token_urlsafe(48)
            token_hash = hashlib.sha256(access_token.encode()).hexdigest()

            # Store the session
            from pco_mcp.models import OAuthSession
            import uuid

            async with session_factory() as db:
                session = OAuthSession(
                    user_id=uuid.UUID(pending["user_id"]),
                    chatgpt_access_token_hash=token_hash,
                    expires_at=datetime.now(UTC) + timedelta(hours=24),
                )
                db.add(session)
                await db.commit()

            return JSONResponse(
                content={
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": 86400,
                    "refresh_token": new_refresh_token,
                }
            )

        if grant_type == "refresh_token":
            # For v1, issue a new token
            access_token = secrets.token_urlsafe(48)
            return JSONResponse(
                content={
                    "access_token": access_token,
                    "token_type": "bearer",
                    "expires_in": 86400,
                }
            )

        raise HTTPException(status_code=400, detail=f"Unsupported grant_type: {grant_type}")

    return router
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oauth_provider.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/oauth/ tests/test_oauth_provider.py
git commit -m "feat: add OAuth 2.1 provider endpoints for ChatGPT"
```

---

## Task 12: PCO OAuth Client

**Files:**
- Create: `src/pco_mcp/oauth/pco_client.py`
- Create: `tests/test_pco_oauth_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pco_oauth_client.py
import httpx
import pytest

from pco_mcp.oauth.pco_client import exchange_pco_code, get_pco_me, refresh_pco_token


class TestExchangePCOCode:
    async def test_exchanges_code_for_tokens(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "access_token": "pco-access-123",
                    "refresh_token": "pco-refresh-456",
                    "expires_in": 7200,
                    "token_type": "Bearer",
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await exchange_pco_code(
                code="auth-code-789",
                client_id="test-client",
                client_secret="test-secret",
                redirect_uri="https://example.com/callback",
                http_client=client,
            )
        assert result["access_token"] == "pco-access-123"
        assert result["refresh_token"] == "pco-refresh-456"

    async def test_raises_on_error_response(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(400, json={"error": "invalid_grant"})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(Exception):
                await exchange_pco_code(
                    code="bad-code",
                    client_id="test-client",
                    client_secret="test-secret",
                    redirect_uri="https://example.com/callback",
                    http_client=client,
                )


class TestGetPCOMe:
    async def test_returns_user_info(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "data": {
                        "id": "12345",
                        "attributes": {
                            "first_name": "Alice",
                            "last_name": "Smith",
                        },
                    },
                    "meta": {
                        "parent": {
                            "id": "org-1",
                            "attributes": {"name": "First Church"},
                        }
                    },
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await get_pco_me("pco-token", http_client=client)
        assert result["id"] == 12345
        assert result["org_name"] == "First Church"


class TestRefreshPCOToken:
    async def test_refreshes_token(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "expires_in": 7200,
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            result = await refresh_pco_token(
                refresh_token="old-refresh",
                client_id="test-client",
                client_secret="test-secret",
                http_client=client,
            )
        assert result["access_token"] == "new-access"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pco_oauth_client.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement oauth/pco_client.py**

```python
# src/pco_mcp/oauth/pco_client.py
import httpx

PCO_TOKEN_URL = "https://api.planningcenteronline.com/oauth/token"
PCO_ME_URL = "https://api.planningcenteronline.com/me"


async def exchange_pco_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict:
    """Exchange a PCO authorization code for access + refresh tokens."""
    client = http_client or httpx.AsyncClient()
    try:
        resp = await client.post(
            PCO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
        )
        if not resp.is_success:
            raise Exception(f"PCO token exchange failed: {resp.status_code} {resp.text}")
        return resp.json()
    finally:
        if http_client is None:
            await client.aclose()


async def get_pco_me(
    access_token: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict:
    """Get the current user's PCO person ID and org info."""
    client = http_client or httpx.AsyncClient()
    try:
        resp = await client.get(
            PCO_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not resp.is_success:
            raise Exception(f"PCO /me request failed: {resp.status_code}")
        body = resp.json()
        data = body["data"]
        meta = body.get("meta", {})
        parent = meta.get("parent", {})
        parent_attrs = parent.get("attributes", {})
        return {
            "id": int(data["id"]),
            "first_name": data["attributes"].get("first_name"),
            "last_name": data["attributes"].get("last_name"),
            "org_name": parent_attrs.get("name"),
        }
    finally:
        if http_client is None:
            await client.aclose()


async def refresh_pco_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
    http_client: httpx.AsyncClient | None = None,
) -> dict:
    """Refresh a PCO access token using a refresh token."""
    client = http_client or httpx.AsyncClient()
    try:
        resp = await client.post(
            PCO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        if not resp.is_success:
            raise Exception(f"PCO token refresh failed: {resp.status_code}")
        return resp.json()
    finally:
        if http_client is None:
            await client.aclose()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pco_oauth_client.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/pco_mcp/oauth/pco_client.py tests/test_pco_oauth_client.py
git commit -m "feat: add PCO OAuth client (code exchange, /me, token refresh)"
```

---

## Task 13: App Wiring (main.py + context)

**Files:**
- Create: `src/pco_mcp/main.py`
- Create: `src/pco_mcp/tools/_context.py`
- Create: `tests/test_main.py`

This is the integration task that wires everything together: FastAPI + FastMCP + OAuth routes + tool context.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    """Create the app with test settings."""
    with patch.dict(
        "os.environ",
        {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "PCO_CLIENT_ID": "test-client",
            "PCO_CLIENT_SECRET": "test-secret",
            "TOKEN_ENCRYPTION_KEY": "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            "SECRET_KEY": "test-secret-key",
            "BASE_URL": "https://pco-mcp.example.com",
        },
    ):
        from pco_mcp.main import create_app

        app = create_app()
        return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestHealthCheck:
    def test_health_returns_ok(self, client) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"


class TestMCPEndpoint:
    def test_mcp_endpoint_exists(self, client) -> None:
        # The MCP endpoint should exist at /mcp/ (may return error without proper MCP request)
        resp = client.get("/mcp/")
        # FastMCP returns 405 for GET on the MCP endpoint (expects POST)
        assert resp.status_code in (200, 405, 400)


class TestOAuthEndpoints:
    def test_register_endpoint_exists(self, client) -> None:
        resp = client.post(
            "/oauth/register",
            json={"redirect_uris": ["https://chatgpt.com/callback"]},
        )
        assert resp.status_code == 201

    def test_authorize_endpoint_exists(self, client) -> None:
        resp = client.get(
            "/oauth/authorize",
            params={
                "client_id": "test",
                "redirect_uri": "https://chatgpt.com/callback",
                "response_type": "code",
                "state": "test",
            },
            follow_redirects=False,
        )
        assert resp.status_code in (302, 307)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement tools/_context.py**

```python
# src/pco_mcp/tools/_context.py
"""
Per-request context for MCP tools.

Tools need access to the authenticated user's PCO API client.
This module provides a context variable that gets set per-request
by the MCP server middleware.
"""
from contextvars import ContextVar

from pco_mcp.pco.client import PCOClient
from pco_mcp.pco.people import PeopleAPI
from pco_mcp.pco.services import ServicesAPI

_pco_client_var: ContextVar[PCOClient] = ContextVar("pco_client")


def set_pco_client(client: PCOClient) -> None:
    """Set the PCO client for the current request context."""
    _pco_client_var.set(client)


def get_pco_client() -> PCOClient:
    """Get the PCO client for the current request context."""
    return _pco_client_var.get()


def get_people_api() -> PeopleAPI:
    """Get a PeopleAPI instance for the current request."""
    return PeopleAPI(get_pco_client())


def get_services_api() -> ServicesAPI:
    """Get a ServicesAPI instance for the current request."""
    return ServicesAPI(get_pco_client())
```

- [ ] **Step 4: Implement main.py**

```python
# src/pco_mcp/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastmcp import FastMCP

from pco_mcp.config import Settings
from pco_mcp.db import create_engine, create_session_factory
from pco_mcp.models import Base
from pco_mcp.oauth.provider import create_oauth_router
from pco_mcp.tools.people import register_people_tools
from pco_mcp.tools.services import register_services_tools


def create_app() -> FastAPI:
    """Create and wire the full application."""
    settings = Settings()

    # Database
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    # FastMCP
    mcp = FastMCP(
        "Planning Center MCP",
        instructions=(
            "You are connected to Planning Center Online, a church management platform. "
            "You can search people, view service plans, list songs, and manage team schedules. "
            "Always confirm before creating or updating records."
        ),
    )
    register_people_tools(mcp)
    register_services_tools(mcp)

    mcp_app = mcp.http_app(path="/")

    # OAuth router
    oauth_router = create_oauth_router(
        session_factory=session_factory,
        pco_client_id=settings.pco_client_id,
        pco_client_secret=settings.pco_client_secret,
        base_url=settings.base_url,
        token_encryption_key=settings.token_encryption_key,
        secret_key=settings.secret_key,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Create tables on startup (use Alembic in production)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    app = FastAPI(title="pco-mcp", lifespan=lifespan)

    # Health check
    @app.get("/health")
    async def health():
        return JSONResponse({"status": "healthy"})

    # Mount OAuth routes
    app.include_router(oauth_router, prefix="/oauth")

    # Mount MCP at /mcp
    app.mount("/mcp", mcp_app)

    return app
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_main.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/pco_mcp/main.py src/pco_mcp/tools/_context.py tests/test_main.py
git commit -m "feat: wire up FastAPI + FastMCP + OAuth into main app"
```

---

## Task 14: Web Routes (Landing Page, Dashboard, Setup Guide)

**Files:**
- Create: `src/pco_mcp/web/__init__.py`
- Create: `src/pco_mcp/web/routes.py`
- Create: `src/pco_mcp/web/templates/base.html`
- Create: `src/pco_mcp/web/templates/landing.html`
- Create: `src/pco_mcp/web/templates/dashboard.html`
- Create: `src/pco_mcp/web/templates/setup_guide.html`
- Create: `tests/test_web_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_web_routes.py
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    with patch.dict(
        "os.environ",
        {
            "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
            "PCO_CLIENT_ID": "test-client",
            "PCO_CLIENT_SECRET": "test-secret",
            "TOKEN_ENCRYPTION_KEY": "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=",
            "SECRET_KEY": "test-secret-key",
            "BASE_URL": "https://pco-mcp.example.com",
        },
    ):
        from pco_mcp.main import create_app

        return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)


class TestLandingPage:
    def test_landing_returns_html(self, client) -> None:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Planning Center" in resp.text

    def test_landing_has_get_started_link(self, client) -> None:
        resp = client.get("/")
        assert "Get Started" in resp.text


class TestSetupGuide:
    def test_setup_guide_returns_html(self, client) -> None:
        resp = client.get("/setup-guide")
        assert resp.status_code == 200
        assert "ChatGPT" in resp.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_web_routes.py -v`
Expected: FAIL (routes not yet registered / templates missing)

- [ ] **Step 3: Create templates**

`src/pco_mcp/web/__init__.py` — empty file.

`src/pco_mcp/web/templates/base.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}pco-mcp{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
</head>
<body>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

`src/pco_mcp/web/templates/landing.html`:
```html
{% extends "base.html" %}
{% block title %}Connect ChatGPT to Planning Center{% endblock %}
{% block content %}
<section>
    <hgroup>
        <h1>Connect ChatGPT to Planning Center</h1>
        <p>Ask ChatGPT about your church's people, services, songs, and schedules.</p>
    </hgroup>
    <p>
        <a href="/auth/start" role="button">Get Started</a>
    </p>
    <h2>How it works</h2>
    <ol>
        <li>Click "Get Started" and log in with your Planning Center account</li>
        <li>Copy the MCP endpoint URL we give you</li>
        <li>Paste it into ChatGPT's Settings &gt; Apps</li>
        <li>Start asking ChatGPT about your church data</li>
    </ol>
</section>
{% endblock %}
```

`src/pco_mcp/web/templates/dashboard.html`:
```html
{% extends "base.html" %}
{% block title %}Your MCP Connection{% endblock %}
{% block content %}
<section>
    <h1>You're connected!</h1>
    <p>Your MCP endpoint URL:</p>
    <pre><code id="mcp-url">{{ mcp_url }}</code></pre>
    <button onclick="navigator.clipboard.writeText(document.getElementById('mcp-url').textContent)">
        Copy URL
    </button>
    <p>Organization: {{ org_name }}</p>
    <p><a href="/setup-guide">Setup Guide: How to add this to ChatGPT</a></p>
</section>
{% endblock %}
```

`src/pco_mcp/web/templates/setup_guide.html`:
```html
{% extends "base.html" %}
{% block title %}Setup Guide{% endblock %}
{% block content %}
<section>
    <h1>Add Planning Center to ChatGPT</h1>
    <ol>
        <li>
            <h3>Open ChatGPT Settings</h3>
            <p>In ChatGPT, click your profile icon, then "Settings".</p>
        </li>
        <li>
            <h3>Go to Apps</h3>
            <p>Click "Apps" in the left sidebar.</p>
        </li>
        <li>
            <h3>Create a new App</h3>
            <p>Click "Create" and give it a name like "Planning Center".</p>
        </li>
        <li>
            <h3>Paste your MCP URL</h3>
            <p>Paste the URL from your dashboard into the URL field.</p>
        </li>
        <li>
            <h3>Done!</h3>
            <p>Start a new chat and ask ChatGPT about your Planning Center data.</p>
        </li>
    </ol>
    <h2>Example questions you can ask</h2>
    <ul>
        <li>"Who are the volunteers at our church?"</li>
        <li>"What songs are scheduled for this Sunday?"</li>
        <li>"Show me upcoming service plans"</li>
        <li>"Find the contact info for John Smith"</li>
    </ul>
</section>
{% endblock %}
```

- [ ] **Step 4: Implement web/routes.py**

```python
# src/pco_mcp/web/routes.py
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

TEMPLATE_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "landing.html")


@router.get("/setup-guide", response_class=HTMLResponse)
async def setup_guide(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "setup_guide.html")
```

- [ ] **Step 5: Wire web routes into main.py**

Add to `create_app()` in `src/pco_mcp/main.py`, after the health check:

```python
    from pco_mcp.web.routes import router as web_router
    app.include_router(web_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_web_routes.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add src/pco_mcp/web/ tests/test_web_routes.py src/pco_mcp/main.py
git commit -m "feat: add landing page, dashboard, and setup guide"
```

---

## Task 15: Shared Test Fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create conftest with shared fixtures**

```python
# tests/conftest.py
import os
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure test environment variables are set for all tests."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PCO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("PCO_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("BASE_URL", "https://pco-mcp.test")
```

- [ ] **Step 2: Remove duplicate env patching from test_config.py, test_main.py, test_web_routes.py**

Each of these files has its own environment setup. Replace with use of the conftest fixture. Remove the `monkeypatch.setenv` blocks from `test_config.py` tests and the `patch.dict("os.environ")` blocks from `test_main.py` and `test_web_routes.py`.

- [ ] **Step 3: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 4: Run coverage check**

Run: `pytest --cov=pco_mcp --cov-report=term-missing`
Expected: 90%+ coverage

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py tests/test_config.py tests/test_main.py tests/test_web_routes.py
git commit -m "refactor: add shared test conftest, remove duplicate env setup"
```

---

## Task 16: Static Analysis + Type Checking

**Files:**
- Modify: `pyproject.toml` (already configured in Task 1)

- [ ] **Step 1: Run mypy**

Run: `mypy src/pco_mcp --strict`
Expected: May have type errors to fix.

- [ ] **Step 2: Fix any type errors**

Address each mypy error. Common fixes: add return type annotations, fix `dict` -> `dict[str, Any]`, add `None` checks.

- [ ] **Step 3: Run ruff**

Run: `ruff check src/ tests/`
Expected: May have lint warnings.

- [ ] **Step 4: Fix any lint issues**

Run: `ruff check --fix src/ tests/`

- [ ] **Step 5: Run bandit**

Run: `bandit -r src/pco_mcp`
Expected: No high-severity issues. Ignore low-severity warnings about `secrets` module usage.

- [ ] **Step 6: Commit fixes**

```bash
git add -u
git commit -m "fix: resolve mypy, ruff, and bandit issues"
```

---

## Task 17: Mutation Testing

**Files:**
- No new files

- [ ] **Step 1: Run mutation testing on core modules**

Run:
```bash
mutmut run --paths-to-mutate src/pco_mcp/crypto.py
mutmut results
```

Expected: 80%+ mutation score on crypto module.

- [ ] **Step 2: Kill surviving mutants**

For each surviving mutant, run `mutmut show <id>` to see the mutation, then write a test that catches it.

- [ ] **Step 3: Run mutation testing on error mapping**

Run:
```bash
mutmut run --paths-to-mutate src/pco_mcp/errors.py
mutmut results
```

- [ ] **Step 4: Kill surviving mutants in errors module**

- [ ] **Step 5: Run mutation testing on PCO client**

Run:
```bash
mutmut run --paths-to-mutate src/pco_mcp/pco/client.py
mutmut results
```

- [ ] **Step 6: Kill surviving mutants in PCO client**

- [ ] **Step 7: Run full mutation test report**

Run:
```bash
mutmut run
mutmut results
mutmut html
```

Expected: 80%+ overall mutation score.

- [ ] **Step 8: Commit any new tests**

```bash
git add tests/
git commit -m "test: add mutation-testing-driven tests for surviving mutants"
```

---

## Task 18: Deployment Configuration

**Files:**
- Create: `Procfile`
- Create: `Dockerfile`
- Create: `railway.toml`

- [ ] **Step 1: Create Procfile**

```
web: uvicorn pco_mcp.main:create_app --factory --host 0.0.0.0 --port ${PORT:-8000}
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "pco_mcp.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Create railway.toml**

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn pco_mcp.main:create_app --factory --host 0.0.0.0 --port $PORT"
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

- [ ] **Step 4: Commit**

```bash
git add Procfile Dockerfile railway.toml
git commit -m "feat: add deployment config (Procfile, Dockerfile, Railway)"
```

---

## Task 19: Final Integration Test

**Files:**
- No new production files
- May add integration test file

- [ ] **Step 1: Run full test suite with coverage**

Run:
```bash
pytest --cov=pco_mcp --cov-report=term-missing --cov-report=html -v
```

Expected: 90%+ coverage, all tests pass.

- [ ] **Step 2: Run all static analysis**

Run:
```bash
mypy src/pco_mcp --strict
ruff check src/ tests/
bandit -r src/pco_mcp
```

Expected: All clean.

- [ ] **Step 3: Verify app starts**

Run:
```bash
cd /Users/christian/projects/pco-mcp
source .venv/bin/activate
uvicorn pco_mcp.main:create_app --factory --host 0.0.0.0 --port 8000 &
sleep 2
curl http://localhost:8000/health
curl http://localhost:8000/
kill %1
```

Expected: Health returns `{"status": "healthy"}`, landing page returns HTML.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final integration verification"
```
