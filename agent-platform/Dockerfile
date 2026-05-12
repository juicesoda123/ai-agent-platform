# Agent Platform Docker 镜像
# 从 AI-Agent 根目录构建:
#   docker build -t agent-platform -f agent-platform/Dockerfile .
# 运行:
#   docker run -p 8000:8000 --env-file agent-platform/.env agent-platform

FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY agent-platform/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn

# 拷贝源码（两个模块）
COPY agent-platform/src/agent_platform/ ./agent_platform/
COPY single-agent/src/agent/ ./agent/

ENV PYTHONPATH=/app
ENV DEEPSEEK_BASE_URL=https://api.deepseek.com

EXPOSE 8000

CMD ["uvicorn", "agent_platform.server:app", "--host", "0.0.0.0", "--port", "8000"]
