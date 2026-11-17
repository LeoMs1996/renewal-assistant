# 续保助手生产镜像（多阶段、非 root、单 worker）
#
# 平台工程域（t8，2026-11-17）依据：
# - 单 worker 是硬约束：server/metrics.py 是进程内聚合，多 worker 会让
#   Prometheus 抓到 N 份互不相干的计数器（rate() 结果随 worker 命中率抖动）。
#   要横向扩容应改成多副本 + 每副本独立暴露（见 k8s/deployment.yaml），
#   而不是单容器多 worker。
# - 依赖用 requirements.lock.txt（版本锁定，构建可重现；requirements.txt 只声明区间）。
# - 镜像内不带 .env / traces / .venv（见 .dockerignore），凭证由环境注入。
# - HEALTHCHECK 打 /health（应用层探活），k8s 侧另配 startup/readiness/liveness 三探针。
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 先装依赖，利用层缓存（代码改动不触发重装）
COPY requirements.lock.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt

# 仅拷贝运行所需目录
COPY server ./server
COPY mcp_servers ./mcp_servers
COPY synthetic ./synthetic
COPY wiki ./wiki
COPY web ./web
COPY SPEC.md README.md ./

# 轨迹目录：容器内必须可写（TraceRecorder 会 mkdir）。生产建议挂卷或在
# k8s 里挂 emptyDir/PVC —— 容器层写会在重启后丢失，/trace 回放与
# otel_export 离线导出都依赖它。
RUN mkdir -p /app/traces && \
    groupadd --system --gid 10001 renewal && \
    useradd --system --uid 10001 --gid renewal --no-create-home renewal && \
    chown -R renewal:renewal /app

USER renewal
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status==200 else 1)"

# --proxy-headers：容器/k8s 场景下由反代终止 TLS，让 uvicorn 信任 X-Forwarded-*；
# --forwarded-allow-ips 默认只信 127.0.0.1，集群内需要按需显式放开（见 README 风险说明）。
CMD ["uvicorn", "server.app:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", \
     "--timeout-keep-alive", "75"]
