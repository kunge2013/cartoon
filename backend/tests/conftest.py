# -*- coding: utf-8 -*-
"""catong_gen 测试共享 fixture（E2E mock 与隔离）。

把 ``tests/test_e2e_api.py`` 里几处强相关的 autouse fixture 抽出来，
方便 ``tests/test_e2e_full_flow.py`` 直接复用，避免重复实现。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 进程级临时目录 + in-memory DB（与 test_e2e_api.py 保持一致）
_TMPDIR = tempfile.mkdtemp(prefix="catong_e2e_")
os.environ.setdefault("CATONG_DATA_DIR", _TMPDIR)
os.environ.setdefault("CATONG_OUTPUT_DIR", _TMPDIR)

import app.database as _app_db_pre  # noqa: E402
from app.database import Base as _Base  # noqa: E402
import app.models.novel  # noqa: E402,F401
import app.models.role  # noqa: E402,F401
import app.models.project  # noqa: E402,F401
import app.models.image  # noqa: E402,F401
import app.models.export  # noqa: E402,F401
import app.models.prompt  # noqa: E402,F401
import app.models.provider  # noqa: E402,F401
import app.models.art_style  # noqa: E402,F401

_PRE_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_Base.metadata.create_all(_PRE_ENGINE)
_app_db_pre.engine = _PRE_ENGINE
_PRE_SESSION = sessionmaker(bind=_PRE_ENGINE, autoflush=False, expire_on_commit=False)
_app_db_pre.SessionLocal = _PRE_SESSION


@pytest.fixture()
def seed_basics(_pre_session):
    """为单测注入两个 mock 供应商账号（deepseek / grsai）。

    conftest 启动时已经塞过默认账号，但 ``_clean_per_test`` 会清空
    ProviderAccount，所以这里重新塞一遍。
    """
    from app.models.provider import ProviderAccount
    s = _pre_session()
    try:
        s.add_all([
            ProviderAccount(
                provider_code="deepseek", base_url="https://api.deepseek.com/v1",
                api_key="mock-ds-key", model="deepseek-chat", valid=True,
            ),
            ProviderAccount(
                provider_code="grsai", base_url="https://api.grsai.com/v1",
                api_key="mock-grsai-key", model="nano-banana-2", valid=True,
            ),
        ])
        s.commit()
    finally:
        s.close()


@pytest.fixture()
def _pre_session():
    """从 conftest 暴露 in-memory SessionLocal 工厂。"""
    return _PRE_SESSION


# ---------------------------------------------------------------- 一次性 seed
# 进程级：导入 conftest 时把提示词五件套 + 默认 settings 写入 _PRE_ENGINE。
# 这模拟 ``python -m app.seeds.seed`` 的效果，但走的是 in-memory DB，
# 不污染主库 ``data/catong_gen.db``。
def _bootstrap_seed_data():
    import json as _json
    from app.models.prompt import (Prompt, PromptPreset, PromptSnippet,
                                    PromptTemplate)
    from app.models.role import CategoryTag
    from app.models.provider import ProviderAccount
    from app.seeds.seed import (TEMPLATES, IMAGE_DERIVE_BODY, SUMMARY_BODY,
                                PORTRAIT_BODY, PRESETS)

    src_path = Path(__file__).parent.parent / "app" / "seeds" / "source_prompts.json"
    if not src_path.exists():
        return
    src = _json.loads(src_path.read_text(encoding="utf-8"))
    purpose_map = {
        "小说视频提示词指令": "video_derive",
        "获取人物形象": "role_derive",
        "角色三视图": "role_portrait",
        "人物形象视频": "role_video",
        "图片推导词默认前缀": "image_derive",
        "图片推导词默认后缀": "image_derive",
        "视频推导词默认前缀": "video_derive",
        "视频推导词默认后缀": "video_derive",
        "分镜提示词-短文本版": "storyboard_short",
        "分镜提示词-长文本版": "storyboard_long",
        "一键对话": "dialogue_split",
        "文案同义改写": "rewrite",
        "VIP智能角色推导": "role_derive",
    }
    s = _PRE_SESSION()
    try:
        for row in src:
            s.add(Prompt(
                title=row["title"], content=row["content"],
                category=row["category"],
                purpose=purpose_map.get(row["title"], "generic"),
                is_system=bool(row.get("is_system", 0)),
            ))
        s.add(PromptSnippet(tag="negative", name="平台水印禁令（源库实证）",
                            content="禁止：图片右下角出现腾讯动漫 17173 等其他机构水印！",
                            sort_order=0))
        s.add(PromptSnippet(tag="style_prefix", name="图片推导默认前缀（prompts#5）",
                            content="顶级韩漫风格，融合精致日系2D插画美学，精细线稿，柔和色彩，电影级光影，高对比度，",
                            sort_order=0))
        s.add(PromptSnippet(tag="portrait_render", name="三视图渲染公共词（roles 实证）",
                            content="strictly isolated on a pure white background, solid white backdrop, no cast shadows，无场景、无文字、无 logo。",
                            sort_order=1))
        src_by_title = {r["title"]: r["content"] for r in src}
        title_by_pid = {r["id"]: r["title"] for r in src}
        tpl_id_by_stage: dict = {}
        for stage, name, src_pid, extra in TEMPLATES:
            if src_pid is not None:
                body = src_by_title[title_by_pid[src_pid]] + extra
            elif stage == "image_derive":
                body = IMAGE_DERIVE_BODY
            elif stage == "summary":
                body = SUMMARY_BODY
            elif stage == "role_portrait":
                body = PORTRAIT_BODY
            else:
                continue
            tpl = PromptTemplate(stage=stage, name=name, body=body)
            s.add(tpl)
            s.flush()
            tpl_id_by_stage[stage] = tpl.id
        for pid, stage, name, tpl_stage, active in PRESETS:
            if tpl_stage not in tpl_id_by_stage:
                continue
            s.add(PromptPreset(
                id=pid, stage=stage, name=name,
                template_id=tpl_id_by_stage[tpl_stage],
                slots_json="{}", is_system=True, is_active=active,
            ))
        for cat, val, order in [
            ("类型", "角色", 0), ("类型", "场景", 1), ("类型", "道具", 2),
            ("时空", "古代", 0), ("时空", "现代", 1), ("时空", "科幻", 2),
            ("时空", "玄幻", 3), ("时空", "ABO", 4),
        ]:
            s.add(CategoryTag(category=cat, tag_value=val, display_order=order))
        from app.models.provider import Setting
        for k, v in {
            "llm_default_provider": "deepseek",
            "image_provider": "grsai",
            "image_model": "nano-banana-2",
            "image_aspect_ratio": "3:4",
            "image_resolution": "2K",
            "manga_derive_preset_id": "plot_manga_fusion_bw",
        }.items():
            s.add(Setting(key=k, value=v))
        # 默认账号
        s.add(ProviderAccount(provider_code="deepseek", base_url="https://api.deepseek.com/v1",
                              api_key="mock-ds-key", model="deepseek-chat", valid=True))
        s.add(ProviderAccount(provider_code="grsai", base_url="https://api.grsai.com/v1",
                              api_key="mock-grsai-key", model="nano-banana-2", valid=True))
        s.commit()
    finally:
        s.close()


_bootstrap_seed_data()


@pytest.fixture(autouse=True)
def _patch_output_dir(monkeypatch, tmp_path):
    """所有 e2e 测试的 Output 目录指向 tmp_path。

    既要 patch ``app.config.OUTPUT_DIR``，也要把已经 import 过的
    业务模块里的 ``OUTPUT_DIR`` 别名同步指向新值（否则它们仍是
    import 时绑定的旧 Path）。
    """
    import app.config as _cfg
    import app.services.export as _exp_svc
    import app.services.image_generation as _img_svc
    import app.services.image_derive_service as _ds
    import app.routers.export as _exp_rt
    import app.routers.image_generation as _img_rt
    import app.routers.image_derive as _ds_rt
    import app.routers.images as _img_rt2

    old = _cfg.OUTPUT_DIR
    _cfg.OUTPUT_DIR = tmp_path
    for mod in (_exp_svc, _img_svc, _ds,
                _exp_rt, _img_rt, _ds_rt, _img_rt2):
        if hasattr(mod, "OUTPUT_DIR"):
            mod.OUTPUT_DIR = tmp_path
    try:
        yield
    finally:
        _cfg.OUTPUT_DIR = old


@pytest.fixture(autouse=True)
def _disable_startup_create_all():
    """阻止 ``@app.on_event("startup")`` 走模块级 engine 真实建表（污染主库）。

    方案：把 ``app.database.engine`` 临时指向 ``_PRE_ENGINE``，让 startup 的
    ``Base.metadata.create_all(app.database.engine)`` 实际作用在我们的
    in-memory 库上（幂等操作，无害）。其它测试文件用自己临时创建的
    engine + ``Base.metadata.create_all(engine)`` 完全不受影响。
    """
    import app.database as _app_db
    orig_engine = _app_db.engine
    _app_db.engine = _PRE_ENGINE
    try:
        yield
    finally:
        _app_db.engine = orig_engine


@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """拦截所有 LLM.chat 调用，按 stage 返回不同 mock 输出。"""
    import json
    from app.adapters import llm as llm_adapter
    from app.services import role_service as rs
    from app.services import script_service as ss
    from app.services import image_derive_service as ds

    SAMPLE_NOVEL = (
        "霜降\n\n第一章 山中夜雨\n\n雨水顺着青瓦滴下来，林七蹲在檐下。"
        "远处传来更夫的梆子声，他攥紧手里的短刀。天将亮时，他终于起身。"
        "第2章 南城旧巷\n\n南城的巷子比记忆中更窄。"
        "林七一路问过去，直到他在城西的一口枯井旁看见了一个穿灰袍的老人。"
    )
    MOCK_ROLE_JSON = json.dumps(
        [
            {"name": "林七", "content": "一个18岁的少年剑客，短刀不离身，眼神锐利"},
            {"name": "灰袍老人", "content": "一个60多岁的神秘老人，住在南城枯井旁"},
        ],
        ensure_ascii=False,
    )
    MOCK_STORYBOARD = (
        "以下是分镜：\n"
        "1. 林七蹲在屋檐下，雨水从青瓦滴落，攥着短刀沉思。\n"
        "2. 远景：夜色中传来更夫敲梆子的声音，林七抬头望去。\n"
        "3. 林七起身走入晨雾中，背景是远山与古道。\n"
        "4. 南城旧巷：林七在窄巷中穿行，墙上爬满青苔。\n"
        "5. 林七走到枯井旁，与灰袍老人四目相对，老人开口说话。\n"
    )
    MOCK_SUMMARY = "少年剑客林七为完成师父遗愿，独闯南城寻找老槐树，在旧巷偶遇灰袍老人。"
    MOCK_IMAGE_PROMPT = (
        "顶级韩漫风格，融合精致日系2D插画美学，多格构图：第1格林七蹲在青瓦屋檐下，"
        "雨水滴落特写；第2格中景，林七攥紧短刀沉思。电影级光影，高对比度。\n\n"
        "本镜采用双格横条版式：左格人物特写、右格环境描写，"
        "阅读动线横向推进；色彩冷蓝调，旁白框白底黑边。\n\n"
        "禁止：水印、低分辨率、变形肢体、模糊。"
    )

    def fake_chat(db, prompt, provider_code=None, model=None, **kwargs):
        if "分镜" in prompt or "短句" in prompt or "分镜拆分" in prompt:
            return MOCK_STORYBOARD
        if "梗概" in prompt or "摘要" in prompt:
            return MOCK_SUMMARY
        if "三段" in prompt or "画风与多格" in prompt or "本镜内容" in prompt:
            return MOCK_IMAGE_PROMPT
        if "人物" in prompt or "角色" in prompt:
            return MOCK_ROLE_JSON
        return MOCK_SUMMARY

    monkeypatch.setattr(llm_adapter, "chat", fake_chat, raising=True)
    monkeypatch.setattr(rs, "chat", fake_chat, raising=True)
    monkeypatch.setattr(ss, "chat", fake_chat, raising=True)
    monkeypatch.setattr(ds, "chat", fake_chat, raising=True)
    yield


@pytest.fixture(autouse=True)
def _mock_image_provider(monkeypatch):
    """拦截生图适配器：不联网，落盘一张小 PNG。"""
    from PIL import Image
    from app.services import image_generation as img_svc

    counter = {"n": 0}

    def fake_generate_image(self, prompt, model="nano-banana-2", aspect_ratio="3:4",
                            resolution="2K", output_dir=None):
        counter["n"] += 1
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            from pathlib import Path
            fp = output_dir / f"mock_{counter['n']}.png"
            Image.new("RGB", (60, 80), color=(123, 200, 80)).save(fp)
            return {"image_url": str(fp), "generation_time": 0.1}
        return {"image_url": f"https://mock.local/{counter['n']}.png", "generation_time": 0.1}

    monkeypatch.setattr(img_svc.ImageProviderAdapter, "generate_image", fake_generate_image)
    yield
