# -*- coding: utf-8 -*-
"""种子数据：提示词五件套（幂等）。

- prompts：源库 13 条全量迁移（_inspect/prompts.json 快照 -> seeds/source_prompts.json）
- snippets：负面水印 / 图片推导默认前缀 / 三视图渲染词（源系统硬编码取证）
- templates：首期 8 个阶段模板（含分段标记）
- presets：首期 6+ 预设并对齐源 settings 激活状态（image_derive -> plot_manga_fusion_bw）
"""
import json
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models.novel import Novel  # noqa: F401 触发建表
from app.models.provider import ProviderAccount, Setting
from app.models.prompt import Prompt, PromptPreset, PromptSnippet, PromptTemplate
from app.models.role import CategoryTag, Role  # noqa: F401
from app.prompt_engine import list_variables

SEED_DIR = Path(__file__).parent

# ------------------------------------------------------------------ snippets

NEGATIVE_WATERMARK = "禁止：图片右下角出现腾讯动漫 17173 等其他机构水印！"
STYLE_PREFIX_DEFAULT = "顶级韩漫风格，融合精致日系2D插画美学，精细线稿，柔和色彩，电影级光影，高对比度，"
PORTRAIT_RENDER = (
    "strictly isolated on a pure white background, solid white backdrop, no cast shadows，无场景、无文字、无 logo。"
    "画面包含 full-body front view, full-body side view (left/right), full-body back view, "
    "close-up headshot, facial expression sheet featuring 4 close-up headshots displaying distinct emotions。"
    "渲染要求：physically based rendering (PBR), ambient occlusion (AO), subsurface scattering (SSS)。"
    "masterpiece, best quality, ultra-detailed, 8k resolution, sharp focus。"
    "Please avoid any text, watermarks, blurred edges, distorted anatomy, or low-quality plastic textures。"
)

# ------------------------------------------------------------------ templates

IMAGE_DERIVE_BODY = """<!--#seg:system-->
你是一位顶级条漫分镜画师，擅长把小说分镜内容推导为多格条漫的图片生成提示词。

<!--#seg:instruction-->
请把【本镜内容】推导为一条完整的图片生成提示词，严格输出三段，段与段之间用一个空行分隔：
第一段【画风与多格场景总述】：以"{{ style_prefix }}"开头，描述多格构图方式、每格画面内容、机位景别、旁白框位置；
第二段【版式逻辑详解】：说明格子数量与比例、阅读动线（如Z字/横向）、选择该版式的剧情理由、每格的画面细节与情绪、色彩规范、字框样式（统一白底黑边，正文黑字#1a1a1a，不因情绪变色或夸张放大）；
第三段【固定负面句】：逐字输出"{{ negative_suffix }}"。

<!--#seg:context-->
【画风】{{ style_prefix }}
【项目摘要】{{ project_summary }}
【角色卡】
{% for r in roles %}{{ r.name }}：{{ r.content }}
{% endfor %}【前情分镜】
{% for s in prev_shots %}第{{ s.order }}镜：{{ s.content }}
{% endfor %}【本镜内容】{{ shot_content }}

<!--#seg:custom_slots-->
{% if custom_1 %}{{ custom_1 }}{% endif %}

<!--#seg:project_affix_prefix-->
{% if project_img_prefix %}{{ project_img_prefix }}{% endif %}

<!--#seg:project_affix_suffix-->
{% if project_img_suffix %}{{ project_img_suffix }}{% endif %}

<!--#seg:negative-->
{{ negative_suffix }}"""

STORYBOARD_TAIL = "\n\n## 待处理正文\n{{ novel_text }}\n"

ROLE_DERIVE_TAIL = "\n\n## 待推导小说\n{{ novel_text }}\n"

TEMPLATES = [
    # stage, name, body 来源（源 prompts id -> 追加变量尾巴），无则用内置
    ("role_derive", "VIP智能角色推导-v1", 13, ROLE_DERIVE_TAIL),
    ("storyboard_short", "分镜拆分-短文本版-v1", 9, STORYBOARD_TAIL),
    ("storyboard_long", "分镜拆分-长文本版-v1", 10, STORYBOARD_TAIL),
    ("dialogue_split", "一键对话分离-v1", 11, STORYBOARD_TAIL),
    ("rewrite", "文案同义改写-v1", 12, STORYBOARD_TAIL),
    ("summary", "项目摘要-v1", None, None),
    ("image_derive", "条漫三段式推导-v1", None, IMAGE_DERIVE_BODY),
    ("role_portrait", "角色三视图拼装-v1", None, None),
]

SUMMARY_BODY = """<!--#seg:system-->
你是一位资深网文编辑。

<!--#seg:instruction-->
请阅读下面的小说正文，输出一段不超过 {{ max_words }} 字的剧情梗概，直接输出梗概正文，不要任何解释。

<!--#seg:context-->
【正文】
{{ novel_text }}"""

PORTRAIT_BODY = """<!--#seg:style_prefix-->
{% if art_style_name %}{{ art_style_name }}画风，{% endif %}{{ portrait_render | default('') }}

<!--#seg:context-->
{{ role_content }}"""

PRESETS = [
    # preset_id, stage, name, template_stage, active
    ("role_derive_vip", "role_derive", "VIP智能角色推导（源库迁移）", "role_derive", True),
    ("storyboard_short_v1", "storyboard_short", "分镜拆分-短句版", "storyboard_short", True),
    ("storyboard_long_v1", "storyboard_long", "分镜拆分-长句版", "storyboard_long", False),
    ("dialogue_split_v1", "dialogue_split", "一键对话分离", "dialogue_split", True),
    ("rewrite_v1", "rewrite", "文案同义改写", "rewrite", True),
    ("summary_v1", "summary", "项目摘要", "summary", True),
    ("plot_manga_fusion_bw", "image_derive", "剧情条漫融合（对标源预设）", "image_derive", True),
    ("portrait_s1_v1", "role_portrait", "三视图直接拼装（S1）", "role_portrait", True),
]


