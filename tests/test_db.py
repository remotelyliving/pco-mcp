import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pco_mcp.models import Base, OAuthSession, User


@pytest.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    # Enable foreign key enforcement for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
