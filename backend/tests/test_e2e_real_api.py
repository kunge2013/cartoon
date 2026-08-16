# [AGC:FILE] tool=Cc author=fangkun date=2026-08-16
# -*- coding: utf-8 -*-
"""catong_gen 全流程真实 API 端到端测试（不使用 mock）。

测试范围：完整跑通「小说 -> 角色推导 -> 项目分镜 -> 图片提示词 -> 出图 -> 导出连环画」
全链路，所有 LLM 和图像生成均调用真实 API。

================================================================================
快速开始
================================================================================

1. 配置 API Key 和 URL（环境变量）：

   Windows PowerShell（推荐）:
     $env:CATONG_TEST_LLM_PROVIDER="deepseek"
     $env:CATONG_TEST_LLM_API_KEY="sk-你的LLM密钥"
     $env:CATONG_TEST_LLM_BASE_URL="https://api.deepseek.com/v1"
     $env:CATONG_TEST_LLM_MODEL="deepseek-chat"
     $env:CATONG_TEST_IMAGE_API_KEY="sk-你的图像密钥"
     $env:CATONG_TEST_IMAGE_BASE_URL="https://api.grsai.com/v1"

   Windows CMD:
     set CATONG_TEST_LLM_PROVIDER=deepseek
     set CATONG_TEST_LLM_API_KEY=sk-你的LLM密钥
     set CATONG_TEST_LLM_BASE_URL=https://api.deepseek.com/v1
     set CATONG_TEST_LLM_MODEL=deepseek-chat
     set CATONG_TEST_IMAGE_API_KEY=sk-你的图像密钥
     set CATONG_TEST_IMAGE_BASE_URL=https://api.grsai.com/v1

   Linux / macOS:
     export CATONG_TEST_LLM_PROVIDER=deepseek
     export CATONG_TEST_LLM_API_KEY=sk-你的LLM密钥
     export CATONG_TEST_LLM_BASE_URL=https://api.deepseek.com/v1
     export CATONG_TEST_LLM_MODEL=deepseek-chat
     export CATONG_TEST_IMAGE_API_KEY=sk-你的图像密钥
     export CATONG_TEST_IMAGE_BASE_URL=https://api.grsai.com/v1

2. 运行测试：

   cd backend
   pytest -v -s tests/test_e2e_real_api.py

================================================================================
环境变量配置说明
================================================================================

必需：
  CATONG_TEST_LLM_API_KEY
      LLM API Key，用于角色推导 / 分镜拆分 / 摘要 / 图片提示词
      根据 CATONG_TEST_LLM_PROVIDER 的不同，对应不同供应商的密钥

  CATONG_TEST_IMAGE_API_KEY
      图像生成 API Key，用于出图
      根据 CATONG_TEST_IMAGE_PROVIDER 的不同，对应不同供应商的密钥

可选 — LLM 配置：
  CATONG_TEST_LLM_PROVIDER
      LLM 供应商代码，默认 deepseek
      可选值: deepseek / grsai / volcengine

  CATONG_TEST_LLM_BASE_URL
      LLM API 的 Base URL，根据 provider 有不同默认值：
        deepseek:   https://api.deepseek.com/v1
        grsai:      https://api.grsai.com/v1
        volcengine: https://ark.cn-beijing.volces.com/api/v3
      如果使用代理或自建网关，修改此变量

  CATONG_TEST_LLM_MODEL
      LLM 模型名，根据 provider 有不同默认值：
        deepseek:   deepseek-chat
        grsai:      deepseek-chat
        volcengine: doubao-pro-32k

可选 — 图像生成配置：
  CATONG_TEST_IMAGE_PROVIDER
      图像供应商代码，默认 grsai

  CATONG_TEST_IMAGE_BASE_URL
      图像 API 的 Base URL，默认 https://api.grsai.com/v1
      如果使用代理或自建网关，修改此变量
      实际请求端点: {BASE_URL}/images/generations

  CATONG_TEST_IMAGE_MODEL
      图像模型，默认 nano-banana-2

  CATONG_TEST_IMAGE_ASPECT_RATIO
      图像宽高比，默认 3:4

  CATONG_TEST_IMAGE_RESOLUTION
      图像分辨率，默认 2K

  CATONG_TEST_MAX_SHOTS
      生成图片的最大分镜数，默认 3（控制测试耗时和 API 费用）

================================================================================
各供应商 URL 和模型参考
================================================================================

  DeepSeek:
    Base URL: https://api.deepseek.com/v1
    LLM 模型: deepseek-chat, deepseek-reasoner
    密钥获取: https://platform.deepseek.com/

  GRS AI:
    Base URL: https://api.grsai.com/v1
    LLM 模型: deepseek-chat（兼容 OpenAI 协议）
    图像模型: nano-banana-2
    密钥获取: https://www.grsai.com/

  火山引擎 (Volcengine):
    Base URL: https://ark.cn-beijing.volces.com/api/v3
    LLM 模型: doubao-pro-32k, doubao-pro-128k 等（需在方舟控制台创建接入点）
    密钥获取: https://console.volcengine.com/ark

================================================================================
注意事项
================================================================================

- 本测试会产生真实 API 调用费用
- 图像生成可能较慢（每张约 10-60 秒），请耐心等待
- 测试使用独立的临时数据库，不会污染生产数据
- 生成的图片保存在系统临时目录，测试结束后自动清理
- 如果 API 返回远程图片 URL，测试会自动下载到本地用于拼接导出
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import pytest
from fastapi.testclient import TestClient

# ============================================================================
# 在 conftest mock fixture 生效前，保存原始函数引用
# ============================================================================
# conftest.py 的 autouse fixture 会在每个测试运行前 monkeypatch 这些函数，
# 我们在模块导入时（fixture 执行前）保存原始引用，以便在测试中恢复。
from app.adapters import llm as _llm_mod  # noqa: E402
from app.services import role_service as _rs_mod  # noqa: E402
from app.services import script_service as _ss_mod  # noqa: E402
from app.services import image_derive_service as _ds_mod  # noqa: E402
from app.services.image_generation import ImageProviderAdapter as _ImgAdapter  # noqa: E402

_ORIGINAL_CHAT = _llm_mod.chat
_ORIGINAL_GENERATE_IMAGE = _ImgAdapter.generate_image

# ============================================================================
# 各供应商默认 URL 和模型
# ============================================================================
_PROVIDER_DEFAULTS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
    },
    "grsai": {
        "base_url": "https://api.grsai.com/v1",
        "model": "deepseek-chat",
    },
    "volcengine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-pro-32k",
    },
}

# ============================================================================
# 读取环境变量配置
# ============================================================================
# LLM 配置（通用变量优先，兼容旧变量名）
_LLM_PROVIDER = os.environ.get("CATONG_TEST_LLM_PROVIDER", "deepseek").lower()
_llm_defaults = _PROVIDER_DEFAULTS.get(_LLM_PROVIDER, _PROVIDER_DEFAULTS["deepseek"])

_LLM_API_KEY = (
    os.environ.get("CATONG_TEST_LLM_API_KEY", "")
    or os.environ.get("CATONG_TEST_DEEPSEEK_API_KEY", "")  # 向后兼容
)
_LLM_BASE_URL = os.environ.get("CATONG_TEST_LLM_BASE_URL", "") or _llm_defaults["base_url"]
_LLM_MODEL = os.environ.get("CATONG_TEST_LLM_MODEL", "") or _llm_defaults["model"]

# 图像生成配置
_IMAGE_PROVIDER = os.environ.get("CATONG_TEST_IMAGE_PROVIDER", "grsai").lower()
_IMAGE_API_KEY = (
    os.environ.get("CATONG_TEST_IMAGE_API_KEY", "")
    or os.environ.get("CATONG_TEST_GRSAI_API_KEY", "")  # 向后兼容
)
_image_provider_defaults = _PROVIDER_DEFAULTS.get(_IMAGE_PROVIDER, _PROVIDER_DEFAULTS["grsai"])
_IMAGE_BASE_URL = (
    os.environ.get("CATONG_TEST_IMAGE_BASE_URL", "")
    or os.environ.get("CATONG_TEST_GRSAI_BASE_URL", "")  # 向后兼容
    or _image_provider_defaults["base_url"]
)
_IMAGE_MODEL = (
    os.environ.get("CATONG_TEST_IMAGE_MODEL", "")
    or ("nano-banana-2" if _IMAGE_PROVIDER == "grsai" else _image_provider_defaults["model"])
)
_IMAGE_ASPECT_RATIO = os.environ.get("CATONG_TEST_IMAGE_ASPECT_RATIO", "3:4")
_IMAGE_RESOLUTION = os.environ.get("CATONG_TEST_IMAGE_RESOLUTION", "2K")
_MAX_SHOTS = int(os.environ.get("CATONG_TEST_MAX_SHOTS", "3"))

# 判断 API key 是否已配置
_HAS_LLM_KEY = bool(_LLM_API_KEY)
_HAS_IMAGE_KEY = bool(_IMAGE_API_KEY)
_SHOULD_SKIP = not (_HAS_LLM_KEY and _HAS_IMAGE_KEY)
_SKIP_REASON = (
    "需要配置环境变量:\n"
    "  CATONG_TEST_LLM_API_KEY    - LLM API 密钥\n"
    "  CATONG_TEST_IMAGE_API_KEY  - 图像生成 API 密钥\n"
    "详细说明请查看测试文件头部的文档字符串。"
)

# ============================================================================
# 测试用小说文本（足够丰富，能推导出多个角色和分镜）
# ============================================================================
SAMPLE_NOVEL = (
    "夜归人\n\n"
    "第一章 渡口\n\n"
    "暮色像一块灰色的布，慢慢盖住了青牛镇的渡口。"
    "沈砚之坐在老槐树下的石墩上，手里攥着一封皱巴巴的信。"
    "信是三天前到的，上面只有八个字：'速归，师门有难。'\n\n"
    "他穿着一件洗得发白的青衫，腰间挂着一柄没有剑穗的长剑。"
    "剑鞘上有几道深浅不一的划痕，像是被什么利器砍过。"
    "渡船迟迟不来，河面上只有雾气在缓缓流动。\n\n"
    "'你也是在等船？'一个声音从身后传来。\n\n"
    "沈砚之回头，看见一个穿黑色劲装的女子。"
    "她约莫二十出头，眉目英气，背上斜挎着一柄窄刀，"
    "刀鞘上刻着一个小小的'顾'字。\n\n"
    "'嗯。'沈砚之点了点头，下意识地将信收入袖中。\n\n"
    "女子走到他身旁，目光落在他腰间的剑上，微微皱眉："
    "'青云剑？你是天衍宗的人？'\n\n"
    "沈砚之没有回答，只是反问：'你又是谁？'\n\n"
    "'顾长宁。'女子顿了顿，'幽州顾氏。'\n\n"
    "沈砚之心中一凛。幽州顾氏是北地最有名的武林世家，"
    "以刀法和情报网闻名天下。她出现在这里，绝非巧合。\n\n"
    "第二章 夜渡\n\n"
    "渡船终于在月上柳梢时靠岸。撑船的是个佝偻的老人，"
    "一言不发地收了两人的船钱，便撑篙向河心去。\n\n"
    "船至河中央，雾气忽然浓得像牛奶。"
    "顾长宁下意识地握住了刀柄，沈砚之也站起了身。\n\n"
    "水面下传来'咕咚'一声，像是有什么东西沉了下去。"
    "紧接着，渡船猛地一晃，老人不知何时已倒在船尾，"
    "后心插着一支黑色的短箭。\n\n"
    "'小心！'顾长宁翻身跃起，窄刀出鞘，"
    "刀光在雾气中划出一道冷冽的弧线。\n\n"
    "沈砚之拔剑出鞘。青云剑发出一声清越的龙吟，"
    "青色的剑光将周围的雾气逼退了三尺。\n\n"
    "三条黑影从水中跃起，手持短刃直扑二人。"
    "顾长宁刀走轻灵，一刀划开了最前面那人的咽喉。"
    "沈砚之剑势沉稳，青云剑连刺两剑，逼退了另外两人。\n\n"
    "'他们是影阁的人。'顾长宁踢了踢地上的尸体，"
    "'看来天衍宗的事，比我想象的更麻烦。'\n\n"
    "沈砚之收剑入鞘，看着河面上渐渐散去的雾气，"
    "低声道：'不管多麻烦，我都要回去。'\n\n"
    "第三章 山道\n\n"
    "天亮时，两人在十里外的岸边找到了一艘渔船。"
    "船主是个热心的老渔夫，听说他们要去天柱山，"
    "便指了一条偏僻的山道。\n\n"
    "'大路最近不太平，'老渔夫说，"
    "'前天还有官差在查过路的人。你们走山道，虽然远些，但安全。'\n\n"
    "山道蜿蜒在崇山峻岭之间，两旁是参天的古木。"
    "阳光透过树叶洒下来，在地上映出斑驳的光影。"
    "走了大约两个时辰，两人在一处山泉旁歇脚。\n\n"
    "顾长宁用水壶接了泉水，递给沈砚之："
    "'你和天衍宗到底是什么关系？那封信是谁写的？'\n\n"
    "沈砚之沉默了片刻，才说：'写信的是我师父，天衍宗掌门玄清子。"
    "我十年前下山历练，一直没有回去。'\n\n"
    "'那影阁为什么要杀你？'\n\n"
    "'影阁是北地最大的杀手组织，'沈砚之接过水壶喝了一口，"
    "'他们和天衍宗之间的恩怨，可以追溯到二十年前。"
    "但这一次，恐怕不只是旧怨。'\n\n"
    "他顿了顿，从袖中取出那封信，翻到背面。"
    "背面用极小的字写着一行话：'紫玉在掌门手中，速取。'\n\n"
    "顾长宁脸色微变：'紫玉令？传说中能号令天下武林的那块令牌？'\n\n"
    "'正是。'沈砚之将信收好，'如果影阁也在打紫玉令的主意，"
    "那天衍宗现在的处境，比我想象的还要危险。'\n"
)


# ============================================================================
# 辅助函数
# ============================================================================

def _phase(title: str) -> None:
    """打印阶段标题。"""
    bar = "=" * 70
    print(f"\n{bar}\n  {title}\n{bar}")


def _ok(msg: str) -> None:
    """打印成功信息。"""
    print(f"  [OK] {msg}")


def _info(msg: str) -> None:
    """打印信息。"""
    print(f"  [INFO] {msg}")


def _download_url_to_local(url: str, output_dir: Path, filename_prefix: str = "img") -> Optional[str]:
    """下载远程图片到本地，返回本地路径。

    如果图片已经是本地路径则直接返回。
    """
    # 已经是本地路径
    local_path = Path(url)
    if local_path.exists() and local_path.is_file():
        return str(local_path)

    # 尝试下载远程 URL
    if not url.startswith(("http://", "https://")):
        return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        # 从 URL 或时间戳生成文件名
        ext = ".png"
        if "." in url.split("/")[-1]:
            possible_ext = "." + url.split("/")[-1].rsplit(".", 1)[-1].split("?")[0].lower()
            if possible_ext in (".png", ".jpg", ".jpeg", ".webp"):
                ext = possible_ext
        filename = f"{filename_prefix}_{int(time.time() * 1000)}{ext}"
        filepath = output_dir / filename

        _info(f"下载远程图片: {url[:80]}...")
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            filepath.write_bytes(resp.content)

        _ok(f"图片已保存: {filepath} ({len(resp.content)} bytes)")
        return str(filepath)
    except Exception as e:
        print(f"  [WARN] 下载图片失败: {e}")
        return None


# ============================================================================
# Fixture：撤销 conftest 的 mock，使用真实 API
# ============================================================================

@pytest.fixture(autouse=True)
def _real_api(monkeypatch):
    """撤销 conftest.py 中的 LLM 和图像生成 mock，恢复真实 API 调用。

    conftest.py 的 _mock_llm 和 _mock_image_provider 是 autouse fixture，
    会在每个测试前 monkeypatch 关键函数。本 fixture 在它们之后执行，
    将函数恢复为原始实现。
    """
    # 恢复真实的 LLM chat 函数（在所有引用它的模块中）
    monkeypatch.setattr(_llm_mod, "chat", _ORIGINAL_CHAT)
    monkeypatch.setattr(_rs_mod, "chat", _ORIGINAL_CHAT)
    monkeypatch.setattr(_ss_mod, "chat", _ORIGINAL_CHAT)
    monkeypatch.setattr(_ds_mod, "chat", _ORIGINAL_CHAT)

    # 恢复真实的图像生成函数
    monkeypatch.setattr(_ImgAdapter, "generate_image", _ORIGINAL_GENERATE_IMAGE)

    yield


@pytest.fixture(autouse=True)
def _real_provider_accounts(_pre_session):
    """注入真实的 API Key 到 provider_accounts 表。

    替换 conftest seed 数据中的 mock key。
    根据环境变量配置，自动创建 LLM 和图像生成两个供应商账号。
    如果 LLM 和图像使用同一个 provider_code（如都用 grsai），
    则合并为一个账号（使用图像的 base_url 和 model）。
    """
    from app.models.provider import ProviderAccount

    s = _pre_session()
    try:
        # 删除所有现有的 mock 账号
        s.query(ProviderAccount).delete()
        s.commit()

        if _HAS_LLM_KEY and _HAS_IMAGE_KEY:
            # 如果 LLM 和图像使用同一个供应商，合并为一个账号
            if _LLM_PROVIDER == _IMAGE_PROVIDER:
                merged_account = ProviderAccount(
                    provider_code=_LLM_PROVIDER,
                    base_url=_IMAGE_BASE_URL,
                    api_key=_IMAGE_API_KEY,
                    model=_IMAGE_MODEL,
                    valid=True,
                    remark="e2e-real-api-test-merged",
                )
                s.add(merged_account)
            else:
                # LLM 账号
                llm_account = ProviderAccount(
                    provider_code=_LLM_PROVIDER,
                    base_url=_LLM_BASE_URL,
                    api_key=_LLM_API_KEY,
                    model=_LLM_MODEL,
                    valid=True,
                    remark="e2e-real-api-test-llm",
                )
                s.add(llm_account)

                # 图像生成账号
                image_account = ProviderAccount(
                    provider_code=_IMAGE_PROVIDER,
                    base_url=_IMAGE_BASE_URL,
                    api_key=_IMAGE_API_KEY,
                    model=_IMAGE_MODEL,
                    valid=True,
                    remark="e2e-real-api-test-image",
                )
                s.add(image_account)

        s.commit()

        # 打印当前配置（不打印密钥本身）
        if _HAS_LLM_KEY:
            print(f"\n  [CONFIG] LLM: provider={_LLM_PROVIDER}, base_url={_LLM_BASE_URL}, model={_LLM_MODEL}")
        if _HAS_IMAGE_KEY:
            print(f"  [CONFIG] Image: provider={_IMAGE_PROVIDER}, base_url={_IMAGE_BASE_URL}, model={_IMAGE_MODEL}")
            print(f"  [CONFIG] Image: aspect_ratio={_IMAGE_ASPECT_RATIO}, resolution={_IMAGE_RESOLUTION}, max_shots={_MAX_SHOTS}")
    finally:
        s.close()

    yield

    # 测试结束后清理账号（in-memory DB 会自动消失，这里保险起见）
    s = _pre_session()
    try:
        s.query(ProviderAccount).filter(
            ProviderAccount.remark.like("e2e-real-api-test%")
        ).delete(synchronize_session=False)
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _clean_e2e_data(_pre_session):
    """每个测试前清理业务数据，避免数据干扰。"""
    from app.models.novel import Novel, NovelFile
    from app.models.role import Role, RoleTag
    from app.models.project import Project, Script
    from app.models.image import ImageTask
    from app.models.export import ExportTask
    from app.models.prompt import PromptRenderLog
    from app.models.art_style import ArtStyle

    s = _pre_session()
    try:
        for model in (ImageTask, ExportTask, Script, Project, RoleTag, Role,
                      NovelFile, Novel, PromptRenderLog, ArtStyle):
            try:
                s.query(model).delete()
            except Exception:
                s.rollback()
        s.commit()
    finally:
        s.close()
    yield


@pytest.fixture()
def client() -> TestClient:
    """创建 TestClient。"""
    from app.main import app
    with TestClient(app) as c:
        yield c


# ============================================================================
# 全流程测试
# ============================================================================

@pytest.mark.skipif(_SHOULD_SKIP, reason=_SKIP_REASON)
class TestNovelToComicFullFlow:
    """从小说到连环画的完整全流程测试（真实 API，无 mock）。"""

    def test_novel_to_comic_full_flow(self, client: TestClient, tmp_path: Path):
        """完整流程：小说 -> 角色 -> 分镜 -> 图片提示词 -> 出图 -> 导出。

        本测试调用真实的 LLM API 和图像生成 API，验证整个管道的端到端正确性。
        """
        overall_start = time.time()
        timings: dict[str, float] = {}

        def _timed(label: str, fn):
            t0 = time.time()
            result = fn()
            timings[label] = time.time() - t0
            return result

        # ==================================================================
        # Phase 0/1: 健康检查与预设验证
        # ==================================================================
        _phase("Phase 0/1 - 健康检查与提示词预设")

        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        _ok(f"服务健康: {body['app']} v{body['version']}")

        r = client.get("/api/prompt-presets")
        assert r.status_code == 200
        presets = r.json()
        assert len(presets) >= 8
        _ok(f"提示词预设数量: {len(presets)}")

        # 验证供应商账号已配置
        r = client.get("/api/provider-accounts")
        assert r.status_code == 200
        accounts = r.json()["items"]
        provider_codes = {a["provider_code"] for a in accounts}
        _ok(f"已配置供应商: {provider_codes}")
        if _LLM_PROVIDER == _IMAGE_PROVIDER:
            # LLM 和图像使用同一个供应商，只需验证一个账号
            assert _LLM_PROVIDER in provider_codes, (
                f"供应商 {_LLM_PROVIDER} 未配置"
            )
        else:
            assert _LLM_PROVIDER in provider_codes, (
                f"LLM 供应商 {_LLM_PROVIDER} 未配置"
            )
            assert _IMAGE_PROVIDER in provider_codes, (
                f"图像供应商 {_IMAGE_PROVIDER} 未配置"
            )

        # ==================================================================
        # Phase 2: 创建小说 + 清洗
        # ==================================================================
        _phase("Phase 2 - 创建小说与文本清洗")

        r = _timed("create_novel", lambda: client.post(
            "/api/novels",
            json={"name": "夜归人-全流程测试", "text": SAMPLE_NOVEL},
        ))
        assert r.status_code == 201, f"创建小说失败: {r.text}"
        novel_id = r.json()["id"]
        _ok(f"小说已创建: NOVEL_ID={novel_id}")

        # 验证小说详情
        r = client.get("/api/novels/detail", params={"novel_id": novel_id})
        assert r.status_code == 200
        novel_detail = r.json()
        assert novel_detail["name"] == "夜归人-全流程测试"
        assert len(novel_detail["content"]) > 100
        _ok(f"小说字数: {len(novel_detail['content'])}")

        # 清洗文本
        r = _timed("clean_novel", lambda: client.post(
            "/api/novels/clean",
            params={"novel_id": novel_id},
            json={
                "rules": ["format", "serial", "punct", "speech_quote"],
                "apply": True,
            },
        ))
        assert r.status_code == 200, f"小说清洗失败: {r.text}"
        clean_result = r.json()
        assert clean_result["applied"] is True
        _ok(
            f"文本清洗完成: format={clean_result['is_format_cleaned']}, "
            f"serial={clean_result['is_serial_cleaned']}, "
            f"punct={clean_result['is_punct_cleaned']}"
        )

        # ==================================================================
        # Phase 3: AI 推导角色
        # ==================================================================
        _phase("Phase 3 - AI 角色推导（真实 LLM 调用）")

        r = _timed("derive_roles", lambda: client.post(
            "/api/roles/derive",
            json={
                "novel_id": novel_id,
                "preset_id": "role_derive_vip",
                "replace_existing": True,
                "provider_code": _LLM_PROVIDER,
                "model": _LLM_MODEL,
            },
        ))
        assert r.status_code == 200, f"角色推导失败: {r.text}"
        role_result = r.json()
        n_roles = role_result["count"]
        assert n_roles >= 2, f"期望至少 2 个角色，实际 {n_roles}"
        _ok(f"AI 推导出 {n_roles} 个角色 (耗时 {timings['derive_roles']:.1f}s)")

        # 打印角色信息
        r = client.get("/api/roles", params={"novel_id": novel_id})
        assert r.status_code == 200
        roles = r.json()["items"]
        for role in roles:
            content_preview = (role["content"] or "")[:80]
            _info(f"  角色: {role['name']} - {content_preview}...")

        role_names = {r["name"] for r in roles}
        assert "沈砚之" in role_names or "顾长宁" in role_names, (
            f"未找到预期角色，实际角色: {role_names}"
        )
        _ok(f"角色名称验证通过: {role_names}")

        # ==================================================================
        # Phase 4: 创建项目 + 摘要 + 分镜拆分
        # ==================================================================
        _phase("Phase 4 - 创建项目、摘要与分镜拆分（真实 LLM 调用）")

        r = _timed("create_project", lambda: client.post(
            "/api/projects",
            json={
                "name": "夜归人-连环画",
                "novel_id": novel_id,
                "mode": "manga",
                "derive_preset_id": "plot_manga_fusion_bw",
            },
        ))
        assert r.status_code == 201, f"创建项目失败: {r.text}"
        project_id = r.json()["id"]
        _ok(f"项目已创建: PROJECT_ID={project_id}")

        # 生成项目摘要
        r = _timed("summary", lambda: client.post(
            "/api/projects/summary",
            params={"project_id": project_id},
            json={
                "max_words": 200,
                "provider_code": _LLM_PROVIDER,
                "model": _LLM_MODEL,
            },
        ))
        assert r.status_code == 200, f"摘要生成失败: {r.text}"
        summary = r.json()["summary"]
        assert len(summary) > 10, "摘要内容过短"
        _ok(f"项目摘要 ({len(summary)} 字): {summary[:100]}...")

        # 拆分分镜
        r = _timed("split_storyboard", lambda: client.post(
            "/api/projects/split",
            params={"project_id": project_id},
            json={
                "preset_id": "storyboard_short_v1",
                "replace_existing": True,
                "provider_code": _LLM_PROVIDER,
                "model": _LLM_MODEL,
            },
        ))
        assert r.status_code == 200, f"分镜拆分失败: {r.text}"
        split_result = r.json()
        n_shots = split_result["count"]
        assert n_shots >= 3, f"期望至少 3 个分镜，实际 {n_shots}"
        _ok(f"AI 拆分出 {n_shots} 个分镜 (耗时 {timings['split_storyboard']:.1f}s)")

        # 获取分镜列表
        r = client.get("/api/projects/scripts", params={"project_id": project_id})
        assert r.status_code == 200
        scripts = r.json()["items"]
        script_ids = [s["id"] for s in scripts]
        assert len(script_ids) == n_shots

        # 打印前几个分镜
        for i, s in enumerate(scripts[:5]):
            content_preview = (s["content"] or "")[:80]
            _info(f"  分镜 {i+1}: {content_preview}...")

        # ==================================================================
        # Phase 5: 批量推导图片提示词
        # ==================================================================
        _phase("Phase 5 - 批量推导图片提示词（真实 LLM 调用）")

        # 只为前 N 个分镜推导提示词和生成图片，控制时间和费用
        target_script_ids = script_ids[:_MAX_SHOTS]
        _info(f"将为前 {len(target_script_ids)} 个分镜推导图片提示词并生成图片")

        r = _timed("batch_derive_prompts", lambda: client.post(
            f"/api/image-derive/projects/{project_id}/batch",
            json={
                "script_ids": target_script_ids,
                "provider_code": _LLM_PROVIDER,
                "model": _LLM_MODEL,
            },
        ))
        assert r.status_code == 200, f"批量推导失败: {r.text}"
        derive_summary = r.json()
        _ok(
            f"图片提示词推导完成: total={derive_summary['total']}, "
            f"success={derive_summary['success']}, failed={derive_summary['failed']} "
            f"(耗时 {timings['batch_derive_prompts']:.1f}s)"
        )
        assert derive_summary["success"] >= 1, "至少需要成功推导 1 个分镜的提示词"

        # 验证提示词已填充
        r = client.get("/api/projects/scripts", params={"project_id": project_id})
        scripts_after = r.json()["items"]
        filled_scripts = [s for s in scripts_after if s["image_prompt"]]
        _ok(f"image_prompt 填充率: {len(filled_scripts)}/{len(scripts_after)}")
        assert len(filled_scripts) >= 1

        # 打印第一个提示词预览
        if filled_scripts:
            prompt_preview = filled_scripts[0]["image_prompt"][:200]
            _info(f"  首个提示词预览: {prompt_preview}...")

        # ==================================================================
        # Phase 6: 图片生成（真实图像 API 调用）
        # ==================================================================
        _phase("Phase 6 - 图片生成（真实图像 API 调用）")

        # 获取当前 OUTPUT_DIR（被 conftest 的 _patch_output_dir 指向 tmp_path）
        from app.config import OUTPUT_DIR as current_output_dir

        generated_tasks = []
        for idx, sid in enumerate(target_script_ids):
            _info(f"正在生成分镜 {idx+1}/{len(target_script_ids)} 的图片 (script_id={sid})...")

            r = _timed(
                f"generate_image_{idx+1}",
                lambda sid=sid: client.post(
                    "/api/image-generation/generate",
                    json={
                        "script_id": sid,
                        "provider_code": _IMAGE_PROVIDER,
                        "model": _IMAGE_MODEL,
                        "aspect_ratio": _IMAGE_ASPECT_RATIO,
                        "resolution": _IMAGE_RESOLUTION,
                    },
                ),
            )

            # 图像生成可能因为各种原因失败，记录但不立即中断
            if r.status_code != 200:
                print(f"  [WARN] 分镜 {sid} 图片生成失败: {r.text}")
                continue

            gen_result = r.json()
            task_id = gen_result["task_id"]
            image_url = gen_result["image_url"]
            generated_tasks.append({
                "script_id": sid,
                "task_id": task_id,
                "image_url": image_url,
            })
            _ok(
                f"分镜 {idx+1} 图片已生成: task_id={task_id} "
                f"(耗时 {timings[f'generate_image_{idx+1}']:.1f}s)"
            )

        assert len(generated_tasks) >= 1, (
            f"至少需要成功生成 1 张图片，实际成功 {len(generated_tasks)}"
        )

        # 如果 API 返回远程 URL，下载到本地以便导出
        _phase("Phase 6.5 - 图片本地化处理")
        for task_info in generated_tasks:
            image_url = task_info["image_url"]
            sid = task_info["script_id"]

            project_img_dir = current_output_dir / str(project_id) / "1" / "image"
            local_path = _download_url_to_local(
                url=image_url,
                output_dir=project_img_dir,
                filename_prefix=f"script_{sid}",
            )

            if local_path and local_path != image_url:
                # 更新数据库中的图片路径为本地路径
                r = client.get(
                    "/api/projects/scripts/detail",
                    params={"script_id": sid},
                )
                if r.status_code == 200:
                    script_detail = r.json()
                    # 更新 main_image 和 candidate_images
                    import json as _json
                    candidates = _json.loads(script_detail.get("candidate_images") or "{}")
                    for key, cand in candidates.items():
                        if cand.get("task_id") == task_info["task_id"]:
                            cand["image_url"] = local_path
                    client.put(
                        "/api/projects/scripts/detail",
                        params={"script_id": sid},
                        json={
                            **{k: script_detail.get(k, "") for k in [
                                "content", "image_prompt", "video_prompt",
                                "screen_prompt", "reference_image", "notes", "extra",
                            ]},
                            "main_image": local_path,
                            "candidate_images": _json.dumps(candidates, ensure_ascii=False),
                            "selected_candidate": task_info["task_id"],
                            "is_main_locked": script_detail.get("is_main_locked", False),
                            "generation_enabled": script_detail.get("generation_enabled", True),
                            "duration": script_detail.get("duration"),
                            "prompt_touched": True,
                        },
                    )
                    task_info["image_url"] = local_path
                    task_info["local_path"] = local_path
                    _ok(f"分镜 {sid} 图片已本地化: {local_path}")
            elif local_path:
                task_info["local_path"] = local_path
                _ok(f"分镜 {sid} 图片已在本地: {local_path}")

        # 验证候选图
        if generated_tasks:
            test_sid = generated_tasks[0]["script_id"]
            r = client.get(f"/api/image-generation/candidates/{test_sid}")
            assert r.status_code == 200
            candidates = r.json()
            assert len(candidates) >= 1
            _ok(f"分镜 {test_sid} 候选图数量: {len(candidates)}")

        # ==================================================================
        # Phase 7: 导出连环画
        # ==================================================================
        _phase("Phase 7 - 导出连环画（长图拼接 + ZIP 打包）")

        # 检查导出信息
        r = client.get(f"/api/export/info/{project_id}")
        assert r.status_code == 200
        export_info = r.json()
        _ok(
            f"导出信息: total_scripts={export_info['total_scripts']}, "
            f"scripts_with_images={export_info['scripts_with_images']}, "
            f"can_export={export_info['can_export']}"
        )
        assert export_info["can_export"] is True, "没有任何分镜有主图，无法导出"

        # 创建长图导出
        r = _timed("export_vertical", lambda: client.post(
            "/api/export/create",
            json={
                "project_id": project_id,
                "export_style": "vertical",
                "page_numbers": True,
                "titles": True,
                "quality": 90,
            },
        ))
        assert r.status_code == 200, f"导出失败: {r.text}"
        export_task = r.json()
        assert export_task["status"] == "done", f"导出状态不是 done: {export_task}"
        assert export_task["file_size"] > 0, "导出文件大小为 0"
        export_id = export_task["id"]
        _ok(
            f"连环画长图已导出: task_id={export_id}, "
            f"size={export_task['file_size']} bytes, "
            f"path={export_task['output_path']} "
            f"(耗时 {timings['export_vertical']:.1f}s)"
        )

        # 下载导出文件并验证
        r = client.get(f"/api/export/download/{export_id}")
        assert r.status_code == 200
        assert len(r.content) > 0
        assert r.headers.get("content-type", "").startswith("image/")
        export_bytes = len(r.content)
        _ok(f"导出长图下载验证通过: {export_bytes} bytes")

        # 验证导出文件在磁盘上存在
        export_file = current_output_dir / export_task["output_path"]
        assert export_file.exists(), f"导出文件不存在: {export_file}"
        assert export_file.stat().st_size > 0
        _ok(f"导出文件磁盘验证通过: {export_file}")

        # 创建 ZIP 打包
        r = _timed("export_zip", lambda: client.post(
            f"/api/export/zip/{project_id}"
        ))
        assert r.status_code == 200, f"ZIP 打包失败: {r.text}"
        assert len(r.content) > 0
        assert r.headers.get("content-type") == "application/zip"
        zip_bytes = len(r.content)
        _ok(f"ZIP 打包下载验证通过: {zip_bytes} bytes (耗时 {timings['export_zip']:.1f}s)")

        # ==================================================================
        # 总览
        # ==================================================================
        total_time = time.time() - overall_start
        _phase("全流程测试完成 - 总览")
        _ok(f"总耗时: {total_time:.1f}s ({total_time/60:.1f} 分钟)")
        _ok(f"小说字数: {len(novel_detail['content'])}")
        _ok(f"推导角色: {n_roles} 个")
        _ok(f"拆分分镜: {n_shots} 个")
        _ok(f"生成图片: {len(generated_tasks)} 张")
        _ok(f"导出长图: {export_bytes} bytes")
        _ok(f"导出 ZIP: {zip_bytes} bytes")

        print("\n  各阶段耗时明细:")
        for label, sec in sorted(timings.items(), key=lambda x: -x[1]):
            print(f"    {label:>28s}: {sec:7.2f}s")
        print("=" * 70)
