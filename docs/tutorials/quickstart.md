# 快速开始

## 环境要求

- Python 3.12+
- Node.js 22+
- PostgreSQL 16
- Redis 7+
- Qdrant 1.16+

## WSL + Docker 一键启动（推荐）

```bash
cp .env.example .env
# 编辑 .env，填写模型 API Key 和安全配置
./start_docker.sh
```

该脚本会构建应用镜像、启动并等待 PostgreSQL/Redis/Qdrant、执行数据库迁移，
再强制重建 FastAPI 与 Celery 容器。强制重建用于刷新 WSL bind mount，避免旧容器恢复后看不到源码。

## WSL 本地开发模式

需要让 FastAPI 和 Celery 直接运行在 WSL 中时，使用：

```bash
./start.sh
```

启动后访问：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- C端用户界面: http://localhost:8000/app
- B端管理后台: http://localhost:8000/admin

## 手动分步启动

如需手动配置开发环境，请参考 [本地开发环境搭建](./local-development.md)。

## 下一步

- 了解系统架构：[架构文档](../explanation/architecture/)
- 查看环境变量说明：[环境变量参考](../reference/environment-variables.md)
- 查看常用命令：[命令速查表](../reference/command-cheatsheet.md)
