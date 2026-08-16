# -*- coding: utf-8 -*-
"""角色推导输出解析测试（多级容错）。"""
from app.services.role_service import parse_roles_llm_output


def test_parse_clean_json():
    raw = '[{"name": "纪澄少年", "content": "一个12岁的古代南州活泼少女"}, {"name": "谢煜扬", "content": "一个12岁的小少爷"}]'
    roles = parse_roles_llm_output(raw)
    assert len(roles) == 2
    assert roles[0]["name"] == "纪澄少年"


def test_parse_markdown_fenced():
    raw = '好的，结果如下：\n```json\n[{"name": "苏晚", "content": "一个24岁的现代年轻女性"}]\n```'
    roles = parse_roles_llm_output(raw)
    assert len(roles) == 1 and roles[0]["name"] == "苏晚"


def test_parse_prefix_text():
    raw = '分析完成。\n[{"name": "甲", "content": "描述甲的外貌特征很长的一段话"}]\n以上。'
    roles = parse_roles_llm_output(raw)
    assert len(roles) == 1 and roles[0]["name"] == "甲"


def test_parse_line_fallback():
    raw = "纪澄少年：一个12岁的古代南州活泼少女\n谢煜扬：一个12岁的京城官宦小少爷"
    roles = parse_roles_llm_output(raw)
    assert len(roles) == 2
    assert roles[0]["name"] == "纪澄少年"
    assert "小少爷" in roles[1]["content"]


def test_parse_garbage_returns_empty():
    assert parse_roles_llm_output("今天天气不错。") == []
