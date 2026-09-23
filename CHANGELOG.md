# Changelog

## [Unreleased] - V1.2 Project Bootstrap & Documentation Consolidation

### Changed

- Consolidated local/UAT initialization into one production-guarded, idempotent bootstrap.
- Added persisted tenant, identity, order, refund/review, complaint, configuration, knowledge, and
  asynchronous-delivery verification data using the current model/runtime boundaries.
- Made Alembic, least-privilege PostgreSQL role verification, real knowledge ingestion, and
  full-stack verification part of the canonical Docker startup.
- Rewrote the reviewer/developer README, local-development guide, and environment reference from
  the current architecture and validation evidence.
- Removed the destructive random bulk seeder and one proven unrouted historical admin page while
  preserving compatibility wrappers and historical engineering evidence.

This V1.2 label is a change baseline. The package semantic version remains `5.0.0`.

本项目遵循语义化版本。此文件记录面向使用者的重要变化。

## [5.0.0] - 2026-09-05

### Changed

- 项目统一升级为“星仓 AI 智能客服 / Star Warehouse AI”。
- Python 包、Celery、容器、数据库连接、追踪、日志、告警和监控标识统一为 `star-warehouse-ai`。
- 客户服务台与运营管理中心统一品牌文案和视觉呈现。
- README 与文档中心按原生 AI 全栈架构重新组织。
- GitHub Actions 拆分为品牌文档、后端质量、后端测试、前端和 Docker Smoke 分层门禁。

### Compatibility

- REST API 路径与数据库结构保持不变。
- 已知旧版显示名称会在配置加载时迁移为新名称。
- Grafana 查询在 v5 生命周期内兼容旧服务标签。
