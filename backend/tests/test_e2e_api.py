# -*- coding: utf-8 -*-
"""catong_gen 端到端 API 自动化测试（★ 流程测试文档配套脚本）。

测试范围：完整跑通「小说 → 角色 → 项目分镜 → 图片提示词 → 出图 → 导出」全链路。
执行方式（无需任何外部 API Key）：

    cd backend
    pytest -v tests/test_e2e_api.py

策略：
- 共享 conftest.py 已经把 ``app.database.engine`` 切到 in-memory SQLite，
  LLM/生图适配器均 monkeypatch，Output 目录指到 tmp_path
- 走 FastAPI ``TestClient`` 在内存里跑完整 HTTP 路由
- 跑完完整链路并断言主图/导出文件实际生成
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

# 重要：test_e2e_full_flow.py 会复用本文件的常量
SAMPLE_NOVEL = (
    "霜降\n\n"
    "第一章 山中夜雨\n\n"
    "雨水顺着青瓦滴下来，林七蹲在檐下，眼神像被火烤过。"
    "远处传来更夫的梆子声，他攥紧手里的短刀，"
    "心里反复念着师父临终那句话：'此去南城，替我看看那棵老槐树。'\n\n"
    "天将亮时，他终于起身。"
    "第2章 南城旧巷\n\n"
    "南城的巷子比记忆中更窄。青石板上的苔藓踩上去滑得很。"
    "林七一路问过去，'老槐树'三个字被无数人摇头，"
    "直到他在城西的一口枯井旁看见了一个穿灰袍的老人。"
    "老人抬头看他，'你来了。'\n"
)

SAMPLE_NOVEL_TEXT = SAMPLE_NOVEL  # 别名，兼容旧代码

MOCK_STORYBOARD = (
    "以下是分镜：\n"
    "1. 林七蹲在屋檐下，雨水从青瓦滴落，攥着短刀沉思。\n"
    "2. 远景：夜色中传来更夫敲梆子的声音，林七抬头望去。\n"
    "3. 林七起身走入晨雾中，背景是远山与古道。\n"
    "4. 南城旧巷：林七在窄巷中穿行，墙上爬满青苔。\n"
    "5. 林七走到枯井旁，与灰袍老人四目相对，老人开口说话。\n"
)

# conftest 已经处理了所有 autouse mock；这里只暴露共享数据


# ---------------------------------------------------------------- 公共 fixture

# 注意：以下 import 必须在 conftest 之后
from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _pre_session():
    """从 conftest 暴露 in-memory SessionLocal 工厂。"""
    from tests.conftest import _PRE_SESSION
    return _PRE_SESSION


@pytest.fixture()
def e2e_session_factory(_pre_session):
    """别名 fixture，兼容历史用法。"""
    return _pre_session


@pytest.fixture(autouse=True)
def _clean_per_test(_pre_session):
    """每用例前清空业务表 + ProviderAccount（保留提示词五件套 / 分类标签 / 默认 settings）。"""
    from app.models.novel import Novel, NovelFile
    from app.models.role import Role, RoleTag
    from app.models.project import Project, Script
    from app.models.image import ImageTask
    from app.models.export import ExportTask
    from app.models.prompt import PromptRenderLog
    from app.models.art_style import ArtStyle
    from app.models.provider import ProviderAccount

    s = _pre_session()
    try:
        for model in (ImageTask, ExportTask, Script, Project, RoleTag, Role,
                      NovelFile, Novel, PromptRenderLog, ArtStyle, ProviderAccount):
            try:
                s.query(model).delete()
            except Exception:
                s.rollback()
        s.commit()
    finally:
        s.close()
    yield


@pytest.fixture()
def db_session(_pre_session) -> Iterator:
    """每次用例一个干净 session。"""
    s = _pre_session()
    try:
        yield s
    finally:
        s.close()


# ============================================================== 业务用例


class TestHealthAndSettings:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["app"] == "catong_gen"

    def test_settings_round_trip(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 200
        assert r.json()["llm_default_provider"] == "deepseek"

        r = client.put("/api/settings", json={"key": "image_aspect_ratio", "value": "1:1"})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

        r = client.get("/api/settings")
        assert r.json()["image_aspect_ratio"] == "1:1"

    def test_provider_accounts_list(self, client, seed_basics):
        r = client.get("/api/provider-accounts")
        assert r.status_code == 200
        codes = {x["provider_code"] for x in r.json()["items"]}
        assert {"deepseek", "grsai"} <= codes


class TestPromptAndAssembler:
    def test_assemble_stages(self, client):
        r = client.get("/api/assemble/stages")
        assert r.status_code == 200
        stages = r.json()
        for s in ("role_derive", "storyboard_short", "image_derive", "summary"):
            assert s in stages

    def test_render_logs_pagination(self, client):
        r = client.get("/api/render-logs")
        assert r.status_code == 200
        assert "items" in r.json()


class TestNovelFlow:
    def test_create_and_clean(self, client):
        r = client.post("/api/novels", json={"name": "霜降", "text": SAMPLE_NOVEL_TEXT})
        assert r.status_code == 201, r.text
        novel_id = r.json()["id"]

        r = client.get("/api/novels/detail", params={"novel_id": novel_id})
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "霜降"
        assert body["original_text"] == body["content"]

        r = client.post(
            "/api/novels/clean",
            params={"novel_id": novel_id},
            json={"rules": ["format", "serial", "punct"], "apply": False},
        )
        assert r.status_code == 200, r.text
        preview = r.json()
        assert preview["applied"] is False
        assert "diff" in preview
        assert "counts" in preview

        r = client.post(
            "/api/novels/clean",
            params={"novel_id": novel_id},
            json={"rules": ["format", "serial", "punct", "speech_quote"], "apply": True},
        )
        assert r.status_code == 200
        applied = r.json()
        assert applied["applied"] is True
        assert applied["is_format_cleaned"] is True
        assert applied["is_serial_cleaned"] is True
        assert applied["is_punct_cleaned"] is True

        r = client.get("/api/novels/detail", params={"novel_id": novel_id})
        body = r.json()
        assert all(body[k] for k in ("is_format_cleaned", "is_serial_cleaned", "is_punct_cleaned"))
        assert body["original_text"] == SAMPLE_NOVEL_TEXT  # 原文保留

    def test_import_txt(self, client, tmp_path):
        fp = tmp_path / "sample.txt"
        fp.write_text(SAMPLE_NOVEL_TEXT, encoding="utf-8")
        with fp.open("rb") as f:
            r = client.post("/api/novels/import-txt", files={"file": ("sample.txt", f, "text/plain")})
        assert r.status_code == 201
        assert r.json()["name"]


class TestRoleFlow:
    def test_derive_and_list(self, client):
        r = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT})
        novel_id = r.json()["id"]

        r = client.post("/api/roles/derive", json={
            "novel_id": novel_id,
            "preset_id": "role_derive_vip",
            "replace_existing": True,
        })
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["count"] >= 1
        assert "log_id" in out

        r = client.get("/api/roles", params={"novel_id": novel_id})
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) >= 1
        names = {x["name"] for x in items}
        assert "林七" in names

        role_id = items[0]["id"]
        r = client.put(
            "/api/roles/tags",
            params={"role_id": role_id},
            json=[{"category": "类型", "value": "角色"}],
        )
        assert r.status_code == 200
        assert r.json()["count"] == 1


class TestProjectFlow:
    def test_create_split_summary(self, client):
        r = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT})
        novel_id = r.json()["id"]

        r = client.post("/api/projects", json={
            "name": "霜降-条漫", "novel_id": novel_id, "mode": "manga",
            "derive_preset_id": "plot_manga_fusion_bw",
        })
        assert r.status_code == 201
        project_id = r.json()["id"]

        r = client.post(
            "/api/projects/summary",
            params={"project_id": project_id},
            json={"max_words": 200},
        )
        assert r.status_code == 200, r.text
        assert "summary" in r.json()

        r = client.post(
            "/api/projects/split",
            params={"project_id": project_id},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        assert r.status_code == 200
        out = r.json()
        assert out["count"] >= 3

        r = client.get("/api/projects/scripts", params={"project_id": project_id})
        scripts = r.json()["items"]
        assert len(scripts) >= 3

        order = [s["id"] for s in scripts]
        order.reverse()
        r = client.put(
            "/api/projects/scripts/reorder",
            params={"project_id": project_id},
            json={"order": order},
        )
        assert r.status_code == 200

    def test_update_script_marks_prompt_touched(self, client):
        r = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT})
        novel_id = r.json()["id"]
        r = client.post("/api/projects", json={"name": "p", "novel_id": novel_id})
        project_id = r.json()["id"]
        r = client.post(
            "/api/projects/split",
            params={"project_id": project_id},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        sid = client.get("/api/projects/scripts", params={"project_id": project_id}).json()["items"][0]["id"]

        r = client.put(
            "/api/projects/scripts/detail",
            params={"script_id": sid},
            json={"content": "改写镜头", "image_prompt": "手工提示词", "video_prompt": "", "screen_prompt": "",
                  "main_image": "", "candidate_images": "{}", "selected_candidate": None, "reference_image": "",
                  "notes": "", "is_main_locked": False, "generation_enabled": True, "duration": None, "extra": "{}",
                  "prompt_touched": False},
        )
        assert r.status_code == 200

        s = client.get("/api/projects/scripts/detail", params={"script_id": sid}).json()
        assert s["image_prompt"] == "手工提示词"
        assert s["prompt_touched"] is True


class TestImageDeriveFlow:
    def test_derive_and_batch(self, client):
        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        client.post(
            "/api/projects/split",
            params={"project_id": pid},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        scripts = client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]
        sids = [s["id"] for s in scripts]

        r = client.post(f"/api/image-derive/scripts/{sids[0]}", json={})
        assert r.status_code == 200, r.text
        out = r.json()
        assert "image_prompt" in out and out["image_prompt"]
        assert out["render_log_id"] > 0

        r = client.post(f"/api/image-derive/projects/{pid}/batch", json={})
        assert r.status_code == 200
        summary = r.json()
        assert summary["total"] == len(scripts)
        assert summary["success"] >= 1

        scripts_after = client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]
        filled = [s for s in scripts_after if s["image_prompt"]]
        assert len(filled) >= 1

    def test_assembler_dry_run_no_llm(self, client):
        """拼装引擎独立 dry-run：必须不调 LLM，且返回分段 + 全文。"""
        r = client.post("/api/assemble/preview", json={
            "stage": "image_derive",
            "preset_id": "plot_manga_fusion_bw",
            "variables": {"shot_content": "林七蹲在屋檐下", "style_prefix": "韩漫，"},
            "persist_log": False,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["stage"] == "image_derive"
        assert any(seg["key"] == "negative" for seg in body["segments"])
        assert "林七蹲在屋檐下" in body["rendered"]


class TestImageGenerationFlow:
    def test_generate_and_select_main(self, client):
        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        client.post(
            "/api/projects/split",
            params={"project_id": pid},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        scripts = client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]
        sid = scripts[0]["id"]

        client.post(f"/api/image-derive/scripts/{sid}", json={})

        r = client.post("/api/image-generation/generate", json={
            "script_id": sid, "provider_code": "grsai", "model": "nano-banana-2",
            "aspect_ratio": "3:4", "resolution": "2K",
        })
        assert r.status_code == 200, r.text
        gen1 = r.json()
        assert gen1["status"] == "done"
        assert gen1["image_url"]
        task1 = gen1["task_id"]

        r = client.post("/api/image-generation/generate", json={"script_id": sid})
        assert r.status_code == 200
        gen2 = r.json()
        task2 = gen2["task_id"]

        r = client.get(f"/api/image-generation/candidates/{sid}")
        assert r.status_code == 200
        cands = r.json()
        assert len(cands) == 2

        r = client.post("/api/image-generation/select-main", json={
            "script_id": sid, "task_id": task2,
        })
        assert r.status_code == 200
        assert r.json()["main_image"] == gen2["image_url"]

        s = client.get("/api/projects/scripts/detail", params={"script_id": sid}).json()
        assert s["main_image"] == gen2["image_url"]
        assert s["selected_candidate"] == task2

    def test_task_list_and_get(self, client):
        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        client.post(
            "/api/projects/split",
            params={"project_id": pid},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        sid = client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"][0]["id"]
        client.post(f"/api/image-derive/scripts/{sid}", json={})
        r = client.post("/api/image-generation/generate", json={"script_id": sid})
        tid = r.json()["task_id"]

        r = client.get(f"/api/image-generation/tasks/{tid}")
        assert r.status_code == 200
        assert r.json()["status"] == "done"

        r = client.get("/api/image-generation/tasks", params={"script_id": sid})
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestExportFlow:
    def test_full_export_chain(self, client, tmp_path):
        # 1) 准备
        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        client.post(
            "/api/projects/split",
            params={"project_id": pid},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        scripts = client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]

        for s in scripts[:2]:
            client.post(f"/api/image-derive/scripts/{s['id']}", json={})
            client.post("/api/image-generation/generate", json={"script_id": s["id"]})

        r = client.get(f"/api/export/info/{pid}")
        assert r.status_code == 200
        info = r.json()
        assert info["can_export"] is True
        assert info["scripts_with_images"] >= 2

        r = client.post("/api/export/create", json={
            "project_id": pid, "export_style": "vertical",
            "page_numbers": True, "titles": False, "quality": 90,
        })
        assert r.status_code == 200, r.text
        task = r.json()
        assert task["status"] == "done"
        assert task["file_size"] > 0
        eid = task["id"]

        out_file = tmp_path / task["output_path"]
        assert out_file.exists()
        assert out_file.stat().st_size > 0

        r = client.get(f"/api/export/download/{eid}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/jpeg")
        assert len(r.content) > 0

        r = client.post(f"/api/export/zip/{pid}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert len(r.content) > 0

    def test_export_blocked_without_images(self, client):
        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        client.post(
            "/api/projects/split",
            params={"project_id": pid},
            json={"preset_id": "storyboard_short_v1", "replace_existing": True},
        )
        r = client.get(f"/api/export/info/{pid}")
        assert r.json()["can_export"] is False


class TestArtStyleFlow:
    def test_create_bind_get(self, client):
        r = client.post("/api/art-styles", json={
            "code": "e2e_h2", "name": "E2E韩漫",
            "prefix": "韩漫顶级", "suffix": "，光影佳",
            "negative_prompt": "禁水印",
            "recommended_model": "nano-banana-2",
            "recommended_aspect_ratio": "3:4", "recommended_resolution": "2K",
        })
        assert r.status_code == 201, r.text
        style_id = r.json()["id"]

        r = client.get("/api/art-styles")
        assert r.status_code == 200
        codes = {x["code"] for x in r.json()}
        assert "e2e_h2" in codes

        nid = client.post("/api/novels", json={"text": SAMPLE_NOVEL_TEXT}).json()["id"]
        pid = client.post("/api/projects", json={"name": "p", "novel_id": nid}).json()["id"]
        r = client.post("/api/art-styles/bind", json={
            "project_id": pid, "style_id": style_id,
        })
        assert r.status_code == 200
        assert r.json()["style_id"] == style_id

        r = client.get(f"/api/art-styles/project/{pid}")
        assert r.status_code == 200
        assert r.json()["id"] == style_id


# ============================================================== Seed 兼容性


def test_seed_runs_clean():
    """验证 seed.seed_all() 在 in-memory 引擎上是幂等的。"""
    from app.seeds import seed as seed_mod
    from app.database import Base
    from tests.conftest import _PRE_ENGINE, _PRE_SESSION

    seed_mod.engine = _PRE_ENGINE
    seed_mod.Base = Base
    seed_mod.SessionLocal = _PRE_SESSION

    stats = seed_mod.seed_all(verbose=False)
    assert stats["prompts"] == 0
    assert stats["templates"] == 0
    assert stats["presets"] == 0

    from app.models.prompt import PromptPreset
    s = _PRE_SESSION()
    try:
        assert s.query(PromptPreset).count() >= 8
    finally:
        s.close()
