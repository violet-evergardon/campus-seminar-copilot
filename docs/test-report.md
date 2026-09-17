# 测试报告

验证日期：2026-08-12（Asia/Shanghai）。

| 检查 | 结果 | 证据摘要 |
|---|---|---|
| Python 静态编译 | 通过 | `python -m compileall -q backend/app` |
| pytest / API 集成 | 通过 | 15 passed，0 warning（0.35s） |
| 前端生产构建 | 通过 | Vite 7.3.6，4,872 modules transformed |
| 离线排序评测 | 通过 | 2/2 ordering checks，测试集 rate 1.0，不代表线上准确率 |
| 技能 quality gate | 通过 | chat/recommend/upload/ICS/admin/feedback 六项均 true |
| 演示数据幂等性 | 通过 | 首次 5 条活动/5 来源；复跑 `events_created: 0` |
| 浏览器 UI | 通过 | 桌面与 390×844；最终控制台错误/警告 0 |
| 原文件保护 | 通过 | 受保护文件在任务日期的修改数 0 |

浏览器行为覆盖：相关性过滤、可溯源问答、详情评分分量、收藏/ICS 入口、粘贴解析成草稿、管理员发布、五站 fixture 同步、无结果坏案例和移动导航自动收起。

真实限制：本机未启用 Milvus、BGE、外部 LLM 和 OCR；相应 provider 只提供可选配置，MVP 实测路径是 SQLite、确定性相似度、模板回答和图片待补充草稿。本机未安装 Docker，Compose YAML 已解析并确认包含 backend/frontend/milvus 三个服务，但未实际拉镜像启动。前端单包约 1.27 MB（gzip 约 402 KB），生产规模可进一步路由级拆包。