def seed_all(verbose: bool = True) -> dict:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    stats = {"prompts": 0, "snippets": 0, "templates": 0, "presets": 0,
             "category_tags": 0, "provider_accounts": 0, "settings": 0}
    try:
        # 1) prompts：源库 13 条幂等导入
        src = json.loads((SEED_DIR / "source_prompts.json").read_text(encoding="utf-8"))
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
        for row in src:
            exists = (
                db.query(Prompt)
                .filter(Prompt.title == row["title"], Prompt.category == row["category"])
                .first()
            )
            if exists:
                continue
            db.add(
                Prompt(
                    title=row["title"],
                    content=row["content"],
                    category=row["category"],
                    purpose=purpose_map.get(row["title"], "generic"),
                    is_system=bool(row.get("is_system", 0)),
                )
            )
            stats["prompts"] += 1

        # 2) snippets
        snippets = [
            ("negative", "平台水印禁令（源库实证）", NEGATIVE_WATERMARK, 0),
            ("style_prefix", "图片推导默认前缀（prompts#5）", STYLE_PREFIX_DEFAULT, 0),
            ("portrait_render", "三视图渲染公共词（roles 实证）", PORTRAIT_RENDER, 1),
        ]
        for tag, name, content, order in snippets:
            if not db.query(PromptSnippet).filter(PromptSnippet.name == name).first():
                db.add(PromptSnippet(tag=tag, name=name, content=content, sort_order=order))
                stats["snippets"] += 1

        db.commit()

        # 3) templates（body 取源 prompt content 或内置）
        src_by_title = {r["title"]: r["content"] for r in src}
        title_by_pid = {r["id"]: r["title"] for r in src}
        tpl_id_by_stage: dict = {}
        for stage, name, src_pid, extra in TEMPLATES:
            if db.query(PromptTemplate).filter(PromptTemplate.stage == stage).first():
                tpl_id_by_stage[stage] = (
                    db.query(PromptTemplate).filter(PromptTemplate.stage == stage).first().id
                )
                continue
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
            db.add(tpl)
            db.commit()
            db.refresh(tpl)
            tpl_id_by_stage[stage] = tpl.id
            stats["templates"] += 1
            if verbose:
                print(f"  template[{stage}] variables: {list_variables(body)}")

        # 4) presets
        for pid, stage, name, tpl_stage, active in PRESETS:
            if tpl_stage not in tpl_id_by_stage:
                continue
            if db.query(PromptPreset).filter(PromptPreset.id == pid).first():
                continue
            db.add(
                PromptPreset(
                    id=pid,
                    stage=stage,
                    name=name,
                    template_id=tpl_id_by_stage[tpl_stage],
                    slots_json="{}",
                    is_system=True,
                    is_active=active,
                )
            )
            stats["presets"] += 1

        db.commit()

        # 5) category_tags：源库 8 条（类型/时空）
        ct_seed = [
            ("类型", "角色", 0), ("类型", "场景", 1), ("类型", "道具", 2),
            ("时空", "古代", 0), ("时空", "现代", 1), ("时空", "科幻", 2),
            ("时空", "玄幻", 3), ("时空", "ABO", 4),
        ]
        for cat, val, order in ct_seed:
            exists = (
                db.query(CategoryTag)
                .filter(CategoryTag.category == cat, CategoryTag.tag_value == val)
                .first()
            )
            if not exists:
                db.add(CategoryTag(category=cat, tag_value=val, display_order=order))
                stats["category_tags"] += 1

        # 6) provider_accounts：从源 settings.json 快照导入 LLM Key（本地私有数据）
        src_settings_path = SEED_DIR.parent.parent.parent / "_inspect" / "settings.json"
        if src_settings_path.exists():
            try:
                src_settings = {r["key"]: r["value"] for r in json.loads(
                    src_settings_path.read_text(encoding="utf-8"))}
            except Exception:
                src_settings = {}
            key_map = {
                "deepseek": ("account_pool_deepseek_api_key", "https://api.deepseek.com/v1", "deepseek-chat"),
                "grsai": ("account_pool_grsai_api_key", "https://api.grsai.com/v1", "deepseek-chat"),
                "volcengine": ("account_pool_volcengine_api_key",
                               "https://ark.cn-beijing.volces.com/api/v3", "doubao-pro-32k"),
            }
            for code, (sk, url, model) in key_map.items():
                key = src_settings.get(sk, "")
                if not key:
                    continue
                exists = (
                    db.query(ProviderAccount)
                    .filter(ProviderAccount.provider_code == code)
                    .first()
                )
                if not exists:
                    db.add(ProviderAccount(provider_code=code, base_url=url,
                                           api_key=key, model=model,
                                           remark="源雪漫画 settings 迁移"))
                    stats["provider_accounts"] += 1

        # 7) settings：合理化默认值
        defaults = {
            "llm_default_provider": "deepseek",
            "image_provider": "grsai",
            "image_model": "nano-banana-2",
            "image_aspect_ratio": "3:4",
            "image_resolution": "2K",
            "image_batch_concurrency": "5",
            "manga_derive_preset_id": "plot_manga_fusion_bw",
        }
        for k, v in defaults.items():
            if not db.get(Setting, k):
                db.add(Setting(key=k, value=v))
                stats["settings"] += 1

        db.commit()
    finally:
        db.close()
    if verbose:
        print("seed done:", stats)
    return stats


if __name__ == "__main__":
    seed_all()
