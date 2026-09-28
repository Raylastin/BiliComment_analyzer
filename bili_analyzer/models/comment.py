"""Comment model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bili_analyzer.models.base import Base, TimestampMixin


class Comment(Base, TimestampMixin):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rpid: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    bvid: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    mid: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    parent_rpid: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    root_rpid: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    ctime: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    like_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    emotion_label: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    emotion_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

