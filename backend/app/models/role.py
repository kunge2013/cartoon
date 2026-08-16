# -*- coding: utf-8 -*-
"""角色中心 ORM：roles / role_tags / category_tags（对标源库）。"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    novel_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int | None] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    alias: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")          # 视觉描述（注入提示词）
    content_word2: Mapped[str] = mapped_column(Text, default="")    # 三视图/精修提示词
    role_kind: Mapped[str] = mapped_column(String(20), default="library")  # library/asset
    cover_path: Mapped[str] = mapped_column(String(500), default="")
    reference_image_url: Mapped[str] = mapped_column(String(500), default="")
    portrait_previews_json: Mapped[str] = mapped_column(Text, default="[]")
    asset_art_style_json: Mapped[str] = mapped_column(Text, default="")
    audio_path: Mapped[str] = mapped_column(String(500), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RoleTag(Base):
    __tablename__ = "role_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    tag_category: Mapped[str] = mapped_column(String(50), nullable=False)
    tag_value: Mapped[str] = mapped_column(String(100), nullable=False)


class CategoryTag(Base):
    """标签字典（种子=源库 8 条：类型/时空）。"""

    __tablename__ = "category_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    tag_value: Mapped[str] = mapped_column(String(100), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
