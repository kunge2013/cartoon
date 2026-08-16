# -*- coding: utf-8 -*-
"""角色推导服务：拼装引擎(S2) -> LLM -> JSON 角色列表 -> 入库。

解析容错：JSON 失败 -> 降级为行解析（名称：描述 / 名称/描述），再失败抛错。
"""
from __future__ import annotations

import json
import re

from sqlalchemy.orm import Session

from app.adapters.llm import chat
from app.models.role import Role, RoleTag
from app.prompt_engine import Assembler, AssemblyContext


def parse_roles_llm_output(text: str) -> list[dict]:
    """从 LLM 输出解析 [{name, content}]，多级容错。"""
    # 1) 剥 markdown 代码块
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    # 2) 找最外层 JSON 数组
    m = re.search(r"\[.*\]", cleaned, re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            roles = [
                {"name": str(r.get("name", "")).strip(), "content": str(r.get("content", "")).strip()}
                for r in arr
                if isinstance(r, dict) and r.get("name") and r.get("content")
            ]
            if roles:
                return roles
        except json.JSONDecodeError:
            pass
    # 3) 逐个对象抓取
    roles = []
    for om in re.finditer(r"\{[^{}]*\"name\"\s*:\s*\"([^\"]+)\"[^{}]*\"content\"\s*:\s*\"([^\"]*(?:\\.[^\"]*)*)\"[^{}]*\}", cleaned, re.S):
        roles.append({"name": om.group(1).strip(), "content": om.group(2).replace('\\"', '"').strip()})
    if roles:
        return roles
    # 4) 行解析降级：名称：描述 / 名称/描述
    for ln in cleaned.split("\n"):
        ln = ln.strip().lstrip("-*·0123456789. 、")
        if not ln:
            continue
        m2 = re.match(r"^([^：:/]{1,20})[：:]\s*(.{10,})$", ln)
        if m2:
            roles.append({"name": m2.group(1).strip(), "content": m2.group(2).strip()})
    return roles


def derive_roles(
    db: Session,
    novel_text: str,
    novel_id: int,
    preset_id: str | None = None,
    provider_code: str | None = None,
    model: str | None = None,
    replace_existing: bool = False,
    default_tag: tuple[str, str] | None = ("类型", "角色"),
) -> dict:
    """推导角色并入库。返回 {roles: [...], raw_output, log_id}。"""
    asm = Assembler(db)
    result = asm.assemble(
        AssemblyContext(
            stage="role_derive",
            preset_id=preset_id,
            variables={"novel_text": novel_text},
            target_table="novels",
            target_id=novel_id,
        )
    )
    raw = chat(db, result.rendered, provider_code=provider_code, model=model)
    roles = parse_roles_llm_output(raw)
    if not roles:
        raise ValueError(f"LLM 输出无法解析为角色列表：{raw[:200]}")

    if replace_existing:
        db.query(RoleTag).filter(
            RoleTag.role_id.in_(db.query(Role.id).filter(Role.novel_id == novel_id))
        ).delete(synchronize_session=False)
        db.query(Role).filter(Role.novel_id == novel_id).delete(synchronize_session=False)

    created = []
    for r in roles:
        exists = (
            db.query(Role)
            .filter(Role.novel_id == novel_id, Role.name == r["name"])
            .first()
        )
        if exists:
            exists.content = r["content"]
            row = exists
        else:
            row = Role(novel_id=novel_id, name=r["name"], content=r["content"], role_kind="library")
            db.add(row)
            db.flush()
            if default_tag:
                db.add(RoleTag(role_id=row.id, tag_category=default_tag[0], tag_value=default_tag[1]))
        created.append({"id": row.id, "name": row.name, "content": r["content"]})
    db.commit()
    return {"roles": created, "raw_output": raw, "log_id": result.log_id}
