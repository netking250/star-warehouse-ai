# 星仓AI智能客服改造路线图

本路线图将企业化改造拆为六个可独立验收的版本。项目定位为企业 AI 客服中台；订单、商品、支付、库存等业务系统仍是权威数据源。

## 当前实施状态

- V1 已完成：品牌、用户工作台、运营控制台和统一视觉基线。
- V2.1 已完成：统一 `AuthContext`、租户声明、RBAC 角色/scope、JWT `aud/iss/jti`、会话上下文和用户表身份字段。
- V2.2 已完成：业务表租户迁移、查询/写入强制隔离、Redis/Qdrant 命名空间、Token 即时吊销与企业 OIDC IdP 适配。
- V3 待实施：业务系统 Port/Adapter、统一 DTO 与上游韧性策略。

## V1：品牌与体验基线

- 全局更名为“星仓AI智能客服”。
- 重构用户登录、对话工作台、快捷服务和响应状态展示。
- 重构管理登录与运营控制台导航。
- 建立统一品牌组件、色彩、圆角、阴影和响应式规范。
- 固化后端、前端构建、类型与测试基线。

验收：用户端与管理端品牌一致，桌面和移动端主要界面可用，前端构建、Lint 和测试通过。

## V2：身份、租户与权限

- 引入 `AuthContext`：`tenant_id`、`user_id`、`roles`、`scopes`、`session_id`、`correlation_id`。
- 建立管理端 RBAC、Token 刷新/吊销以及 SSE/WebSocket 权限复验。
- PostgreSQL、Redis、Qdrant 完成租户命名空间与强制过滤。

验收：跨租户测试全部被拒绝，所有访问可追溯到租户与用户。

### V2.2 交付说明

- 所有平台 SQLModel 表统一继承 `TenantScopedModel`；ORM 查询自动注入当前租户条件，跨租户写入在 flush 前拒绝。
- Redis 键使用 `{environment}:{tenant_id}:...`，Qdrant collection 使用环境前缀且 payload/query 强制携带 `tenant_id`。
- `POST /api/v1/logout` 将当前 `jti` 写入 Redis 撤销表；REST、SSE、用户及管理员 WebSocket 均复验撤销状态。
- `POST /api/v1/enterprise/login` 通过可配置 OIDC UserInfo adapter 验证企业身份，并仅允许兑换已绑定、启用的本地租户账号。
- 部署前执行 Alembic 升级，并为现有 Qdrant 数据补齐租户 payload 后重新索引；旧的无租户向量不会被检索。

## V3：业务系统适配器

- 建立 Identity、Product、Inventory、Order、Payment、Invoice、Logistics、Cart、Refund、Notification Port。
- 提供 Mock、Sandbox、Production 实现及统一 DTO、错误码、超时、重试、熔断和审计。
- 先接只读查询，再接购物车等低风险写操作。

验收：上游异常有契约测试，Agent 无法绕过 Adapter 修改业务数据。

## V4：知识库生命周期

- 使用对象存储打通 API 与 Worker 文件共享。
- 建立文档版本、摄取任务、切片、发布记录和权限策略模型。
- 支持 UUID point、内容 Hash 幂等、审批、发布、回滚、删除清理和引用溯源。

验收：知识上传、解析、发布、检索、更新、删除形成闭环，未授权召回为零。

## V5：受控写操作与安全合规

- 高风险命令统一为 `preview → confirm → execute`。
- 增加确定性规则、幂等、补偿、人工审核和状态恢复校验。
- 完成 PII 脱敏、数据保留、导出删除、密钥管理和安全测试。

验收：高风险操作全部可确认、可幂等、可审计、可补偿。

## V6：生产化、观测与灰度

- 完成生产网络隔离、队列拆分、健康检查、滚动发布和兼容迁移。
- 打通 Trace、指标、日志、告警、Runbook、备份和恢复演练。
- 建立 CI/CD 质量门禁，并依次执行 Shadow、内部、5%、25%、50%、100% 灰度。

验收：满足既定 SLO，具备自动回滚、模型降级和人工客服接管能力。
