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
    refresh_token_hash: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
