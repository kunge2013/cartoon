# -*- coding: utf-8 -*-
"""设置中心 API：K/V 设置 + LLM 供应商账号池。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.provider import ProviderAccount, Setting

router = APIRouter()


class SettingIn(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    value: str = ""


class AccountIn(BaseModel):
    provider_code: str = Field(min_length=1, max_length=50)
    base_url: str = ""
    api_key: str = Field(min_length=1)
    model: str = ""
    remark: str = ""
    valid: bool = True


HIDDEN_KEYS = {"llm_default_provider", "image_provider"}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    rows = db.query(Setting).all()
    return {r.key: r.value for r in rows}


@router.put("/settings")
def put_setting(data: SettingIn, db: Session = Depends(get_db)):
    row = db.get(Setting, data.key)
    if row:
        row.value = data.value
    else:
        db.add(Setting(key=data.key, value=data.value))
    db.commit()
    return {"ok": True}


@router.get("/provider-accounts")
def list_accounts(db: Session = Depends(get_db)):
    rows = db.query(ProviderAccount).order_by(ProviderAccount.id).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id, "provider_code": r.provider_code, "base_url": r.base_url,
                "model": r.model, "remark": r.remark, "valid": r.valid,
                "api_key_tail": r.api_key[-6:] if len(r.api_key) > 6 else "***",
            }
            for r in rows
        ],
    }


@router.post("/provider-accounts", status_code=201)
def add_account(data: AccountIn, db: Session = Depends(get_db)):
    row = ProviderAccount(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}


@router.delete("/provider-accounts/detail")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    row = db.get(ProviderAccount, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    db.delete(row)
    db.commit()
    return {"ok": True}
