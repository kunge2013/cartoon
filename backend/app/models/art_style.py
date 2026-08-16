# -*- coding: utf-8 -*-
"""画风库 ORM：art_styles（画风管理）。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ArtStyle(Base):
    """画风定义。"""
    
    __tablename__ = "art_styles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="")
    prefix: Mapped[str] = mapped_column(Text, default="")
    suffix: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    preview_image: Mapped[str] = mapped_column(Text, default="")
    reference_image: Mapped[str] = mapped_column(Text, default="")
    recommended_model: Mapped[str] = mapped_column(String(100), default="")
    recommended_aspect_ratio: Mapped[str] = mapped_column(String(20), default="3:4")
    recommended_resolution: Mapped[str] = mapped_column(String(20), default="2K")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
