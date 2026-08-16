# -*- coding: utf-8 -*-
"""catong_gen 端到端「全程跑通」冒烟测试（高层封装）。

把整套「小说 → 角色 → 项目分镜 → 图片 prompt → 出图 → 导出」压缩到
**一个用例** 里跑，每步打印阶段标题和断言摘要，失败时给出上下文。

跑法::

    pytest -v -s tests/test_e2e_full_flow.py

适用场景：
- 升级依赖或 ORM 后快速回归；
- CI 中作为「冒烟门禁」单点失败即报警；
- 新人按阶段顺序阅读代码时的可执行文档。
"""
from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _phase(title: str):
    """打印阶段标题，方便 -s 输出。"""
    bar = "=" * 60
    print(f"\n{bar}\n>>> {title}\n{bar}")


def _ok(msg: str):
    print(f"  ✓ {msg}")


@pytest.fixture()
def full_client() -> TestClient:
    """完整流程客户端（conftest 已处理 mock）。"""
    return TestClient(app)


def test_phase_0_to_8_in_one_shot(full_client, seed_basics):
    """Phase 0 → 8 一次跑通。"""
    overall_t = time.time()
    timings: dict[str, float] = {}

    def _timed(label, fn):
        t0 = time.time()
        result = fn()
        timings[label] = time.time() - t0
        return result

    # ============================ Phase 0/1 ============================
    _phase("Phase 0/1 — 环境与提示词体系（seed 已在 import 阶段完成）")
    r = full_client.get("/api/health")
    assert r.status_code == 200
    _ok(f"/api/health → {r.json()['app']} v{r.json()['version']}")

    r = full_client.get("/api/prompt-presets")
    assert r.status_code == 200
    presets = r.json()
    _ok(f"/api/prompt-presets → {len(presets)} 个预设（期望 8）")
    assert len(presets) == 8

    r = full_client.get("/api/assemble/stages")
    assert r.status_code == 200
    _ok(f"/api/assemble/stages → {len(r.json())} 个阶段")

    # ============================ Phase 2 ============================
    _phase("Phase 2 — 小说中心（导入 + 清洗）")
    from tests.test_e2e_api import SAMPLE_NOVEL
    nid = _timed("create_novel", lambda: full_client.post(
        "/api/novels", json={"name": "端到端-霜降", "text": SAMPLE_NOVEL}
    ).json()["id"])
    _ok(f"POST /api/novels → NOVEL_ID={nid}")

    r = _timed("clean_novel", lambda: full_client.post(
        "/api/novels/clean",
        params={"novel_id": nid},
        json={"rules": ["format", "serial", "punct", "speech_quote"], "apply": True},
    ))
    assert r.status_code == 200 and r.json()["applied"] is True
    _ok("POST /api/novels/clean → 4 规则已应用，is_*_cleaned 全 True")

    # ============================ Phase 3 ============================
    _phase("Phase 3 — 角色中心（AI 推导）")
    r = _timed("derive_roles", lambda: full_client.post("/api/roles/derive", json={
        "novel_id": nid, "preset_id": "role_derive_vip", "replace_existing": True,
    }))
    assert r.status_code == 200, r.text
    n_roles = r.json()["count"]
    _ok(f"POST /api/roles/derive → {n_roles} 个角色 (log_id={r.json()['log_id']})")
    assert n_roles >= 2

    role_ids = [r["id"] for r in full_client.get(
        "/api/roles", params={"novel_id": nid}
    ).json()["items"]]
    _ok(f"GET /api/roles → role_ids={role_ids}")

    # ============================ Phase 4 ============================
    _phase("Phase 4 — 项目与分镜（建项目 + 拆镜）")
    pid = _timed("create_project", lambda: full_client.post("/api/projects", json={
        "name": "端到端-条漫", "novel_id": nid, "mode": "manga",
        "derive_preset_id": "plot_manga_fusion_bw",
    }).json()["id"])
    _ok(f"POST /api/projects → PROJECT_ID={pid}")

    _timed("summary", lambda: full_client.post(
        "/api/projects/summary", params={"project_id": pid}, json={"max_words": 200},
    ))
    p = full_client.get("/api/projects/detail", params={"project_id": pid}).json()
    _ok(f"POST /api/projects/summary → 已写入 project.summary ({len(p['summary'])} 字)")

    r = _timed("split", lambda: full_client.post(
        "/api/projects/split", params={"project_id": pid},
        json={"preset_id": "storyboard_short_v1", "replace_existing": True},
    ))
    n_shots = r.json()["count"]
    _ok(f"POST /api/projects/split → {n_shots} 个分镜")
    assert n_shots >= 3

    scripts = full_client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]
    sids = [s["id"] for s in scripts]
    _ok(f"GET /api/projects/scripts → SCRIPT_IDS={sids}")

    # ============================ Phase 5 ============================
    _phase("Phase 5 — 图片提示词推导（批量）")
    r = _timed("derive_batch", lambda: full_client.post(
        f"/api/image-derive/projects/{pid}/batch", json={},
    ))
    assert r.status_code == 200, r.text
    summary = r.json()
    _ok(f"POST /api/image-derive/projects/{{}}/batch → "
        f"total={summary['total']}, success={summary['success']}, failed={summary['failed']}")
    assert summary["success"] >= 1

    after = full_client.get("/api/projects/scripts", params={"project_id": pid}).json()["items"]
    filled = sum(1 for s in after if s["image_prompt"])
    _ok(f"image_prompt 填充率: {filled}/{len(after)}")

    # ============================ Phase 6 ============================
    _phase("Phase 6 — 图片生成（生图 + 选主图）")
    task_ids = []
    for sid in sids:
        r = full_client.post("/api/image-generation/generate", json={
            "script_id": sid, "provider_code": "grsai",
            "model": "nano-banana-2", "aspect_ratio": "3:4", "resolution": "2K",
        })
        assert r.status_code == 200, r.text
        task_ids.append(r.json()["task_id"])
    _ok(f"已生 {len(task_ids)} 张图，task_ids={task_ids}")

    r = full_client.post("/api/image-generation/generate", json={"script_id": sids[0]})
    assert r.status_code == 200
    new_task = r.json()["task_id"]
    r = full_client.post("/api/image-generation/select-main", json={
        "script_id": sids[0], "task_id": new_task,
    })
    assert r.status_code == 200
    _ok(f"select-main → script[{sids[0]}] 主图已切到 task={new_task}")

    # ============================ Phase 7 ============================
    _phase("Phase 7 — 条漫导出（长图 + ZIP）")
    r = full_client.get(f"/api/export/info/{pid}")
    assert r.status_code == 200 and r.json()["can_export"] is True
    _ok(f"GET /api/export/info/{{}} → can_export={r.json()['can_export']}, "
        f"scripts_with_images={r.json()['scripts_with_images']}")

    r = _timed("export", lambda: full_client.post("/api/export/create", json={
        "project_id": pid, "export_style": "vertical",
        "page_numbers": True, "titles": False, "quality": 90,
    }))
    assert r.status_code == 200, r.text
    et = r.json()
    assert et["status"] == "done" and et["file_size"] > 0
    eid = et["id"]
    _ok(f"POST /api/export/create → task_id={eid}, size={et['file_size']}B")

    r = full_client.get(f"/api/export/download/{eid}")
    assert r.status_code == 200 and len(r.content) > 0
    _ok(f"GET /api/export/download/{{}} → {len(r.content)}B JPEG")

    r = full_client.post(f"/api/export/zip/{pid}")
    assert r.status_code == 200 and len(r.content) > 0
    _ok(f"POST /api/export/zip/{{}} → {len(r.content)}B ZIP")

    # ============================ Phase 8 ============================
    _phase("Phase 8 — 画风库（CRUD + 绑定）")
    r = full_client.post("/api/art-styles", json={
        "code": "e2e_h2_v1", "name": "端到端韩漫",
        "prefix": "顶级韩漫，", "suffix": "，电影级光影",
        "recommended_model": "nano-banana-2",
        "recommended_aspect_ratio": "3:4", "recommended_resolution": "2K",
    })
    assert r.status_code == 201, r.text
    style_id = r.json()["id"]
    _ok(f"POST /api/art-styles → style_id={style_id}")

    r = full_client.post("/api/art-styles/bind", json={
        "project_id": pid, "style_id": style_id,
    })
    assert r.status_code == 200
    _ok(f"POST /api/art-styles/bind → project[{pid}] 已绑 style[{style_id}]")

    r = full_client.get(f"/api/art-styles/project/{pid}")
    assert r.status_code == 200 and r.json()["id"] == style_id
    _ok("GET /api/art-styles/project/{{}} → 反查通过")

    # ============================ 收尾 ============================
    _phase("总览")
    total = time.time() - overall_t
    _ok(f"全部阶段耗时 {total:.2f}s")
    for label, sec in timings.items():
        print(f"    · {label:>16}: {sec:.3f}s")
    print("=" * 60)
