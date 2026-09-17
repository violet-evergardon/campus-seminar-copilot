# 简历描述（基于实际实现）

- 将半导体文档 RAG 原型场景化重构为高校学术活动推荐与问答平台，使用 FastAPI、SQLAlchemy、SQLite、React、TypeScript 和 Ant Design 实现采集、解析、审核、发布、搜索、推荐、问答、收藏、ICS、反馈与坏案例闭环。
- 设计无 API 密钥可运行的确定性检索和模板化可溯源回答，并通过 provider 隔离可选 Milvus/BGE/LLM；设置 Corrective/Adaptive RAG 最大循环次数。
- 实现五个武汉大学公开站点的独立适配器、SSRF 域名白名单、合理超时/重试、增量去重、解析证据、离线 fixture 与单站失败隔离。
- 使用 pytest、FastAPI 集成测试、前端生产构建、项目 quality gate 和真实浏览器检查验证 MVP。测试数量与构建结果以仓库最终测试报告为准，不虚构线上用户、延迟或准确率。

