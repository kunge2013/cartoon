# -*- coding: utf-8 -*-
"""提示词五件套 ORM 模型（★ Phase 1 核心）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prompt(Base):
    """提示词库条目（对标源库 prompts 表，扩展 purpose/variables/enabled）。"""

    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="未分类")
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="generic")
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PromptSnippet(Base):
    """片段：可复用小块（负面后缀/画风前缀/质量词/三视图渲染词）。"""

    __tablename__ = "prompt_snippets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tag: Mapped[str] = mapped_column(String(50), nullable=False, default="custom")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PromptTemplate(Base):
    """模板：某业务阶段的主体指令（Jinja2 语法，含 <!--#seg:key--> 分段标记）。"""

    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PromptPreset(Base):
    """预设：阶段 + 模板 + 槽位（对标 manga_derive_presets / plot_manga_fusion_bw）。"""

    __tablename__ = "prompt_presets"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prompt_templates.id"), nullable=False
    )
    slots_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PromptRenderLog(Base):
    """渲染历史：每次拼装留痕（对标 manga_derive_llm_raw_log 的强化版）。"""

    __tablename__ = "prompt_render_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    preset_id: Mapped[str] = mapped_column(String(100), nullable=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    context_json: Mapped[str] = mapped_column(Text, nullable=True)
    rendered: Mapped[str] = mapped_column(Text, nullable=True)
    target_table: Mapped[str] = mapped_column(String(50), nullable=True)
    target_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
