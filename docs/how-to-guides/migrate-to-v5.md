# 迁移到星仓 AI v5

v5 将产品身份统一为“星仓 AI 智能客服 / Star Warehouse AI”。这次升级不修改 REST API 路径和数据库表结构，重点变化是包、进程、容器与可观测性标识。

## 标识映射

| 范围 | v4 及更早 | v5 |
| --- | --- | --- |
| 产品显示名 | `E-commerce Smart Agent` | `星仓 AI 智能客服` |
| 仓库目录/服务 slug | `E-commerce-Smart-Agent` / `ecommerce-agent` | `star-warehouse-ai` |
| Celery 应用名 | `ecommerce_agent` | `star_warehouse_ai` |
| LangSmith / OTel 服务 | `ecommerce-smart-agent` | `star-warehouse-ai` |

## 升级步骤

1. 拉取 v5 代码并备份 `.env`、PostgreSQL、Redis 和 Qdrant 数据。
2. 对照 `.env.example` 增加 `SERVICE_NAME=star-warehouse-ai` 与 `ALERT_DEDUP_PREFIX=star-warehouse-ai`。
3. 保留现有数据卷，重新构建应用和 Worker 容器。
4. 执行 `uv run alembic upgrade head`。
5. 验证 `/health` 返回 `version: v5.0`，并检查新日志和追踪的服务标签。

旧版 `PROJECT_NAME` 可以继续存在于原 `.env` 中，v5 会将已知旧值规范化为新显示名。自定义的企业部署名称不会被覆盖。

## 监控连续性

新数据统一写入 `star-warehouse-ai`。随仓库提供的 Grafana Dashboard 在整个 v5 生命周期内同时查询新旧标签，因此升级前的日志和指标仍可查看。建议在进入 v6 前完成历史数据保留或迁移策略。

## 回滚

回滚应用镜像前先确认旧版本能够读取当前数据库迁移。容器名称变化不会重命名 Compose 的逻辑数据卷；不要删除数据卷来处理命名差异。
