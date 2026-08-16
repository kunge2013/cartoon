# -*- coding: utf-8 -*-
"""拼装引擎（★ 设计文档 06 的实现）。

管线：预设解析 -> 变量合并 -> Jinja2 渲染（StrictUndefined）-> 分段切分 -> 后处理 -> 落日志。
引擎不 import 业务模型，上下文由调用方备好，保证可独立单测。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from jinja2 import Environment, StrictUndefined
from sqlalchemy.orm import Session

from app.models.prompt import PromptPreset, PromptRenderLog, PromptSnippet, PromptTemplate

# ---------------------------------------------------------------- 分段模型

SEGMENT_ORDER = [
    "project_affix_prefix",
    "style_prefix",
    "system",
    "instruction",
    "context",
    "custom_slots",
    "project_affix_suffix",
    "negative",
]

SEG_MARK_RE = re.compile(r"<!--\s*#seg:([a-z_]+)\s*-->")

_jinja_env = Environment(
    undefined=StrictUndefined,
    trim_blocks=False,
    lstrip_blocks=False,
    keep_trailing_newline=True,
    autoescape=False,
)


@dataclass
class AssemblyContext:
    stage: str
    preset_id: str | None = None
    variables: dict = field(default_factory=dict)
    target_table: str | None = None
    target_id: int | None = None
    persist_log: bool = True


@dataclass
class Segment:
    key: str
    text: str


@dataclass
class AssemblyResult:
    stage: str
    preset_id: str | None
    template_id: int | None
    segments: list
    rendered: str
    log_id: int | None = None


# 已知可选变量的缺省值（模板引用但调用方未提供时不炸；未知变量仍由 StrictUndefined 报错）
OPTIONAL_DEFAULTS = {
    "project_summary": "",
    "roles": [],
    "prev_shots": [],
    "project_img_prefix": "",
    "project_img_suffix": "",
    "negative_suffix": "",
    "custom_1": "", "custom_2": "", "custom_3": "",
    "custom_4": "", "custom_5": "", "custom_6": "",
    "max_words": 200,
    "portrait_render": "",
    "art_style_name": "",
    "continue_from": "",
    "era_hint": "",
}


# ---------------------------------------------------------------- 阶段契约（设计文档 06 §3.1）

STAGE_CONTRACTS = {
    "role_derive": {
        "name": "角色视觉推导",
        "required": ["novel_text"],
        "optional": ["era_hint"],
        "output": "json_roles",
    },
    "role_portrait": {
        "name": "角色三视图生成（S1 直接拼装）",
        "required": ["role_content"],
        "optional": ["portrait_render", "art_style_name"],
        "output": "text",
    },
    "storyboard_short": {
        "name": "分镜拆分-短句版",
        "required": ["novel_text"],
        "optional": ["continue_from"],
        "output": "numbered_list",
    },
    "storyboard_long": {
        "name": "分镜拆分-长句版",
        "required": ["novel_text"],
        "optional": ["continue_from"],
        "output": "numbered_list",
    },
    "dialogue_split": {
        "name": "旁白/对白分离",
        "required": ["novel_text"],
        "optional": [],
        "output": "tagged_lines",
    },
    "rewrite": {
        "name": "文案同义改写",
        "required": ["novel_text"],
        "optional": [],
        "output": "plain_text",
    },
    "image_derive": {
        "name": "图片提示词推导（三段式）",
        "required": ["shot_content", "style_prefix"],
        "optional": [
            "roles", "prev_shots", "project_summary",
            "project_img_prefix", "project_img_suffix",
            "custom_1", "custom_2", "custom_3", "custom_4", "custom_5", "custom_6",
            "negative_suffix",
        ],
        "output": "three_part_text",
    },
    "video_derive": {
        "name": "视频提示词推导",
        "required": ["shot_content"],
        "optional": ["roles", "prev_shots"],
        "output": "shot_table",
    },
    "summary": {
        "name": "项目摘要",
        "required": ["novel_text"],
        "optional": ["max_words"],
        "output": "plain_text",
    },
    "image_request": {
        "name": "图片生成请求拼装（S1）",
        "required": ["image_prompt"],
        "optional": ["project_img_prefix", "project_img_suffix", "negative_suffix"],
        "output": "text",
    },
}


def list_stages() -> dict:
    return STAGE_CONTRACTS


# ---------------------------------------------------------------- 渲染

def render_template(body: str, variables: dict) -> str:
    tpl = _jinja_env.from_string(body)
    return tpl.render(**variables)


VAR_RE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")


def list_variables(body: str) -> list:
    found = [m.group(1) for m in VAR_RE.finditer(body)]
    seen, out = set(), []
    for v in found:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def split_segments(rendered: str) -> list:
    """按 <!--#seg:key--> 标记切分并剥离标记；未标记部分归入 'default'。"""
    segments = []
    marks = list(SEG_MARK_RE.finditer(rendered))
    if not marks:
        return [Segment("default", rendered.strip())]
    head = rendered[: marks[0].start()]
    if head.strip():
        segments.append(Segment("default", head.strip()))
    for i, m in enumerate(marks):
        key = m.group(1)
        seg_start = m.end()
        seg_end = marks[i + 1].start() if i + 1 < len(marks) else len(rendered)
        text = rendered[seg_start:seg_end].strip()
        if text:
            segments.append(Segment(key, text))
    return segments


