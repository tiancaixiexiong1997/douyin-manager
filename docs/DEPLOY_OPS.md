# 部署运维（P0）

## 健康与就绪检查

- 存活检查：`GET /health`
- 就绪检查（数据库 + Redis）：`GET /health/ready`
- 队列检查（worker 在线状态）：`GET /health/queue`
  - 返回项包含：`queued_jobs / failed_jobs / started_jobs / scheduled_jobs / deferred_jobs / stuck_jobs`

示例：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
curl http://localhost:8000/health/queue
```

## 前端 API 地址（VPS 必看）

- 前端默认走同域 `/api`（由 Nginx 反代到 `backend:8000`），无需再写死 `localhost:8000`。
- 仅在前后端分离部署时，才设置 `VITE_API_URL`（例如 `https://api.example.com`）。
- `docker-compose` 默认将后端绑定到 `127.0.0.1:8000`，避免公网直接暴露后端端口。
- 如需临时开放后端端口，可在 `.env` 中设置：`BACKEND_PORT_BIND=0.0.0.0:8000:8000`。
- `douyin-fetcher` 默认不暴露宿主机端口，仅供容器内网调用，减少端口冲突与攻击面。
- 后端默认开启“入队前 worker 活跃检测”（`REQUIRE_ACTIVE_WORKER_ON_ENQUEUE=true`），防止任务在 worker 离线时卡在“排队中”。
- 队列任务支持自动重试：
  - `JOB_QUEUE_RETRY_MAX`（默认 1）
  - `JOB_QUEUE_RETRY_INTERVAL_SECONDS`（默认 30）
  - `JOB_QUEUE_STUCK_JOB_TIMEOUT_SECONDS`（默认 1800）
- 排期日期判断使用 `APP_TIMEZONE`（默认 `Asia/Shanghai`），建议按运营时区配置，避免 UTC 偏移导致“今天被判为过去日期”。
- 启动日志会提示常见配置风险：
  - `AI_API_KEY` 为空时，AI 能力不可用（账号策划/脚本生成）。
  - 系统无任何用户且 `DEFAULT_ADMIN_PASSWORD` 为空时，首次部署会无法登录。
- 无水印代理下载支持超时与重试调优：
  - `DOWNLOAD_PROXY_CONNECT_TIMEOUT_SECONDS`（默认 15）
  - `DOWNLOAD_PROXY_READ_TIMEOUT_SECONDS`（默认 120）
  - `DOWNLOAD_PROXY_FETCHER_TIMEOUT_SECONDS`（默认 10）
  - `DOWNLOAD_PROXY_CHUNK_SIZE_BYTES`（默认 524288）
  - `DOWNLOAD_PROXY_MAX_NETWORK_RETRIES`（默认 1）
- API 可开启 GZip 压缩（默认开启）：
  - `ENABLE_GZIP=true`
  - `GZIP_MINIMUM_SIZE=1024`
  - `GZIP_COMPRESS_LEVEL=6`
- 后端响应会附带 `X-Request-ID`，排查线上问题时可把该值连同时间戳提供给运维/开发快速定位日志。
- 可选结构化日志（便于 Loki/ELK 收集）：
  - `LOG_JSON=true`
  - `LOG_LEVEL=INFO`
- 默认开启基础安全响应头（可关闭）：
  - `ENABLE_SECURITY_HEADERS=true`
  - `SECURITY_HSTS_SECONDS=31536000`（仅 HTTPS + `COOKIE_SECURE=true` 时下发 HSTS）
- 生产环境建议设置：`COOKIE_SECURE=true` 且使用明确 `CORS_ORIGINS` 白名单；可开启 `SECURITY_STRICT_MODE=true` 强制拦截高风险弱配置。

## 数据库备份

在项目根目录执行：

```bash
bash scripts/backup_db.sh
```

可指定数据库路径与备份目录：

```bash
bash scripts/backup_db.sh /app/data/douyincehua.db /app/backups
```

可指定保留天数（第 3 个参数，默认 14 天）：

```bash
bash scripts/backup_db.sh /app/data/douyincehua.db /app/backups 30
```

## 数据库恢复

先停止 `backend` 与 `backend-worker`，然后执行：

```bash
bash scripts/restore_db.sh backups/douyincehua_20260314_010101.db.gz
```

恢复前会自动生成当前数据库快照，避免误操作。

## Alembic 迁移

在 `backend` 目录执行：

```bash
alembic upgrade head
```

创建新迁移：

```bash
alembic revision -m "your migration message"
```

## 建议的定时备份（crontab）

每天凌晨 3 点执行一次：

```bash
0 3 * * * cd /path/to/douyin-manager && bash scripts/backup_db.sh >> logs/backup.log 2>&1
```

## 持续集成（CI）

- 已提供 GitHub Actions 工作流：`/.github/workflows/ci.yml`
- 自动执行：后端测试、前端 lint/build、`docker compose config -q` 校验
