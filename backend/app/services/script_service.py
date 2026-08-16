# -*- coding: utf-8 -*-
"""分镜服务：AI 拆分分镜（storyboard 预设）+ 编号列表解析 + 项目摘要。"""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.adapters.llm import chat
from app.models.project import Project, Script
from app.prompt_engine import Assembler, AssemblyContext


def parse_numbered_shots(text: str) -> list[str]:
    """解析 LLM 输出的编号分镜：1. xxx / 1、xxx / 镜头1：xxx。"""
    shots: list[str] = []
    for raw_ln in text.split("\n"):
        ln = raw_ln.strip()
        if not ln:
            continue
        m = re.match(r"^(?:镜头|镜|分镜)?\s*(\d{1,4})\s*[\.、．:：]\s*(.+)$", ln)
        if m:
            body = m.group(2).strip()
            if body:
                shots.append(body)
            continue
        # 无编号的续行：并入上一条（长句被折行）
        if shots and not re.match(r"^(镜头|镜|分镜)", ln):
            shots[-1] += ln
    # 过滤掉明显的应答语
    shots = [s for s in shots if not re.match(r"^(好的|明白|以下是|接下来|短句版本|长句版本)", s)]
    return shots


def _novel_content(db: Session, novel_id: int | None) -> str:
    from app.models.novel import Novel

    if not novel_id:
        return ""
    n = db.get(Novel, novel_id)
    return (n.content or "") if n else ""


def do_split_storyboard(
    db: Session,
    project_id: int,
    preset_id: str | None = None,
    provider_code: str | None = None,
    model: str | None = None,
    text_override: str | None = None,
    replace_existing: bool = False,
) -> dict:
    """执行拆分并写 scripts 表。"""
    from app.models.novel import Novel

    project = db.get(Project, project_id)
    if project is None:
        raise KeyError("project not found")
    text = text_override
    if not text:
        n = db.get(Novel, project.novel_id) if project.novel_id else None
        text = (n.content or "") if n else ""
    if not (text or "").strip():
        raise ValueError("novel text is empty")

    asm = Assembler(db)
    result = asm.assemble(
        AssemblyContext(
            stage="storyboard_short",
            preset_id=preset_id,
            variables={"novel_text": text[:8000]},
            target_table="projects",
            target_id=project_id,
        )
    )
    raw = chat(db, result.rendered, provider_code=provider_code, model=model, max_tokens=8192)
    shots = parse_numbered_shots(raw)
    if not shots:
        raise ValueError(f"无法解析分镜输出：{raw[:200]}")

    if replace_existing:
        db.query(Script).filter(Script.project_id == project_id).delete(synchronize_session=False)

    start_index = (
        db.query(Script).filter(Script.project_id == project_id).count()
    )
    rows = []
    for i, s in enumerate(shots):
        row = Script(
            project_id=project_id,
            mode=project.mode,
            order_index=start_index + i,
            shot_id=start_index + i + 1,
            shot_index=1,
            content=s,
        )
        db.add(row)
        rows.append(row)
    db.commit()
    return {"count": len(rows), "first": rows[0].content if rows else "", "log_id": result.log_id}


def generate_summary(
    db: Session,
    project_id: int,
    provider_code: str | None = None,
    model: str | None = None,
    max_words: int = 200,
) -> dict:
    project = db.get(Project, project_id)
    if project is None:
        raise KeyError("project not found")
    text = _novel_content(db, project.novel_id)
    if not text.strip():
        raise ValueError("novel text is empty")
    asm = Assembler(db)
    result = asm.assemble(
        AssemblyContext(
            stage="summary",
            variables={"novel_text": text[:6000], "max_words": max_words},
            target_table="projects",
            target_id=project_id,
        )
    )
    summary = chat(db, result.rendered, provider_code=provider_code, model=model, max_tokens=1024).strip()
    project.summary = summary
    db.commit()
    return {"summary": summary, "log_id": result.log_id}
