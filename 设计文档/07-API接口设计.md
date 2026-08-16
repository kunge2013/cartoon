# 07 - API 接口设计（REST，前缀 /api）

> 仅列核心端点；字段级 Schema 以 FastAPI 自动生成的 OpenAPI（`/docs`）为准。
> 通用约定：列表分页 `?page=&page_size=`；时间戳 ISO8601；错误 `{detail: "..."}`。

## 1. 健康与元信息

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 存活/版本/DB 连接 |
| GET | `/assemble/stages` | 阶段字典+变量契约（调试台用） |

## 2. 提示词体系 ★（详见文档 05）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/prompts` | 列表（category/purpose/keyword/is_system 过滤）/ 新建 |
| GET/PUT/DELETE | `/prompts/{id}` | 详情/更新(system 自动 fork)/删除(system 拒绝) |
| POST | `/prompts/{id}/fork` | 复制副本 |
| POST | `/prompts/import`；GET `/prompts/export` | JSON 导入导出 |
| GET/POST | `/prompt-categories` | 分类（含计数） |
| GET/POST | `/prompt-snippets`；PUT/DELETE `/prompt-snippets/{id}` | 片段库 |
| GET/POST | `/prompt-templates`；PUT/DELETE `/prompt-templates/{id}`；GET `/prompt-templates/{id}/variables` | 模板库 |
| GET/POST | `/prompt-presets`；PUT/DELETE `/prompt-presets/{id}`；POST `/prompt-presets/{id}/activate` | 预设 |
| POST | `/assemble/preview` | ★ 拼装 dry-run（分段结果） |
| GET | `/render-logs`；GET `/render-logs/{id}` | 渲染历史 |

## 3. 小说中心

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/novels` | 列表/新建（txt 上传或 paste） |
| GET/PUT/DELETE | `/novels/{id}` | 详情（含各阶段字段）/ 更新 / 删除 |
| POST | `/novels/{id}/clean` | 规则清洗（format/serial/punct），返回 diff 预览 |
| POST | `/novels/{novel_id}/stage/{stage}` | 触发 AI 阶段：role/rewrite/script/storyboard/opening（内部走拼装引擎+LLM） |
| GET/PUT | `/novels/{id}/files`；`/novels/{novel_id}/files/{file_id}` | 多标签页正文 |

## 4. 角色中心

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/roles` | 列表（novel_id 过滤）/ 新建 |
| GET/PUT/DELETE | `/roles/{id}` | 详情/更新/删除 |
| POST | `/roles/derive` | AI 推导（入参 novel_id + preset），返回并入库角色列表 |
| POST | `/roles/{id}/portrait` | 生成三视图（S1 配方 -> 图像API -> 落 roles/portrait_*.png） |
| PUT | `/roles/{id}/tags` | 设置标签 |
| GET/POST | `/category-tags` | 标签字典 |

## 5. 项目与分镜

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/projects` | 列表/新建（novel_id、mode、derive_preset_id、前后缀） |
| GET/PUT/DELETE | `/projects/{id}` | 详情/更新/删除 |
| POST | `/projects/{id}/summary` | AI 生成摘要 |
| GET/POST | `/projects/{id}/scripts` | 分镜列表（含候选图）/ 手工新增 |
| PUT | `/projects/{id}/scripts/reorder` | 批量排序 |
| POST | `/projects/{id}/split` | AI 拆分分镜（preset=storyboard_short/long） |
| GET/PUT/DELETE | `/scripts/{id}` | 单镜详情/更新（content、image_prompt、notes、enabled）/删除 |
| POST | `/scripts/{id}/derive` | 单镜推导 image_prompt（走拼装+LLM） |
| POST | `/projects/{id}/derive-batch` | 批量推导（跳过 prompt_touched） |

## 6. 图片生成

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/providers`；GET/POST `/provider-accounts`；PUT/DELETE `/provider-accounts/{id}` | 供应商与账号池 |
| POST | `/scripts/{id}/generate` | 生成候选图（n 张，provider/model/ratio/resolution 可覆盖）-> image_task |
| POST | `/projects/{id}/generate-batch` | 批量生成（并发上限=settings） |
| GET | `/image-tasks`；GET `/image-tasks/{id}` | 任务列表/详情（轮询） |
| GET | `/events/tasks` | SSE 任务进度流 |
| POST | `/scripts/{id}/select-candidate` | 选主图 |
| POST | `/image-tasks/{id}/retry` | 重试（可换模型） |

## 7. 画风库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/art-styles` | 列表（分类过滤）+ 预览图静态路径 |
| POST/PUT/DELETE | `/art-styles`… | 自定义画风 |

## 8. 导出

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/projects/{id}/export/long-strip` | 长图拼接（页码/标题/间隔参数）-> 下载 |
| POST | `/projects/{id}/export/zip` | 图片+JSON 打包 |

## 9. 设置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/settings` | K/V 全量读写（并发/比例/分辨率/默认模型/导出目录） |

## 10. SSE 事件负载示例

```
event: task_progress
data: {"task_id":"t-1024","script_id":10023,"status":"running","progress":0.4}
data: {"task_id":"t-1024","script_id":10023,"status":"done","image_path":"Output/8/0001/image/001_0_x.png"}
```
