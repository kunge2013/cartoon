# -*- coding: utf-8 -*-
"""小说中心 ORM：novels（多阶段字段）+ novel_files（多标签页正文）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    original_text: Mapped[str] = mapped_column(Text, default="")

    # AI 多阶段产物（Phase 3+ 写入）
    character_text: Mapped[str] = mapped_column(Text, default="")
    revised_text: Mapped[str] = mapped_column(Text, default="")
    script_text: Mapped[str] = mapped_column(Text, default="")
    storyboard_text: Mapped[str] = mapped_column(Text, default="")
    opening_text: Mapped[str] = mapped_column(Text, default="")
    character_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    revised_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    script_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    storyboard_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 清洗标记（对标源库 is_*_cleaned）
    is_format_cleaned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_serial_cleaned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_punct_cleaned: Mapped[bool] = mapped_column(Boolean, default=False)

    share_url: Mapped[str] = mapped_column(String(500), default="")
    score_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_report: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class NovelFile(Base):
    """多标签页正文（对标源库 custom_tabs 的结构化版本：原文1/原文2 分卷）。"""

    __tablename__ = "novel_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("novels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot_key: Mapped[str] = mapped_column(String(50), nullable=False)  # custom_1 / custom_2
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # 原文1 / 原文2
    content: Mapped[str] = mapped_column(Text, default="")
    anchor_tab: Mapped[str] = mapped_column(String(50), default="original")
    split_index: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
