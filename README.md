# MetalFlow AI

Phase 1 提供本地 Sandbox SaaS 基础。使用 Next.js、FastAPI 和 PostgreSQL 验证双租户登录、权限与审计。

## 启动本地 Sandbox

启动 Docker Desktop，并确认 Docker CLI 指向本机 daemon。然后在本目录运行：

```bash
./scripts/dev.sh up
./scripts/dev.sh password
```

打开 [本地工作空间](http://localhost:3000)。选择 Sandbox A 或 Sandbox B，并使用上一步显示的合成密码登录。

| 合成账户 | 可用界面 |
|---|---|
| `owner@example.test` | 工作空间、用户和审计日志 |
| `admin@example.test` | 工作空间和用户 |
| `auditor@example.test` | 工作空间和审计日志 |
| `sales@example.test` | 工作空间 |
| `disabled@example.test` | 账号停用，登录失败 |

API 的 [就绪端点](http://127.0.0.1:8000/api/v1/health) 和 [OpenAPI](http://127.0.0.1:8000/openapi.json) 可从本机访问。启动脚本自动生成 `.env.sandbox`，保存数据库及种子账户凭据。请与对应 Docker 数据卷一起保留该文件。种子脚本会保留已有账号密码，重新生成环境文件不会轮换已有数据库的凭据。

```bash
./scripts/dev.sh status
./scripts/dev.sh logs
./scripts/dev.sh down
```

停止命令保留本地数据库卷。

## 验收

```bash
./scripts/verify-phase1.sh
```

该脚本使用随机 Compose 项目和临时数据库，执行双租户 API 与数据库测试、迁移降级、重新升级和复测。项目无需外部账号。完整状态、测试证据和已知问题见 [Phase 1 Delivery Report](reports/PHASE_1.md)。
