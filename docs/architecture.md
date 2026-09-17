# 架构说明

系统采用 FastAPI + SQLAlchemy + SQLite 与 React + TypeScript + Ant Design。SQLite 是活动、用户行为、审核和采集记录的唯一事实来源；检索索引可删除重建，发布失败不会回滚业务事实。

数据流为：站点适配器/粘贴/上传 → 安全解析与证据 → 指纹去重 → 草稿 → 管理员编辑审核 → 发布与增量索引 → 搜索/推荐/问答 → 收藏/ICS/反馈 → 坏案例。

原 `RAG_PROJECT` 的场景化继承包括：标题层级与长摘要切分思想；BGE 稠密向量、BM25、HNSW、RRF 混合检索设计；生产者/消费者批处理与增量同步；工具式问答；Corrective/Adaptive 路由、改写、相关性和答案校验。新实现消除了导入即连外部服务、硬编码路径/地址、全量删 Collection、无限 CLI 和无限重试。

默认 `sqlite + deterministic + template` 无密钥组合。Milvus/Embedding/LLM 仅通过环境变量和 provider 启用。问答工作流最多两轮纠错，只使用已发布且未过期的 SQLite 活动。

