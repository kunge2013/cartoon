# -*- coding: utf-8 -*-
"""拼装引擎 API：阶段契约 / dry-run 预览 / 渲染历史（设计文档 05 §3.3、06 §7）。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.prompt import PromptRenderLog
from app.prompt_engine import Assembler, AssemblyContext, list_stages

router = APIRouter()


class PreviewIn(BaseModel):
    stage: str = Field(min_length=1)
    preset_id: str | None = None
    variables: dict = Field(default_factory=dict)
    persist_log: bool = True


@router.get("/assemble/stages")
def stages():
    return list_stages()


@router.post("/assemble/preview")
def preview(data: PreviewIn, db: Session = Depends(get_db)):
    if data.stage not in list_stages():
        raise HTTPException(422, f"unknown stage: {data.stage}")
    ctx = AssemblyContext(
        stage=data.stage,
        preset_id=data.preset_id,
        variables=data.variables,
        persist_log=data.persist_log,
    )
    asm = Assembler(db)
    try:
        result = asm.assemble(ctx)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "stage": result.stage,
        "preset_id": result.preset_id,
        "template_id": result.template_id,
        "segments": result.segments,
        "rendered": result.rendered,
        "log_id": result.log_id,
    }


@router.get("/render-logs")
def render_logs(
    stage: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(PromptRenderLog)
    if stage:
        q = q.filter(PromptRenderLog.stage == stage)
    total = q.count()
    rows = (
        q.order_by(PromptRenderLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "items": [
            {
                "id": r.id, "stage": r.stage, "preset_id": r.preset_id,
                "target_table": r.target_table, "target_id": r.target_id,
                "rendered": (r.rendered or "")[:200],
                "created_at": str(r.created_at or ""),
            }
            for r in rows
        ],
    }


@router.get("/render-logs/detail")
def render_log_detail(log_id: int, db: Session = Depends(get_db)):
    r = db.get(PromptRenderLog, log_id)
    if not r:
        raise HTTPException(404, "log not found")
    return {
        "id": r.id, "stage": r.stage, "preset_id": r.preset_id,
        "context_json": r.context_json, "rendered": r.rendered,
        "target_table": r.target_table, "target_id": r.target_id,
        "created_at": str(r.created_at or ""),
    }
