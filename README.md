# Campus Seminar Copilot（高校学术活动智能推荐与问答平台）

这是对同工作区 `RAG_PROJECT` 的场景化重构：保留混合检索、批量增量索引、工具式问答和 Corrective/Adaptive RAG 思想，改造成完整的学术活动业务闭环。默认无需 API 密钥、Milvus 或外部模型即可本地运行。

## 功能

- 武汉大学 5 个公开站点的独立适配器、定时增量同步、跨来源去重、解析证据和离线 fixtures。
- 粘贴文本或上传 PDF/图片/TXT/Markdown，抽取字段并生成草稿；管理员可编辑、发布或驳回。
- 关键词/自然语言、日期、领域、主办方、线上/线下和状态筛选。
- `0.45 semantic + 0.30 keyword + 0.25 time` 推荐评分及可解释理由。
- 只基于已发布活动的限轮 RAG 问答；收藏、ICS、反馈和坏案例管理。
- SQLite 唯一事实源；Milvus/BGE/外部 LLM 是环境变量启用的可选 provider。

## Windows PowerShell 启动

需要 Python 3.11+ 和 Node.js 20+。

```powershell
cd D:\Code\RAG企业知识库项目\campus-seminar-copilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r .\backend\requirements.txt
$env:PYTHONPATH = (Resolve-Path .\backend)
python -m app.seed

# 终端 1
cd .\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2（从项目根目录）
cd .\frontend
npm install
npm run dev
```

打开 <http://127.0.0.1:5173>；OpenAPI 在 <http://127.0.0.1:8000/docs>。

## Linux / macOS 启动

```bash
cd campus-seminar-copilot
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -r backend/requirements.txt
PYTHONPATH=backend python -m app.seed

# 终端 1
cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 终端 2
cd frontend && npm install && npm run dev
```

## Docker Compose

```bash
docker compose up --build
```

可选 Milvus：`docker compose --profile milvus up --build`，并在 `.env` 设置 `RETRIEVAL_PROVIDER=milvus` 和 `MILVUS_URI=http://milvus:19530`。默认 Compose 不启动 Milvus。

## 演示数据与采集

`PYTHONPATH=backend python -m app.seed` 幂等创建演示用户、五个采集源和五条明确标注为本地 fixture 的未来活动。UI 的“采集状态”可运行 fixture 或在线同步；测试从不依赖实时网络。

公开来源适配器：武汉大学珞珈讲坛、新闻与传播学院、经济与管理学院、数学与统计学院、质量发展战略研究院。在线采集使用明确 User-Agent、域名白名单、超时、有限重试和请求间隔；这里只承诺“定时增量同步”，不宣称实时推送。

## 验证

```powershell
# Windows（激活虚拟环境并完成 frontend npm install 后）
.\scripts\verify.ps1
```

```bash
# Linux/macOS
./scripts/verify.sh
```

分步命令：

```bash
cd backend
python -m compileall -q app
python -m pytest -q
cd ../frontend
npm run build
cd ..
python scripts/evaluate.py
python C:/Users/86199/.codex/skills/academic-event-platform-builder/scripts/quality_gate.py .
```

## 配置与安全边界

复制 `.env.example` 为 `.env` 可覆盖配置。`ADMIN_TOKEN` 留空时是适合本地演示的无鉴权管理模式；部署到共享网络前必须设置令牌并在反向代理层增加身份认证、TLS 和限流。图片上传在未配置 OCR provider 时只保存文件并建立“待补充”草稿，不虚构字段。

## 文档

- [架构](docs/architecture.md)
- [数据模型](docs/data-model.md)
- [检索与排序](docs/retrieval-and-ranking.md)
- [演示脚本](docs/demo-script.md)
- [简历描述](docs/resume-description.md)
- [测试报告](docs/test-report.md)
