# -*- coding: utf-8 -*-
"""设置与供应商 ORM：settings(K/V) + provider_accounts（账号池）。"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class ProviderAccount(Base):
    __tablename__ = "provider_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # deepseek/grsai/...
    base_url: Mapped[str] = mapped_column(String(300), default="")
    api_key: Mapped[str] = mapped_column(String(300), nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="")
    remark: Mapped[str] = mapped_column(String(200), default="")
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
