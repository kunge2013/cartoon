# -*- coding: utf-8 -*-
"""小说文本清洗管线（规则引擎，不调 LLM）。对标源库 is_format/serial/punct_cleaned。

规则依据源应用行为取证：
- format：统一换行、去行首缩进/行尾空白、压缩 3+ 空行为 2
- serial：去章节数字/标题行（第X章/回/节、纯数字行、（一）、01. 等）、去连载号（1/2）
- punct：中英标点归一（相邻中文时半角转全角）、省略号 ... -> ……
- speech_quote：道/说/问等引语后补「」（源库 原文1 实证行为）
"""
from __future__ import annotations

import difflib
import re

CJK = r"\u4e00-\u9fff"


# ---------------------------------------------------------------- format

def format_clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for ln in text.split("\n"):
        ln = ln.strip()
        lines.append(ln)
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


# ---------------------------------------------------------------- serial

_SERIAL_LINE_PATTERNS = [
    re.compile(rf"^第\s*[0-9〇零一二三四五六七八九十百千]+\s*[章节回卷集话幕]\s*.*$"),
    re.compile(r"^[Cc]hapter\s*\d+.*$"),
    re.compile(r"^\d{1,4}[\.、．]?\s*$"),            # 纯数字行 01 / 1. / 1、
    re.compile(r"^[（(]\s*[0-9〇零一二三四五六七八九十]+\s*[)）]\s*$"),  # （一）(2)
    re.compile(r"^\d{1,4}\s*[、．.]\s*\S{0,20}$"),    # 01 标题
    re.compile(r"^正文\s*\d*\s*$"),
    re.compile(r"^（?\s*\d{1,4}\s*/\s*\d{1,4}\s*）?\s*$"),  # 连载号 1/2
]

_SERIAL_INLINE_PATTERNS = [
    re.compile(r"[（(]\s*\d{1,4}\s*/\s*\d{1,4}\s*[)）]"),   # （1/2）
    re.compile(r"[【\[]\s*\d{1,4}\s*/\s*\d{1,4}\s*[】\]]"),  # 【1/2】
]


def serial_clean(text: str) -> str:
    kept = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s and any(p.match(s) for p in _SERIAL_LINE_PATTERNS):
            continue  # 整行删除
        for p in _SERIAL_INLINE_PATTERNS:
            ln = p.sub("", ln)
        kept.append(ln)
    return "\n".join(kept)


# ---------------------------------------------------------------- punct

def _conv_adjacent_cjk(text: str, half: str, full: str) -> str:
    """仅当半角标点前后紧邻中文时转全角，避免破坏数字/英文。"""
    pat = re.compile(
        rf"(?<=[{CJK}]){re.escape(half)}(?=[{CJK}])|(?<=[{CJK}]){re.escape(half)}$"
    )
    return pat.sub(full, text)


def punct_clean(text: str) -> str:
    # 省略号
    text = re.sub(r"\.{3,}|。{3,}|…{1}(?!…)", "……", text)
    text = re.sub(r"…{3,}", "……", text)
    # 相邻中文的半角标点转全角
    for half, full in [(",", "，"), (";", "；"), (":", "："), ("!", "！"), ("?", "？")]:
        text = _conv_adjacent_cjk(text, half, full)
    # 句号：中文后半角句点，且后接中文/行尾/空行（避开小数 3.14 与英文缩写）
    text = re.sub(rf"(?<=[{CJK}])\.(?=[{CJK}]|$|\n)", "。", text)
    # 中文间的括号
    text = re.sub(rf"(?<=[{CJK}])\((?=[{CJK}])", "（", text)
    text = re.sub(rf"(?<=[{CJK}])\)(?=[{CJK}])", "）", text)
    return text


# ---------------------------------------------------------------- speech_quote

_SPEECH_VERB = (
    "说道|说|问道|问|答道|答|喊道|喊|叫道|叫|叹道|叹|骂道|骂|笑道|笑着说|嘀咕道|嘟哝道|"
    "喃喃道|沉声道|低声道|大声道|开口道|附和道|解释道|补充道|感慨道|无奈道|气道|催促道|"
    "纳闷道|轻声道|正色道|苦笑道|淡淡道|缓缓道|急道|忙道|又道|续道|回道|心道|暗道"
)
_QUOTES = "\u300c\u300d\u2018\u2019\u201c\u201d'\""  # 「」‘’“”'"
_NOT_QUOTE = "[^" + _QUOTES + "\n]"
_SPEECH_RE = re.compile(
    "(" + _SPEECH_VERB + ")[：:]\\s*(" + _NOT_QUOTE + "[^\\n]*)"
)


def speech_quote(text: str) -> str:
    """引语补全：无奈道：让你不要… -> 无奈道：「让你不要…」。已带引号的不处理。"""

    def _wrap(m: re.Match) -> str:
        verb, body = m.group(1), m.group(2).strip()
        if not body:
            return m.group(0)
        return f"{verb}：「{body}」"

    return _SPEECH_RE.sub(_wrap, text)


# ---------------------------------------------------------------- pipeline

RULES = {
    "format": (format_clean, "is_format_cleaned"),
    "serial": (serial_clean, "is_serial_cleaned"),
    "punct": (punct_clean, "is_punct_cleaned"),
    "speech_quote": (speech_quote, None),
}
DEFAULT_RULES = ["format", "serial", "punct", "speech_quote"]


def clean_pipeline(text: str, rules: list[str] | None = None) -> tuple[str, dict]:
    """返回 (清洗后文本, 各规则命中修改行数)。"""
    rules = rules or DEFAULT_RULES
    counts: dict[str, int] = {}
    for r in rules:
        if r not in RULES:
            raise ValueError(f"unknown rule: {r}")
    cur = text
    for r in rules:
        after = RULES[r][0](cur)
        changed = sum(
            1
            for a, b in zip(cur.split("\n"), after.split("\n"))
            if a != b
        ) + abs(len(cur.split("\n")) - len(after.split("\n")))
        counts[r] = changed
        cur = after
    return cur, counts


def unified_diff(before: str, after: str, name: str = "novel") -> str:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"{name}.before",
        tofile=f"{name}.after",
        n=1,
    )
    return "".join(diff)


def extract_name(text: str, fallback: str = "") -> str:
    """首行短且无句末标点 -> 作为书名；否则用 fallback。"""
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        if len(ln) <= 30 and not re.search(r"[。！？!?,，…]", ln):
            return ln
        break
    return fallback or "未命名小说"
