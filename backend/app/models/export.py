# -*- coding: utf-8 -*-
"""图片导出 ORM：export_tasks（导出任务状态机）。"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExportTask(Base):
    """图片导出任务。"""
    
    __tablename__ = "export_tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    
    # 任务状态机：pending -> running -> done/failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    
    # 导出参数
    export_style: Mapped[str] = mapped_column(String(50), default="vertical")  # vertical/horizontal
    page_numbers: Mapped[bool] = mapped_column(default=False)  # 是否添加页码
    titles: Mapped[bool] = mapped_column(default=False)  # 是否添加标题
    quality: Mapped[int] = mapped_column(Integer, default=90)  # JPEG 质量 (1-100)
    
    # 导出结果
    output_path: Mapped[str] = mapped_column(Text, default="")  # 导出文件路径（相对路径）
    file_size: Mapped[int | None] = mapped_column(Integer)  # 文件大小（字节）
    
    # 错误信息
    error_message: Mapped[str] = mapped_column(Text, default="")
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
