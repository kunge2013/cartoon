# catong_gen（卡通生成器）

> 对标复刻 **雪漫画（CineGacha）v1.8.16.26** 的 Web 化项目：小说 -> AI 流水线 -> 全彩条漫分镜图。
> 技术栈：**Web（Vue3 + FastAPI）+ Python 3.11（conda 环境 `catong_gen`）**。

## 文档

全部设计文档见 [`设计文档/`](设计文档/README.md)，阅读顺序：

1. [01-项目总览与技术选型](设计文档/01-项目总览与技术选型.md)
2. [02-功能清单与流程设计](设计文档/02-功能清单与流程设计.md)（先干什么再干什么）
3. [03-核心流程设计](设计文档/03-核心流程设计.md)（一条简单核心流程）
4. [04-数据库设计](设计文档/04-数据库设计.md)
5. [★05-提示词管理模块详细设计](设计文档/05-提示词管理模块详细设计.md)
6. [★06-提示词拼装引擎设计](设计文档/06-提示词拼装引擎设计.md)
7. [07-API接口设计](设计文档/07-API接口设计.md)
8. [08-前端页面设计](设计文档/08-前端页面设计.md)
9. [09-环境与部署](设计文档/09-环境与部署.md)

## 快速开始

```bat
:: 1) conda 环境（已创建则跳过）
conda create -n catong_gen python=3.11 -y
conda activate catong_gen

:: 2) 后端依赖 + 种子数据
pip install -r backend\requirements.txt
cd backend && python -m app.seeds.seed

:: 3) 启动 API（http://127.0.0.1:8300/docs）
uvicorn app.main:app --reload --port 8300
```

## 当前进度（Phase 0~8 已落地）

- [x] Phase 0：conda env `catong_gen`（Python 3.11.15）、FastAPI 骨架、SQLite(WAL)、依赖安装
- [x] Phase 1：提示词五件套（库/片段/模板/预设/渲染历史）+ 拼装引擎（分段渲染管线）
- [x] 源库 13 条提示词种子迁移 + 3 条取证片段 + 8 个阶段模板 + 8 个预设
- [x] API：/api/prompts*、/api/prompt-*、/api/assemble/preview、/api/render-logs
- [x] Phase 2：小说中心（导入/清洗/多标签页）+ 文本清洗管线（4 规则）
- [x] Phase 3：角色中心（LLM 适配层 + AI 角色推导）+ 源库标签迁移 + 供应商账号池
- [x] Phase 4：项目与分镜（AI 拆分镜 + 项目摘要 + Script CRUD + prompt_touched 保护）
- [x] Phase 5：图片提示词推导（上下文注入 + 三段式 LLM 生成 + 渲染日志）
- [x] Phase 6：图片生成（任务状态机 + 图片供应商适配器 + 单镜/批量生成 + 候选图管理）
- [x] Phase 7：导出功能（Pillow 长图拼接 + ZIP 打包 + 页码/标题可选）
- [x] Phase 8：画风库（画风 CRUD + 项目绑定 + 提示词前缀/后缀注入）
- [x] 单元测试 49 项全过（Phase 1-7: 42 + Phase 8: 7）；端到端冒烟测试 80 项全过（Phase 1: 18 + Phase 2: 20 + Phase 3: 9 + Phase 4: 18 + Phase 5: 4 + Phase 6: 6 + Phase 7: 8 + Phase 8: 8）
- [ ] Phase 9+：批量调度、视频模式、TTS……（见设计文档 02 分期路线）

## 目录

```
backend/    FastAPI + SQLAlchemy + 拼装引擎（app/prompt_engine）
设计文档/     全部设计文档（含对标雪漫画的功能清单与分期路线）
scripts/     启动脚本
_inspect/    源应用逆向取证材料（只读快照）
```