def _postprocess(text: str) -> str:
    # 压缩 3+ 连续空行为 2（保留段落边界）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------- 拼装入口

class Assembler:
    def __init__(self, db: Session):
        self.db = db

    def _load_preset(self, ctx: AssemblyContext):
        q = self.db.query(PromptPreset).filter(PromptPreset.stage == ctx.stage)
        if ctx.preset_id:
            preset = q.filter(PromptPreset.id == ctx.preset_id).first()
            if preset is None:
                raise KeyError(f"preset not found: {ctx.preset_id}")
        else:
            preset = q.filter(PromptPreset.is_active.is_(True)).first()
            if preset is None:
                preset = q.first()
            if preset is None:
                raise KeyError(f"no preset for stage: {ctx.stage}")
        template = self.db.get(PromptTemplate, preset.template_id)
        if template is None:
            raise KeyError(f"template missing: {preset.template_id}")
        return preset, template

    def _merge_variables(self, ctx: AssemblyContext, preset: PromptPreset) -> dict:
        merged: dict = {}
        # 1) 片段注入：style_prefix / negative 等以片段为默认来源
        for snip in (
            self.db.query(PromptSnippet)
            .filter(PromptSnippet.enabled.is_(True))
            .order_by(PromptSnippet.sort_order, PromptSnippet.id)
            .all()
        ):
            if snip.tag == "style_prefix":
                merged.setdefault("style_prefix", snip.content)
            elif snip.tag == "negative":
                merged.setdefault("negative_suffix", snip.content)
            elif snip.tag == "portrait_render":
                merged.setdefault("portrait_render", snip.content)
        # 2) 预设槽位
        try:
            slots = json.loads(preset.slots_json or "{}")
        except json.JSONDecodeError:
            slots = {}
        for k, v in slots.items():
            if k == "attach_snippets":
                continue
            if v:
                merged[k] = v
        # 3) 上下文变量（最高优先级）
        merged.update(ctx.variables)
        # 4) 已知可选变量补默认值（防 StrictUndefined 误炸；required 仍强校验）
        for k, v in OPTIONAL_DEFAULTS.items():
            merged.setdefault(k, v)
        return merged

    def assemble(self, ctx: AssemblyContext) -> AssemblyResult:
        preset, template = self._load_preset(ctx)
        variables = self._merge_variables(ctx, preset)

        # 缺失必填变量 -> 明确报错（不静默出残缺提示词）
        contract = STAGE_CONTRACTS.get(ctx.stage, {})
        missing = [v for v in contract.get("required", []) if not variables.get(v)]
        if missing:
            raise ValueError(f"missing required variables: {missing}")

        rendered = render_template(template.body, variables)
        rendered = _postprocess(rendered)
        segments = split_segments(rendered)

        log_id = None
        if ctx.persist_log:
            log = PromptRenderLog(
                preset_id=preset.id,
                stage=ctx.stage,
                context_json=json.dumps(variables, ensure_ascii=False, default=str),
                rendered=rendered,
                target_table=ctx.target_table,
                target_id=ctx.target_id,
            )
            self.db.add(log)
            self.db.commit()
            self.db.refresh(log)
            log_id = log.id

        return AssemblyResult(
            stage=ctx.stage,
            preset_id=preset.id,
            template_id=template.id,
            segments=[{"key": s.key, "text": s.text} for s in segments],
            rendered=rendered,
            log_id=log_id,
        )
