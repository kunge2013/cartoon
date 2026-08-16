# -*- coding: utf-8 -*-
"""提示词体系 API：库 / 分类 / 片段 / 模板 / 预设（设计文档 05 §3）。"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prompt import Prompt, PromptPreset, PromptSnippet, PromptTemplate
from app.prompt_engine import list_variables

router = APIRouter()


# ------------------------------------------------------------------ schemas

class PromptIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category: str = "未分类"
    purpose: str = "generic"
    variables_json: str = "[]"
    is_system: bool = False
    enabled: bool = True


class PromptOut(PromptIn):
    id: int
    created_at: str | None = None
    updated_at: str | None = None


class SnippetIn(BaseModel):
    tag: str = "custom"
    name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    enabled: bool = True
    sort_order: int = 0


class TemplateIn(BaseModel):
    stage: str
    name: str = Field(min_length=1)
    body: str = Field(min_length=1)


class PresetIn(BaseModel):
    id: str = Field(min_length=3, max_length=100)
    stage: str
    name: str
    template_id: int
    slots_json: str = "{}"
    is_active: bool = False


# ------------------------------------------------------------------ prompts

@router.get("/prompts")
def list_prompts(
    category: str | None = None,
    purpose: str | None = None,
    keyword: str | None = None,
    is_system: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Prompt)
    if category:
        q = q.filter(Prompt.category == category)
    if purpose:
        q = q.filter(Prompt.purpose == purpose)
    if is_system is not None:
        q = q.filter(Prompt.is_system.is_(is_system))
    if keyword:
        q = q.filter(Prompt.title.contains(keyword) | Prompt.content.contains(keyword))
    total = q.count()
    rows = (
        q.order_by(Prompt.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "title": r.title, "category": r.category,
                "purpose": r.purpose, "is_system": r.is_system, "enabled": r.enabled,
                "content": r.content,
                "updated_at": str(r.updated_at or ""),
            }
            for r in rows
        ],
    }


@router.post("/prompts", status_code=201)
def create_prompt(data: PromptIn, db: Session = Depends(get_db)):
    p = Prompt(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id}


@router.get("/prompts/{prompt_id}")
def get_prompt(prompt_id: int, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    return {
        "id": p.id, "title": p.title, "content": p.content, "category": p.category,
        "purpose": p.purpose, "variables_json": p.variables_json,
        "is_system": p.is_system, "enabled": p.enabled,
        "created_at": str(p.created_at or ""), "updated_at": str(p.updated_at or ""),
    }


@router.put("/prompts/{prompt_id}")
def update_prompt(prompt_id: int, data: PromptIn, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    if p.is_system:
        # 系统条目：fork 为用户副本，原条目不动（设计文档 05 §6）
        fork = Prompt(
            title=data.title + "（副本）", content=data.content,
            category=data.category, purpose=data.purpose,
            variables_json=data.variables_json, is_system=False,
        )
        db.add(fork)
        db.commit()
        db.refresh(fork)
        return {"id": fork.id, "forked_from": p.id}
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"id": p.id}


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    if p.is_system:
        raise HTTPException(400, "system prompt cannot be deleted, fork instead")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/prompts/{prompt_id}/fork", status_code=201)
def fork_prompt(prompt_id: int, db: Session = Depends(get_db)):
    p = db.get(Prompt, prompt_id)
    if not p:
        raise HTTPException(404, "prompt not found")
    fork = Prompt(
        title=p.title + "（副本）", content=p.content, category=p.category,
        purpose=p.purpose, variables_json=p.variables_json, is_system=False,
    )
    db.add(fork)
    db.commit()
    db.refresh(fork)
    return {"id": fork.id}


@router.post("/prompts/import")
def import_prompts(items: list[dict], db: Session = Depends(get_db)):
    added = 0
    for row in items:
        exists = (
            db.query(Prompt)
            .filter(Prompt.title == row.get("title"), Prompt.category == row.get("category", "未分类"))
            .first()
        )
        if exists:
            continue
        db.add(Prompt(
            title=row["title"], content=row["content"],
            category=row.get("category", "未分类"),
            purpose=row.get("purpose", "generic"),
            is_system=bool(row.get("is_system", 0)),
        ))
        added += 1
    db.commit()
    return {"added": added}


@router.get("/prompts/export")
def export_prompts(category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Prompt)
    if category:
        q = q.filter(Prompt.category == category)
    return [
        {"title": r.title, "content": r.content, "category": r.category,
         "purpose": r.purpose, "is_system": int(r.is_system)}
        for r in q.all()
    ]


@router.get("/prompt-categories")
def prompt_categories(db: Session = Depends(get_db)):
    rows = (
        db.query(Prompt.category, db.query(Prompt).filter(Prompt.category.isnot(None)).count())
        .groupby(Prompt.category)
        .all()
    )
    return [{"category": c, "count": db.query(Prompt).filter(Prompt.category == c).count()} for c, _ in rows]


# ------------------------------------------------------------------ snippets

@router.get("/prompt-snippets")
def list_snippets(tag: str | None = None, db: Session = Depends(get_db)):
    q = db.query(PromptSnippet)
    if tag:
        q = q.filter(PromptSnippet.tag == tag)
    return [
        {"id": r.id, "tag": r.tag, "name": r.name, "content": r.content,
         "enabled": r.enabled, "sort_order": r.sort_order}
        for r in q.order_by(PromptSnippet.sort_order, PromptSnippet.id).all()
    ]


@router.post("/prompt-snippets", status_code=201)
def create_snippet(data: SnippetIn, db: Session = Depends(get_db)):
    s = PromptSnippet(**data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id}


@router.put("/prompt-snippets/{snippet_id}")
def update_snippet(snippet_id: int, data: SnippetIn, db: Session = Depends(get_db)):
    s = db.get(PromptSnippet, snippet_id)
    if not s:
        raise HTTPException(404, "snippet not found")
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    db.commit()
    return {"id": s.id}


@router.delete("/prompt-snippets/{snippet_id}")
def delete_snippet(snippet_id: int, db: Session = Depends(get_db)):
    s = db.get(PromptSnippet, snippet_id)
    if not s:
        raise HTTPException(404, "snippet not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ templates

@router.get("/prompt-templates")
def list_templates(stage: str | None = None, db: Session = Depends(get_db)):
    q = db.query(PromptTemplate)
    if stage:
        q = q.filter(PromptTemplate.stage == stage)
    return [
        {"id": r.id, "stage": r.stage, "name": r.name, "version": r.version,
         "body": r.body, "variables": list_variables(r.body)}
        for r in q.order_by(PromptTemplate.id).all()
    ]


@router.post("/prompt-templates", status_code=201)
def create_template(data: TemplateIn, db: Session = Depends(get_db)):
    t = PromptTemplate(**data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}


@router.put("/prompt-templates/{template_id}")
def update_template(template_id: int, data: TemplateIn, db: Session = Depends(get_db)):
    t = db.get(PromptTemplate, template_id)
    if not t:
        raise HTTPException(404, "template not found")
    for k, v in data.model_dump().items():
        setattr(t, k, v)
    t.version += 1
    db.commit()
    return {"id": t.id, "version": t.version}


@router.delete("/prompt-templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    t = db.get(PromptTemplate, template_id)
    if not t:
        raise HTTPException(404, "template not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ presets

@router.get("/prompt-presets")
def list_presets(stage: str | None = None, db: Session = Depends(get_db)):
    q = db.query(PromptPreset)
    if stage:
        q = q.filter(PromptPreset.stage == stage)
    return [
        {"id": r.id, "stage": r.stage, "name": r.name, "template_id": r.template_id,
         "slots_json": r.slots_json, "is_system": r.is_system, "is_active": r.is_active}
        for r in q.order_by(PromptPreset.stage, PromptPreset.id).all()
    ]


@router.post("/prompt-presets", status_code=201)
def create_preset(data: PresetIn, db: Session = Depends(get_db)):
    if db.get(PromptPreset, data.id):
        raise HTTPException(400, "preset id already exists")
    if not db.get(PromptTemplate, data.template_id):
        raise HTTPException(400, "template not found")
    p = PromptPreset(**data.model_dump())
    db.add(p)
    db.commit()
    return {"id": p.id}


@router.put("/prompt-presets/{preset_id}")
def update_preset(preset_id: str, data: PresetIn, db: Session = Depends(get_db)):
    p = db.get(PromptPreset, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"id": p.id}


@router.delete("/prompt-presets/{preset_id}")
def delete_preset(preset_id: str, db: Session = Depends(get_db)):
    p = db.get(PromptPreset, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    if p.is_system:
        raise HTTPException(400, "system preset cannot be deleted")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/prompt-presets/{preset_id}/activate")
def activate_preset(preset_id: str, db: Session = Depends(get_db)):
    p = db.get(PromptPreset, preset_id)
    if not p:
        raise HTTPException(404, "preset not found")
    db.query(PromptPreset).filter(PromptPreset.stage == p.stage).update(
        {"is_active": False}
    )
    p.is_active = True
    db.commit()
    return {"id": p.id, "stage": p.stage, "is_active": True}
