"""Video model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bili_analyzer.models.base import Base, TimestampMixin


class Video(Base, TimestampMixin):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bvid: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    aid: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    pubdate: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    play_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, index=True)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reply_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    author_mid: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)

