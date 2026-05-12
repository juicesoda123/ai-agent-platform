# Day 31 — Docker 容器化：一键部署

> Phase 6：生产化部署  |  预计用时：25 分钟  |  2026-05-09

---

## 今日目标

1. 理解 Docker 的三层抽象：Dockerfile → Image → Container
2. 写出生产级 Dockerfile（多模块 + 依赖缓存 + 非 root）
3. 产出：`Dockerfile` + `docker-compose.yml` + `.dockerignore` + `requirements.txt`

---

## 一、概念对齐：Docker 是什么

```
Dockerfile          docker build       docker run
(食谱)          →    Image(半成品)  →   Container(运行中的进程)
"怎么做这道菜"       "冻好的预制菜"       "热好的菜端上桌"
```

你的 Agent 项目依赖：Python 3.12 + FastAPI + openai + langfuse + 两个源码目录。Dockerfile 把这些全部打包，任何人拿到镜像就能跑，不用配环境。

---

## 二、关键设计决策

### 1. 构建上下文从项目根目录

```
AI-Agent/                         ← docker build 上下文
├── agent-platform/
│   ├── Dockerfile
│   └── src/agent_platform/       ← COPY 到镜像
├── single-agent/
│   └── src/agent/                ← COPY 到镜像（server.py 依赖它）
```

因为 `server.py` 导入了 `agent.tool_register`，Docker 镜像里两个模块都需要。

### 2. 三层缓存策略

```dockerfile
COPY requirements.txt .           # 第1层：依赖文件（很少变）
RUN pip install ...                # 第2层：安装依赖（很久，缓存住）
COPY src/ ...                      # 第3层：源码（经常变，但上面两层不动）
```

改一行代码 → 只重建第3层（秒级）。不改依赖 → pip install 永远不用重跑。

### 3. .dockerignore

```
__pycache__/   ← 不打包编译缓存
.env           ← 不打包密钥（运行时 --env-file 注入）
examples/      ← 不打包测试
```

---

## 三、使用方式

```bash
# 安装 Docker Desktop 后, 在 AI-Agent 根目录:

# 构建镜像
docker build -t agent-platform -f agent-platform/Dockerfile .

# 运行（注入 .env）
docker run -p 8000:8000 --env-file agent-platform/.env agent-platform

# 或用 docker compose 一键启动
docker compose -f agent-platform/docker-compose.yml up -d

# 验证
curl http://localhost:8000/health
```

---

## 四、文件清单

```
agent-platform/
├── Dockerfile              ← 镜像构建指令
├── docker-compose.yml      ← 一键启动
├── .dockerignore           ← 排除文件
├── requirements.txt        ← Python 依赖（精确版本）
├── src/agent_platform/     ← 5 个模块
└── .env                    ← 运行时注入，不进镜像
```

---

## 五、验收标准

```bash
# 构建成功
docker build -t agent-platform -f agent-platform/Dockerfile .
# → Successfully tagged agent-platform:latest

# 启动成功
docker run -p 8000:8000 --env-file agent-platform/.env agent-platform
# → Uvicorn running on http://0.0.0.0:8000

# 健康检查
curl http://localhost:8000/health
# → {"status":"ok","model":"deepseek-chat","tools":["calculator"]}
```
