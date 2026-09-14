# 系统架构

本节从宏观到微观介绍 Star Warehouse AI 的系统架构。

- [架构守护规则](../../architecture/ARCHITECTURE_GUARDRAILS.md) — T02–T21 结构变更的权威边界与债务映射
- [Accepted decisions](../../engineering/DECISIONS.md) — 当前架构基线
- [Enterprise authorization](../../architecture/AUTHORIZATION.md) — tenant membership, roles,
  capabilities, route policy, revocation, and audit semantics
- [Secure browser session](../../architecture/SECURE_BROWSER_SESSION.md) — HttpOnly cookie,
  session-bound CSRF, exact Origin validation, logout, and WebSocket transport
- [Compliance lifecycle](../../architecture/COMPLIANCE_LIFECYCLE.md) — classification, retention,
  immutable audit, sensitive export approval, metrics, and operational runbooks
- [Dynamic Model Gateway](./model-gateway.md) — configured model routes, capability validation,
  normalized provider adapters, hermetic testing, and the T13/T14 failure-policy seam
- [可信请求/任务上下文](./task-runtime.md) — TaskContext、TaskEnvelope、绑定生命周期与当前直接投递限制
- [Transactional Outbox](./transactional-outbox.md) — atomic business intent, concurrent-safe relay, retry, and at-least-once semantics
- [RabbitMQ and Reliable Celery](./reliable-celery.md) — broker、queue、retry、receipt 与 DLQ 边界
- [架构概览](./overview.md) — 整体架构图与各层职责
- [LangGraph 工作流](./langgraph-workflow.md) — Supervisor-based 图编排
- [数据模型](./data-models/) — ERD 与各表字段说明
- [系统交互流程](./system-flows/) — 关键业务场景的时序图
- [技术栈分层](./tech-stack.md) — 六层技术架构
- [启动流程](./startup-flow.md) — 服务启动依赖
- [CI 与代码质量](./ci-quality.md) — 工具链与流水线
- [统一监控改造方案](../monitoring-unification-plan.md) — 历史规划与设计背景
