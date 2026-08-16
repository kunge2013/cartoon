# -*- coding: utf-8 -*-
"""调试 speech_quote 行为。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.text_pipeline import clean_pipeline

text = "第1章 开端\r\n\r\n\r\n\r\n他抬头,望天...\n我纳闷道：爹，娘，怎么这么早？\n（2/3）"
out, counts = clean_pipeline(text)
for ln in out.split("\n"):
    print(repr(ln))
print("counts:", counts)
