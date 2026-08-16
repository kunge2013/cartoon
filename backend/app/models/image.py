# -*- coding: utf-8 -*-
"""图片生成任务 ORM：image_tasks（状态机 + 候选图管理）。"""
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImageTask(Base):
    """图片生成任务（对标源库 batch_hang_scheduler）。"""
    
    __tablename__ = "image_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    script_id: Mapped[int] = mapped_column(Integer, ForeignKey("scripts.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    
    # 任务状态机：pending -> running -> done/failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/running/done/failed
    
    # 生成参数
    image_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False, default="grsai")  # grsai/openai_compatible
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="nano-banana-2")
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="3:4")
    resolution: Mapped[str] = mapped_column(String(20), default="2K")
    
    # 生成结果
    image_url: Mapped[str] = mapped_column(String(500), default="")  # 生成的图片 URL 或本地路径
    candidate_index: Mapped[int | None] = mapped_column(Integer)  # 在候选图中的索引
    is_main: Mapped[bool] = mapped_column(default=False)  # 是否被选为主图
    
    # 错误信息
    error_message: Mapped[str] = mapped_column(Text, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # 性能指标
    generation_time: Mapped[float | None] = mapped_column(Float, nullable=True)  # 秒
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
