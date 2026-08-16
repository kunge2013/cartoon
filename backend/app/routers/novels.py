# -*- coding: utf-8 -*-
"""小说中心 API：CRUD / TXT 导入 / 规则清洗（diff 预览或应用）/ 多标签页正文。"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.novel import Novel, NovelFile
from app.services.text_pipeline import (
    DEFAULT_RULES,
    RULES,
    clean_pipeline,
    extract_name,
    unified_diff,
)

router = APIRouter()


class NovelIn(BaseModel):
    name: str | None = None
    text: str = Field(min_length=1)


class NovelUpdate(BaseModel):
    name: str | None = None
    content: str | None = None
    share_url: str | None = None


class CleanIn(BaseModel):
    rules: list[str] = Field(default_factory=lambda: list(DEFAULT_RULES))
    apply: bool = False  # false=仅预览 diff


class NovelFileIn(BaseModel):
    slot_key: str = "custom_1"
    name: str = "原文1"
    content: str = ""
    anchor_tab: str = "original"
    split_index: int = 1


def _detail(n: Novel) -> dict:
    return {
        "id": n.id, "name": n.name,
        "content_length": len(n.content or ""),
        "original_text": n.original_text or "",
        "content": n.content or "",
        "character_text": n.character_text or "",
        "revised_text": n.revised_text or "",
        "script_text": n.script_text or "",
        "storyboard_text": n.storyboard_text or "",
        "is_format_cleaned": n.is_format_cleaned,
        "is_serial_cleaned": n.is_serial_cleaned,
        "is_punct_cleaned": n.is_punct_cleaned,
        "share_url": n.share_url,
        "created_at": str(n.created_at or ""),
        "updated_at": str(n.updated_at or ""),
    }


@router.get("/novels")
def list_novels(keyword: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Novel)
    if keyword:
        q = q.filter(Novel.name.contains(keyword))
    rows = q.order_by(Novel.id.desc()).all()
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id, "name": r.name,
                "content_length": len(r.content or ""),
                "is_format_cleaned": r.is_format_cleaned,
                "is_serial_cleaned": r.is_serial_cleaned,
                "is_punct_cleaned": r.is_punct_cleaned,
                "updated_at": str(r.updated_at or ""),
            }
            for r in rows
        ],
    }


@router.post("/novels", status_code=201)
def create_novel(data: NovelIn, db: Session = Depends(get_db)):
    name = data.name or extract_name(data.text)
    n = Novel(name=name, content=data.text, original_text=data.text)
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "name": n.name}


@router.post("/novels/import-txt", status_code=201)
async def import_txt(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    fallback = file.filename or "未命名小说"
    fallback = fallback.rsplit(".", 1)[0]
    name = extract_name(text, fallback=fallback)
    n = Novel(name=name, content=text, original_text=text)
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"id": n.id, "name": n.name, "length": len(text)}


@router.get("/novels/detail")
def get_novel(novel_id: int, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    return _detail(n)


@router.put("/novels/detail")
def update_novel(novel_id: int, data: NovelUpdate, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    if data.name is not None:
        n.name = data.name
    if data.content is not None:
        n.content = data.content  # 手工编辑只改工作正文，original_text 保留
    if data.share_url is not None:
        n.share_url = data.share_url
    db.commit()
    return {"ok": True}


@router.delete("/novels/detail")
def delete_novel(novel_id: int, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    db.query(NovelFile).filter(NovelFile.novel_id == novel_id).delete()
    db.delete(n)
    db.commit()
    return {"ok": True}


@router.post("/novels/clean")
def clean_novel(novel_id: int, data: CleanIn, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    bad = [r for r in data.rules if r not in RULES]
    if bad:
        raise HTTPException(422, f"unknown rules: {bad}")
    after, counts = clean_pipeline(n.content or "", data.rules)
    diff = unified_diff(n.content or "", after, name=n.name)
    if not data.apply:
        return {"applied": False, "counts": counts, "diff": diff[:20000],
                "before_len": len(n.content or ""), "after_len": len(after)}
    # 应用：只改工作正文；original_text 保留原样
    n.content = after
    for r in data.rules:
        flag = RULES[r][1]
        if flag:
            setattr(n, flag, True)
    db.commit()
    return {"applied": True, "counts": counts, "before_len": len(n.content or "") + 0,
            "after_len": len(after),
            "is_format_cleaned": n.is_format_cleaned,
            "is_serial_cleaned": n.is_serial_cleaned,
            "is_punct_cleaned": n.is_punct_cleaned}


# ---------------------------------------------------------------- 多标签页

@router.get("/novels/files")
def list_files(novel_id: int, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    rows = (
        db.query(NovelFile)
        .filter(NovelFile.novel_id == novel_id)
        .order_by(NovelFile.split_index, NovelFile.id)
        .all()
    )
    return {
        "total": len(rows),
        "items": [
            {
                "id": r.id, "slot_key": r.slot_key, "name": r.name,
                "anchor_tab": r.anchor_tab, "split_index": r.split_index,
                "content_length": len(r.content or ""),
                "updated_at": str(r.updated_at or ""),
            }
            for r in rows
        ],
    }


@router.post("/novels/files", status_code=201)
def upsert_file(novel_id: int, data: NovelFileIn, db: Session = Depends(get_db)):
    n = db.get(Novel, novel_id)
    if not n:
        raise HTTPException(404, "novel not found")
    row = (
        db.query(NovelFile)
        .filter(NovelFile.novel_id == novel_id, NovelFile.slot_key == data.slot_key)
        .first()
    )
    if row:
        row.name, row.content = data.name, data.content
        row.anchor_tab, row.split_index = data.anchor_tab, data.split_index
    else:
        row = NovelFile(novel_id=novel_id, **data.model_dump())
        db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "slot_key": row.slot_key}


@router.get("/novels/files/detail")
def get_file(file_id: int, db: Session = Depends(get_db)):
    r = db.get(NovelFile, file_id)
    if not r:
        raise HTTPException(404, "file not found")
    return {"id": r.id, "novel_id": r.novel_id, "slot_key": r.slot_key,
            "name": r.name, "content": r.content, "anchor_tab": r.anchor_tab,
            "split_index": r.split_index}


@router.delete("/novels/files/detail")
def delete_file(file_id: int, db: Session = Depends(get_db)):
    r = db.get(NovelFile, file_id)
    if not r:
        raise HTTPException(404, "file not found")
    db.delete(r)
    db.commit()
    return {"ok": True}
