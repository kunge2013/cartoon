# -*- coding: utf-8 -*-
"""拼装引擎单元测试（渲染快照，防模板静默变化）。"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.prompt import PromptPreset, PromptSnippet, PromptTemplate
from app.prompt_engine import (
    AssemblyContext,
    Assembler,
    list_variables,
    render_template,
    split_segments,
)


@pytest.fixture()
def db():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng)
    session = S()
    # 最小数据：image_derive 模板 + 预设 + 片段
    tpl = PromptTemplate(
        stage="image_derive",
        name="t",
        body=(
            "<!--#seg:system-->\n你是画师。\n\n"
            "<!--#seg:context-->\n【本镜】{{ shot_content }}\n"
            "{% for r in roles %}【角色】{{ r.name }}\n{% endfor %}"
            "\n\n<!--#seg:negative-->\n{{ negative_suffix }}"
        ),
    )
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    session.add(PromptPreset(id="p1", stage="image_derive", name="p", template_id=tpl.id, is_active=True))
    session.add(PromptSnippet(tag="negative", name="n", content="禁止水印。"))
    session.commit()
    yield session
    session.close()


def test_list_variables():
    body = "{{ a }} x {{ b }} {{ a }}"
    assert list_variables(body) == ["a", "b"]


def test_split_segments_marks_stripped():
    rendered = "<!--#seg:system-->\nS\n\n<!--#seg:negative-->\nN"
    segs = split_segments(rendered)
    assert [s.key for s in segs] == ["system", "negative"]
    assert segs[0].text == "S"
    assert "#seg" not in segs[0].text


def test_render_strict_undefined_raises():
    with pytest.raises(Exception):
        render_template("{{ missing_var }}", {})


def test_assemble_segments_and_negative_last(db):
    asm = Assembler(db)
    result = asm.assemble(
        AssemblyContext(
            stage="image_derive",
            variables={"shot_content": "镜头A", "style_prefix": "韩漫画风", "roles": [{"name": "甲"}]},
            persist_log=False,
        )
    )
    keys = [s["key"] for s in result.segments]
    assert keys == ["system", "context", "negative"]
    assert result.segments[-1]["text"] == "禁止水印。"
    assert "镜头A" in result.rendered
    assert "甲" in result.rendered


def test_assemble_missing_required(db):
    asm = Assembler(db)
    with pytest.raises(ValueError):
        asm.assemble(AssemblyContext(stage="image_derive", variables={}))
