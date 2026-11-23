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

## Phase 2 Customer CRM

启动 Sandbox 后，以 `owner@example.test` 或 `admin@example.test` 登录并打开 **客户 CRM**。可创建客户、分配负责人、在 Customer 360 添加联系人和跟进任务。Sales 账户只看到自己负责的客户，可添加联系人和创建、完成跟进。

使用 Python 生成一份合成 Excel 工作簿（目标路径须是新文件）。

```bash
python3 backend/tests/crm_workbook.py /tmp/sandbox-customers.xlsx
```

在 **Excel 导入** 选择该文件并预览，再重新选择同一文件提交。疑似重复行默认跳过，逐条勾选可创建独立客户。导入界面需要 JavaScript。支持名为 `Customers` 的工作表，按 `name,country,website,contact_name,email,phone,linkedin_url` 顺序填写表头。数据单元格使用文本格式以保留电话号码前导零。每份文件上限 2 MiB，最多 500 条数据。

`./scripts/verify-phase1.sh` 运行当前全量 Sandbox 验收，包括 Phase 2。业务样本边界与验证证据见 [Phase 2 Delivery Report](reports/PHASE_2.md)。
