# CI 与代码质量

## 质量工具链

| 工具 | 用途 | 配置位置 |
|---|---|---|
| ruff | Lint + Format | `.pre-commit-config.yaml`, `pyproject.toml` |
| ty | 类型检查 | `.pre-commit-config.yaml` |
| pytest | 单元/集成测试 | `pyproject.toml` |
| GitHub Actions | CI 流水线 | `.github/workflows/ci.yml` |

## CI 流程

现有 `.github/workflows/ci.yml` 分为：

1. Brand/docs identity and local-link validation.
2. Python 3.12 + uv 0.6.5 backend lint, format, and type checks.
3. Isolated PostgreSQL/Redis/Qdrant backend tests with the 75% coverage gate.
4. Node.js 22 frontend format, lint, unit, build, and Playwright checks.
5. Docker image/build/startup health smoke using the canonical Compose file.

Evaluation、monitoring 和 performance 使用独立 workflow。RabbitMQ 是运行时 broker；
普通 pytest workflow 使用显式 `memory://` test transport，真实 broker 证据只在专用
`test_` RabbitMQ vhost 中执行。

## 本地质量检查

```bash
# 安装 pre-commit hook
pre-commit install

# 手动检查
uv run ruff check app tests --fix
uv run ruff format --check app tests
uv run ty check --error-on-warning app tests
```

> 前端代码质量检查请参考 [常用命令速查表](../../reference/command-cheatsheet.md)。
