"""
ORM models for long-term memory storage.

Tables:
  task_memory      — previous tasks and their results
  solution_memory  — successful solutions with patterns
  user_preference  — key-value preferences per user
  knowledge_entry  — stored knowledge with topic/tags
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database.connection import Base


class TaskMemory(Base):
    __tablename__ = "task_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_description: Mapped[str] = mapped_column(Text)
    goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SolutionMemory(Base):
    __tablename__ = "solution_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    problem: Mapped[str] = mapped_column(Text)
    solution: Mapped[str] = mapped_column(Text)
    patterns_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_rating: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserPreference(Base):
    __tablename__ = "user_preference"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    key: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_user_preference"),
    )


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(500), index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
