# -*- coding: utf-8 -*-
"""项目与分镜 ORM：projects + scripts（单表 + mode + extra JSON，见设计文档 04）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    novel_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("novels.id", ondelete="SET NULL"))
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manga")  # manga/camera
    art_style_id: Mapped[int | None] = mapped_column(Integer)
    derive_preset_id: Mapped[str] = mapped_column(String(100), default="plot_manga_fusion_bw")
    summary: Mapped[str] = mapped_column(Text, default="")
    img_prompt_prefix: Mapped[str] = mapped_column(Text, default="")
    img_prompt_suffix: Mapped[str] = mapped_column(Text, default="")
    vid_prompt_prefix: Mapped[str] = mapped_column(Text, default="")
    vid_prompt_suffix: Mapped[str] = mapped_column(Text, default="")
    sync_roles_from_novel: Mapped[bool] = mapped_column(Boolean, default=False)
    episode_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Script(Base):
    """分镜（manga/camera 单表；camera 专属字段入 extra JSON）。"""

    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="manga")
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shot_id: Mapped[int | None] = mapped_column(Integer)
    shot_index: Mapped[int] = mapped_column(Integer, default=1)
    content: Mapped[str] = mapped_column(Text, default="")          # 画面内容
    subtitles: Mapped[str] = mapped_column(Text, default="[]")      # 台词 JSON
    image_prompt: Mapped[str] = mapped_column(Text, default="")     # 三段式推导产物
    video_prompt: Mapped[str] = mapped_column(Text, default="")
    screen_prompt: Mapped[str] = mapped_column(Text, default="")
    main_image: Mapped[str] = mapped_column(String(500), default="")
    candidate_images: Mapped[str] = mapped_column(Text, default="{}")
    selected_candidate: Mapped[int | None] = mapped_column(Integer)
    reference_image: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_main_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    generation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra: Mapped[str] = mapped_column(Text, default="{}")
    prompt_touched: Mapped[bool] = mapped_column(Boolean, default=False)  # 手改保护
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
