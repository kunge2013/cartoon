# -*- coding: utf-8 -*-
"""分镜服务测试：解析编号分镜输出。"""
from app.services.script_service import parse_numbered_shots


def test_parse_standard_numbered():
    """标准格式：1. 内容"""
    text = """1. 纪澄与谢煜扬在南州旧巷并肩而行，两人步调一致，身体距离极近。
2. 谢煜扬抓住纪澄的手腕，神情从震惊转为不舍，女孩仍未完全明白即将发生什么。
3. 任命文书、官印和被翻开的行囊特写，红色官印成为视觉焦点。"""
    shots = parse_numbered_shots(text)
    assert len(shots) == 3
    assert "纪澄与谢煜扬" in shots[0]
    assert "谢煜扬抓住" in shots[1]
    assert "任命文书" in shots[2]


def test_parse_chinese_colon():
    """中文冒号：1：内容"""
    text = "1：镜头一内容描述\n2：镜头二内容描述"
    shots = parse_numbered_shots(text)
    assert len(shots) == 2


def test_parse_with_shot_prefix():
    """带"镜头"前缀：镜头1：内容"""
    text = "镜头1：画面描述\n镜头2：另一个画面"
    shots = parse_numbered_shots(text)
    assert len(shots) == 2
    assert "画面描述" in shots[0]


def test_parse_mixed_format():
    """混合格式：有的带镜头前缀，有的不带"""
    text = "镜头1：第一个画面\n2：第二个画面\n3. 第三个画面"
    shots = parse_numbered_shots(text)
    assert len(shots) == 3


def test_parse_with_llm_preamble():
    """LLM 输出的前言/后语"""
    text = """好的，我已经完成了分镜拆分：

1. 纪澄与谢煜扬在南州旧巷并肩而行。
2. 两人相视而笑，步调一致。

希望这个分镜符合您的要求。"""
    shots = parse_numbered_shots(text)
    assert len(shots) == 2
    assert "纪澄" in shots[0]
    assert "相视而笑" in shots[1]


def test_parse_multiline_shot():
    """单镜头内容跨多行"""
    text = """1. 纪澄与谢煜扬
在南州旧巷并肩而行
2. 两人相视而笑"""
    shots = parse_numbered_shots(text)
    assert len(shots) == 2
    # 第一镜头应该包含换行后的内容
    assert "纪澄与谢煜扬" in shots[0]


def test_parse_empty_lines():
    """空行处理"""
    text = """1. 第一镜头

2. 第二镜头

3. 第三镜头"""
    shots = parse_numbered_shots(text)
    assert len(shots) == 3


def test_parse_no_numbers():
    """无编号内容应返回空"""
    text = "这是一段没有编号的文字"
    shots = parse_numbered_shots(text)
    assert len(shots) == 0


def test_parse_four_digit_number():
    """四位数编号"""
    text = "1234. 这是一个很长的分镜编号"
    shots = parse_numbered_shots(text)
    assert len(shots) == 1


def test_parse_response_phrases_filtered():
    """过滤常见应答语"""
    text = """好的，以下是分镜内容：

1. 第一个镜头
2. 第二个镜头

明白了吗？"""
    shots = parse_numbered_shots(text)
    assert len(shots) == 2
