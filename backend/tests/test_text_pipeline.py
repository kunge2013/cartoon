# -*- coding: utf-8 -*-
"""文本清洗管线单元测试（对标源库行为实证）。"""
from app.services.text_pipeline import (
    clean_pipeline,
    extract_name,
    format_clean,
    punct_clean,
    serial_clean,
    speech_quote,
)


def test_format_clean():
    raw = "\r\n\r\n  第一段。  \r\n\r\n\r\n\r\n\t第二段。\r\n"
    out = format_clean(raw)
    assert "第一段。\n\n第二段。" == out
    assert "\r" not in out


def test_serial_clean_removes_chapter_lines():
    text = "第1章 初见\n正文内容一。\n（一）\n内容二。\n01\n内容三。\nChapter 2 测试\n内容四。"
    out = serial_clean(text)
    assert "第1章" not in out
    assert "Chapter" not in out
    assert "（一）" not in out
    lines = [ln for ln in out.split("\n") if ln.strip()]
    assert lines == ["正文内容一。", "内容二。", "内容三。", "内容四。"]


def test_serial_clean_inline_numbers():
    text = "他笑了笑（1/2），继续说。"
    out = serial_clean(text)
    assert "1/2" not in out
    assert "他笑了笑，继续说。" == out


def test_punct_clean():
    text = "他来了,又走了;天黑了:下雨了!是吗?"
    out = punct_clean(text)
    assert "他来了，又走了；天黑了：下雨了！是吗？" == out


def test_punct_ellipsis():
    assert punct_clean("等了许久...他还没回来。") .count("……") == 1
    assert punct_clean("单点…也是省略") .count("……") == 1


def test_punct_keeps_english():
    text = "version 1.2, hello world! (ok)"
    assert punct_clean(text) == text  # 相邻非中文不动


def test_speech_quote_wraps():
    text = "我娘过来戳戳我的额头，无奈道：让你不要偷偷跑到后山去凫水，偏不听！"
    out = speech_quote(text)
    assert "无奈道：「让你不要偷偷跑到后山去凫水，偏不听！」" in out


def test_speech_quote_skips_existing():
    text = "他说道：「已经带引号了。」"
    assert speech_quote(text) == text


def test_clean_pipeline_counts():
    text = "第1章 开端\r\n\r\n\r\n\r\n他抬头,望天...\n我纳闷道：爹，娘，怎么这么早？\n（2/3）"
    out, counts = clean_pipeline(text)
    assert "第1章" not in out
    assert "（2/3）" not in out
    assert "他抬头，望天……" in out
    assert "我纳闷道：「爹，娘，怎么这么早？」" in out
    assert all(v >= 0 for v in counts.values())


def test_extract_name():
    assert extract_name("纪姑娘的爱给谁都盛大\n\n第一章……", fallback="x") == "纪姑娘的爱给谁都盛大"
    assert extract_name("这是一段很长的正文第一句就不适合做书名，因为太长了。\n正文", fallback="书名") == "书名"
