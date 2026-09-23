# Star Warehouse AI 文档中心

欢迎来到 Star Warehouse AI 的文档中心。本文档采用 [Diátaxis](https://diataxis.fr/) 框架组织，分为教程、操作指南、解释说明和参考资料四个象限。

## 快速导航

### 初学者
- [快速开始](./tutorials/quickstart.md) — 一键启动整个系统
- [本地开发环境搭建](./tutorials/local-development.md) — 从零开始配置开发环境

### 管理员与运维
- [部署边界与 profiles](./how-to-guides/deploy.md)
- [故障排查](./how-to-guides/troubleshoot.md)
- [Operations runbooks](./runbooks/README.md)
- [CI/CD and software supply chain](./how-to-guides/ci-supply-chain.md)
- [Final system view](./explanation/architecture/final-system-view.md)
- [Deterministic offline evaluation](./explanation/context-engineering/offline-evaluation.md)
- [Portfolio case study](./portfolio/CASE_STUDY.md)
- [Engineering evidence index](./portfolio/EVIDENCE_INDEX.md)
- [Final acceptance baseline](./engineering/FINAL_ACCEPTANCE.md)
- [Engineering interview guide](./interview/ENGINEERING_GUIDE.md)
- [Known limitations](./engineering/KNOWN_LIMITATIONS.md)
- [管理员后台操作指南](./how-to-guides/admin-operations.md)
- [迁移到 v5](./how-to-guides/migrate-to-v5.md)

### 开发者与架构师
- [系统架构](./explanation/architecture/) — 整体架构图、数据模型、交互流程
- [Prompt Engineering](./explanation/prompt-engineering/) — Prompt 现状、最佳实践与改进路线图
- [Context Engineering](./explanation/context-engineering/) — 上下文管理、预算控制与优化策略
- [Harness Engineering](./explanation/harness-engineering/) — Agent 评估框架工程、数据集、回归测试与监控体系
- [统一监控改造方案](./explanation/monitoring-unification-plan.md) — 历史规划与背景，不是当前运行手册

### 参考资料
- [API 文档](./reference/api.md)
- [Accepted architecture decisions](./engineering/DECISIONS.md)
- [Historical ADR-001–003](./reference/adr.md)
- [环境变量参考](./reference/environment-variables.md)
- [常用命令速查表](./reference/command-cheatsheet.md)
- [项目文件结构](./reference/project-structure.md)
- [技术栈详情](./reference/tech-stack-detail.md)

## 文档约定

- 每个目录下的 `README.md` 为该章节的索引页
- 所有技术细节尽量引用 [参考资料](./reference/) 中的共享文档，避免重复
- 若发现文档错误或链接失效，请提交 PR 修复

## 权威来源

| 领域 | 权威入口 |
| --- | --- |
| 项目与开发入口 | [`README.md`](../README.md) |
| 架构决策 | [`engineering/DECISIONS.md`](./engineering/DECISIONS.md) |
| 结构守护规则 | [`architecture/ARCHITECTURE_GUARDRAILS.md`](./architecture/ARCHITECTURE_GUARDRAILS.md) |
| 本地开发 | [`tutorials/local-development.md`](./tutorials/local-development.md) |
| 部署边界 | [`how-to-guides/deploy.md`](./how-to-guides/deploy.md) |
| 环境变量 | [`.env.example`](../.env.example) 与 [`reference/environment-variables.md`](./reference/environment-variables.md) |
| 测试 | [`AGENTS.md`](../AGENTS.md) 与 [`tests/AGENTS.md`](../tests/AGENTS.md) |
| Operations | [`runbooks/README.md`](./runbooks/README.md) |
| 当前执行状态 | [`engineering/PROJECT_STATE.md`](./engineering/PROJECT_STATE.md) |
