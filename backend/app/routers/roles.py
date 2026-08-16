# -*- coding: utf-8 -*-
"""角色中心 API：CRUD / AI 推导 / 标签 / 标签字典。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.adapters.llm import LLMError, LLMNotConfigured
from app.database import get_db
from app.models.novel import Novel
from app.models.role import CategoryTag, Role, RoleTag
from app.services.role_service import derive_roles

router = APIRouter()


class RoleIn(BaseModel):
    novel_id: int | None = None
    name: str = Field(min_length=1, max_length=200)
    alias: str = ""
    content: str = ""
    content_word2: str = ""
    role_kind: str = "library"


class DeriveIn(BaseModel):
    novel_id: int
    preset_id: str | None = None
    provider_code: str | None = None
    model: str | None = None
    replace_existing: bool = False
    text_override: str | None = None  # 不传则用小说正文


def _out(r: Role, tags: list | None = None) -> dict:
    return {
        "id": r.id, "novel_id": r.novel_id, "name": r.name, "alias": r.alias,
        "content": r.content, "content_word2": r.content_word2,
        "role_kind": r.role_kind, "cover_path": r.cover_path,
        "order_index": r.order_index,
        "tags": tags if tags is not None else [],
        "updated_at": str(r.updated_at or ""),
    }


@router.get("/roles")
def list_roles(novel_id: int | None = None, keyword: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Role)
    if novel_id:
        q = q.filter(Role.novel_id == novel_id)
    if keyword:
        q = q.filter(Role.name.contains(keyword) | Role.alias.contains(keyword))
    rows = q.order_by(Role.order_index, Role.id).all()
    tag_map: dict[int, list] = {}
    for t in db.query(RoleTag).all():
        tag_map.setdefault(t.role_id, []).append({"category": t.tag_category, "value": t.tag_value})
    return {"total": len(rows), "items": [_out(r, tag_map.get(r.id, [])) for r in rows]}


@router.post("/roles", status_code=201)
def create_role(data: RoleIn, db: Session = Depends(get_db)):
    r = Role(**data.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"id": r.id}


@router.get("/roles/detail")
def get_role(role_id: int, db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "role not found")
    tags = [{"category": t.tag_category, "value": t.tag_value}
            for t in db.query(RoleTag).filter(RoleTag.role_id == role_id)]
    return _out(r, tags)


@router.put("/roles/detail")
def update_role(role_id: int, data: RoleIn, db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "role not found")
    for k, v in data.model_dump().items():
        setattr(r, k, v)
    db.commit()
    return {"id": r.id}


@router.delete("/roles/detail")
def delete_role(role_id: int, db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "role not found")
    db.query(RoleTag).filter(RoleTag.role_id == role_id).delete()
    db.delete(r)
    db.commit()
    return {"ok": True}


@router.put("/roles/tags")
def set_role_tags(role_id: int, tags: list[dict], db: Session = Depends(get_db)):
    r = db.get(Role, role_id)
    if not r:
        raise HTTPException(404, "role not found")
    db.query(RoleTag).filter(RoleTag.role_id == role_id).delete()
    for t in tags:
        db.add(RoleTag(role_id=role_id, tag_category=t.get("category", ""), tag_value=t.get("value", "")))
    db.commit()
    return {"ok": True, "count": len(tags)}


@router.post("/roles/derive")
def derive(data: DeriveIn, db: Session = Depends(get_db)):
    novel = db.get(Novel, data.novel_id)
    if not novel:
        raise HTTPException(404, "novel not found")
    text = data.text_override or novel.content or ""
    if not text.strip():
        raise HTTPException(422, "novel text is empty")
    try:
        out = derive_roles(
            db, text, data.novel_id,
            preset_id=data.preset_id,
            provider_code=data.provider_code,
            model=data.model,
            replace_existing=data.replace_existing,
        )
    except LLMNotConfigured as e:
        raise HTTPException(409, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))
    except ValueError as e:
        raise HTTPException(502, str(e))
    return {"count": len(out["roles"]), "roles": out["roles"], "log_id": out["log_id"]}


# ---------------------------------------------------------------- 标签字典

@router.get("/category-tags")
def list_category_tags(db: Session = Depends(get_db)):
    rows = db.query(CategoryTag).order_by(CategoryTag.category, CategoryTag.display_order).all()
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(r.category, []).append(r.tag_value)
    return {"categories": grouped}


@router.post("/category-tags", status_code=201)
def add_category_tag(category: str, tag_value: str, display_order: int = 0, db: Session = Depends(get_db)):
    exists = (
        db.query(CategoryTag)
        .filter(CategoryTag.category == category, CategoryTag.tag_value == tag_value)
        .first()
    )
    if exists:
        return {"id": exists.id}
    row = CategoryTag(category=category, tag_value=tag_value, display_order=display_order)
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id}
