# -*- coding: utf-8 -*-
"""catong_gen 后端配置。"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 仓库根
DATA_DIR = Path(os.environ.get("CATONG_DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = Path(os.environ.get("CATONG_OUTPUT_DIR", BASE_DIR / "Output"))
ROLES_DIR = BASE_DIR / "roles"
LOG_DIR = BASE_DIR / "logs"

for _d in (DATA_DIR, OUTPUT_DIR, ROLES_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_URL = os.environ.get(
    "CATONG_DB_URL", f"sqlite:///{(DATA_DIR / 'catong_gen.db').as_posix()}"
)

APP_NAME = "catong_gen"
APP_VERSION = "0.1.0-phase0"
