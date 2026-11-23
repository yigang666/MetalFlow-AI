# Phase 1 Delivery Report

**日期** 2026-11-24 SGT  
**交付状态** SaaS Foundation 本地 Sandbox 已实现并通过验收，等待 Product Owner 审阅。Phase 2 等待明确批准。

## 已交付

- Next.js 工作空间支持双租户登录、退出和按角色显示用户与审计日志。浏览器会话使用 HttpOnly、SameSite=Strict Cookie，登录及登出校验来源。
- FastAPI 提供登录、会话轮换和吊销、当前身份、租户、用户列表、审计列表、就绪检查及 OpenAPI。四种固定基础角色的授权矩阵已由 API 强制执行。[接口和权限合同](../tasks/PHASE_1.md)
- PostgreSQL/Alembic 提供租户、用户、会话和审计四张表。应用查询和数据库 RLS 同时限定租户，跨表关系使用租户外键。迁移管理员和受限运行账户分离。种子创建两个合成租户。
- Docker Compose 提供本地开发栈、分离的迁移服务和可销毁的验收环境。GitHub Actions 作业提供 PR 或手动触发的 Sandbox 验证配置。[启动说明](../README.md) · [CI 配置](../.github/workflows/phase1-sandbox.yml)

## 验收与证据

| 检查 | 状态 | 运行结果与证据 |
|---|---|---|
| PostgreSQL 16 本机验证 | PASS | 初始迁移及幂等种子后，15 项集成通过。降级、升级并重建种子后，15 项再次通过。[日志](../harness/build/phase-1/postgres-api.log) |
| PostgreSQL 17 Docker 验收 | PASS | 生产模式容器构建且数据库、API、前端健康。隔离双租户测试 15 项和单测 3 项均通过。降级后检查四张表已撤销，重新升级后再通过 18 项。包含双向隔离、无租户上下文、越界写入与审计不可变、角色/停用实时生效、会话轮换并发、过期、吊销和分页。[日志](../harness/build/phase-1/compose-verify.log) |
| Chrome 端到端 | PASS | 5 组检查通过。验证错误密码、A 租户 Owner、B 租户 Sales/Auditor、会话 Cookie、服务端吊销以及关闭 JavaScript 后的同源登录/登出。[日志](../harness/build/phase-1/browser-smoke.log) |
| 本地应用镜像回滚 | PASS | 在同一隔离数据库上部署候选 API 和 Web 镜像、切回各自上一组镜像、再恢复候选镜像。每步核验实际运行的镜像 ID、健康状态并重跑 5 组浏览器检查。[日志](../harness/build/phase-1/image-rollout.log) |
| 代码质量 | PASS | 后端 Ruff、mypy 检查 6 个源文件、3 项独立单测；前端 ESLint 和 TypeScript；Shell 和浏览器脚本语法。[日志](../harness/build/phase-1/quality-gates.log) |
| 依赖扫描 | PASS | Python 运行依赖复检无已知漏洞，npm 全量审计报告 0 项。[Python](../harness/build/phase-1/python-dependencies.log) · [npm](../harness/build/phase-1/frontend-dependencies.log) |
| 独立代码和安全审查 | PASS（Sandbox 范围） | 审查及修复复核独立于实现。未发现未解决的实质性缺陷。[审查记录](../harness/build/phase-1/review.md) |
| GitHub 托管 CI | NOT RUN | 本地执行了对应验收脚本。当前工作区无 Git 元数据，未触发远端作业。 |

Docker 版本为 29.2.1。本机临时 PostgreSQL 实例已停止，浏览器验收项目及其合成数据卷已清理。[清理日志](../harness/build/phase-1/browser-stack-cleanup.log)

## 修复与已知边界

- 依赖扫描发现初始 Starlette 版本存在已知安全公告，升级 FastAPI 和 Starlette 后复检通过。原生 PostgreSQL 测试起初因试验实例的编码失败，显式使用 UTF-8 后复跑通过。
- 受限环境中的原生 Turbopack 构建因工作进程端口被限制而失败。切换至 Next.js 的 Webpack 构建，Docker 产物构建和实际运行通过。
- 当前仅提供固定角色和合成种子账号。真实身份提供方、邀请规则、用户写入、团队与业务角色、限速及会话保留策略待确认。禁用期间会拒绝已有会话。未来若通过账户管理重新启用账号，需要确定旧会话的吊销策略。
- Phase 0 的业务流程确认、脱敏报价样本复算和企业邮箱 Sandbox 授权仍待业务方处理。外部 Sandbox、生产部署和真实数据验证未执行。

## 分工与检查点

- Database Agent 交付 PostgreSQL schema、RLS、迁移及种子。Team Lead 集成、终检并修正数据库脚本的类型边界。
- Frontend Agent 交付工作空间界面、认证表单和容器构建。DevOps Agent 交付 Compose、开发脚本、隔离验证与 CI。
- 独立 Reviewer 审查应用、容器和安全边界，复核修复。独立 QA 复跑前端质量检查并核对集成和浏览器证据。Team Lead 实现 API，运行迁移、Docker 和浏览器验收。
- 本次以约 05:20 SGT 为起点，09:20 SGT 为四小时截止线，提前完成。当前会话工具没有全局硬超时，验收命令和 CI 使用各自的超时。每个问题的自动修复均在三轮内。
- 工作区来自 Phase 0 文件包。Git 提交不可用，检查点保存在 [启动](../harness/checkpoints/2026-11-24-phase-1-start.md)、[集成](../harness/checkpoints/2026-11-24-phase-1-integration.md) 和 [交付](../harness/checkpoints/2026-11-24-phase-1-delivery.md)。

## 启动

在本机 Docker Desktop 已运行时，执行 `./scripts/dev.sh up`。运行 `./scripts/dev.sh password` 获取合成密码，使用 [本地工作空间](http://localhost:3000) 的 Sandbox A 或 Sandbox B 登录。账号与命令见 [README](../README.md)。
