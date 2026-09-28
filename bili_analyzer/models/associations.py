"""Many-to-many association tables for task-scoped entities."""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Table

from bili_analyzer.models.base import Base

task_videos = Table(
    "task_videos",
    Base.metadata,
    Column(
        "task_id",
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "video_id",
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

task_comments = Table(
    "task_comments",
    Base.metadata,
    Column(
        "task_id",
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "comment_id",
        ForeignKey("comments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

