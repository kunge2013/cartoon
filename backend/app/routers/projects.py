# -*- coding: utf-8 -*-
"""项目与分镜 API：Project CRUD + 分镜拆分 + 项目摘要 + Script CRUD。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.adapters.llm import LLMError, LLMNotConfigured
from app.database import get_db
from app.models.project import Project, Script
from app.services.script_service import do_split_storyboard, generate_summary

router = APIRouter()


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    novel_id: int | None = None
    mode: str = Field(default="manga", pattern="^(manga|camera)$")
    derive_preset_id: str = "plot_manga_fusion_bw"
    summary: str = ""
    img_prompt_prefix: str = ""
    img_prompt_suffix: str = ""
    vid_prompt_prefix: str = ""
    vid_prompt_suffix: str = ""


class SplitIn(BaseModel):
    preset_id: str | None = None
    provider_code: str | None = None
    model: str | None = None
    text_override: str | None = None
    replace_existing: bool = False


class SummaryIn(BaseModel):
    provider_code: str | None = None
    model: str | None = None
    max_words: int = 200


class ScriptIn(BaseModel):
    content: str = ""
    image_prompt: str = ""
    video_prompt: str = ""
    screen_prompt: str = ""
    main_image: str = ""
    candidate_images: str = "{}"
    selected_candidate: int | None = None
    reference_image: str = ""
    notes: str = ""
    is_main_locked: bool = False
    generation_enabled: bool = True
    duration: float | None = None
    extra: str = "{}"
    prompt_touched: bool = False


def _project_out(p: Project) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "novel_id": p.novel_id,
        "mode": p.mode,
        "derive_preset_id": p.derive_preset_id,
        "summary": p.summary,
        "img_prompt_prefix": p.img_prompt_prefix,
        "img_prompt_suffix": p.img_prompt_suffix,
        "vid_prompt_prefix": p.vid_prompt_prefix,
        "vid_prompt_suffix": p.vid_prompt_suffix,
        "created_at": str(p.created_at or ""),
        "updated_at": str(p.updated_at or ""),
    }


def _script_out(s: Script) -> dict:
    return {
        "id": s.id,
        "project_id": s.project_id,
        "mode": s.mode,
        "order_index": s.order_index,
        "shot_id": s.shot_id,
        "shot_index": s.shot_index,
        "content": s.content,
        "image_prompt": s.image_prompt,
        "video_prompt": s.video_prompt,
        "screen_prompt": s.screen_prompt,
        "main_image": s.main_image,
        "candidate_images": s.candidate_images,
        "selected_candidate": s.selected_candidate,
        "reference_image": s.reference_image,
        "notes": s.notes,
        "is_main_locked": s.is_main_locked,
        "generation_enabled": s.generation_enabled,
        "duration": s.duration,
        "extra": s.extra,
        "prompt_touched": s.prompt_touched,
        "created_at": str(s.created_at or ""),
        "updated_at": str(s.updated_at or ""),
    }


# ---------------------------------------------------------------- 项目 CRUD


@router.get("/projects")
def list_projects(keyword: str | None = None, db: Session = Depends(get_db)):
    q = db.query(Project)
    if keyword:
        q = q.filter(Project.name.contains(keyword))
    rows = q.order_by(Project.id.desc()).all()
    return {"total": len(rows), "items": [_project_out(p) for p in rows]}


@router.post("/projects", status_code=201)
def create_project(data: ProjectIn, db: Session = Depends(get_db)):
    p = Project(**data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"id": p.id}


@router.get("/projects/detail")
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    return _project_out(p)


@router.put("/projects/detail")
def update_project(project_id: int, data: ProjectIn, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit()
    return {"id": p.id}


@router.delete("/projects/detail")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    db.query(Script).filter(Script.project_id == project_id).delete()
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- 分镜拆分


@router.post("/projects/split")
def split(project_id: int, data: SplitIn, db: Session = Depends(get_db)):
    try:
        out = do_split_storyboard(
            db,
            project_id,
            preset_id=data.preset_id,
            provider_code=data.provider_code,
            model=data.model,
            text_override=data.text_override,
            replace_existing=data.replace_existing,
        )
    except LLMNotConfigured as e:
        raise HTTPException(409, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e))
    return out


# ---------------------------------------------------------------- 项目摘要


@router.post("/projects/summary")
def summary(project_id: int, data: SummaryIn, db: Session = Depends(get_db)):
    try:
        out = generate_summary(
            db,
            project_id,
            provider_code=data.provider_code,
            model=data.model,
            max_words=data.max_words,
        )
    except LLMNotConfigured as e:
        raise HTTPException(409, str(e))
    except LLMError as e:
        raise HTTPException(502, str(e))
    except (KeyError, ValueError) as e:
        raise HTTPException(422, str(e))
    return out


# ---------------------------------------------------------------- 分镜 CRUD


@router.get("/projects/scripts")
def list_scripts(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    rows = (
        db.query(Script)
        .filter(Script.project_id == project_id)
        .order_by(Script.order_index)
        .all()
    )
    return {"total": len(rows), "items": [_script_out(s) for s in rows]}


@router.post("/projects/scripts", status_code=201)
def create_script(project_id: int, data: ScriptIn, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    max_order = (
        db.query(Script)
        .filter(Script.project_id == project_id)
        .count()
    )
    s = Script(project_id=project_id, order_index=max_order, mode=p.mode, **data.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id}


@router.get("/projects/scripts/detail")
def get_script(script_id: int, db: Session = Depends(get_db)):
    s = db.get(Script, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    return _script_out(s)


@router.put("/projects/scripts/detail")
def update_script(script_id: int, data: ScriptIn, db: Session = Depends(get_db)):
    s = db.get(Script, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    old_prompt = s.image_prompt
    for k, v in data.model_dump().items():
        setattr(s, k, v)
    # 如果用户手动修改了 image_prompt，标记 prompt_touched
    if data.image_prompt and data.image_prompt != old_prompt:
        s.prompt_touched = True
    db.commit()
    return {"id": s.id}


@router.delete("/projects/scripts/detail")
def delete_script(script_id: int, db: Session = Depends(get_db)):
    s = db.get(Script, script_id)
    if not s:
        raise HTTPException(404, "script not found")
    db.delete(s)
    db.commit()
    return {"ok": True}


class ReorderIn(BaseModel):
    order: list[int]  # script id 列表，按新顺序


@router.put("/projects/scripts/reorder")
def reorder_scripts(project_id: int, data: ReorderIn, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    for new_idx, script_id in enumerate(data.order):
        s = db.get(Script, script_id)
        if s and s.project_id == project_id:
            s.order_index = new_idx
    db.commit()
    return {"ok": True, "count": len(data.order)}
