# frontend（Phase 1 后期 / Phase 2 起实施）

按设计文档 [08-前端页面设计](../设计文档/08-前端页面设计.md) 实施：Vue3 + Vite + Element Plus + Pinia。

首个落地页面（Phase 1 验收项）：

1. `/prompts` 提示词库（对接 `/api/prompts`）
2. `/assemble` 拼装调试台（对接 `/api/assemble/preview`，分段高亮）

脚手架（届时执行）：

```bat
npm create vite@latest frontend -- --template vue-ts
cd frontend && npm i element-plus pinia vue-router axios
```
