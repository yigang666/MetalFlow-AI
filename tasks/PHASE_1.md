# Phase 1 · SaaS Foundation

Product Owner 于 2026-11-24 批准本地基础框架、数据库、认证、RBAC、租户隔离和 Docker 开发环境。仅使用合成数据。部署和回滚限本地 Sandbox。外部身份供应商、真实邮件、邀请及业务权限规则保留待确认。

| 任务 | 依赖 | 文件所有权 | 状态 |
|---|---|---|---|
| P1-01 冻结基础合同 | 阶段批准 | Team Lead，本文及 docs | DONE |
| P1-02 数据库 | P1-01 | Database Agent，backend/alembic*、backend/db_admin/ | DONE |
| P1-03 API | P1-02 | Team Lead，backend/app/、backend/requirements* | DONE |
| P1-04 UI | P1-01 | Frontend Agent，frontend/ | DONE |
| P1-05 本地环境 | P1-01 | DevOps Agent，compose.yaml、backend/Dockerfile、backend/.dockerignore、scripts/、.github/ | DONE |
| P1-06 测试及独立审查 | P1-02 至 P1-05 | Team Lead 编写和执行测试，QA 与 Reviewer 独立复核 | DONE |
| P1-07 交付 | P1-06 | Team Lead，状态、报告及启动说明 | DONE |

## Sandbox 接口与权限

合成租户 ID 分别为 11111111-1111-4111-8111-111111111111 和 22222222-2222-4222-8222-222222222222。两个租户各有 owner@example.test、admin@example.test、sales@example.test、auditor@example.test、disabled@example.test。合成密码由启动环境生成和注入，容器仅在本机开放。

- POST /api/v1/auth/login 接收 tenant_id、email、password，返回 access_token、token_type。错误凭据或禁用身份返回 401。
- POST /api/v1/auth/refresh 使用 Bearer 会话轮换令牌，成功返回 200 及新令牌。POST /api/v1/auth/logout 吊销令牌，成功返回 204。会话期限 30 分钟，数据库只保存随机令牌哈希。每次请求重新读取活跃状态与角色。
- GET /api/v1/me 返回 id、tenant_id、email、role、permissions。GET /api/v1/tenant 返回 id、name。所有有效身份可访问。
- GET /api/v1/users 返回 {items:[{id,email,role,active}]}，权限为 users:read，授予 owner 和 admin。
- GET /api/v1/audit-logs 返回 {items:[{id,actor_id,action,outcome,occurred_at}]}，权限为 audit:read，授予 owner 和 auditor。两个列表均按 limit（默认 50、最大 100）及 offset 分页。
- GET /api/v1/health 公开，用于就绪检查。受保护端点在未认证时返回 401，在已认证但权限不足时返回 403。业务查询显式限制租户且数据库 RLS 独立兜底。仅登录请求可选择待认证的租户，令牌中的租户选择子须与同租户已保存会话相匹配。
- Sandbox 用户和角色由种子创建。邀请、用户写接口、团队和业务角色接到具体资源的规则等待确认。

P1-02 和 P1-03 的本机验收证据见 [PostgreSQL 与 API 测试](../harness/build/phase-1/postgres-api.log)。前后端集成与外部于实现者的审查在 P1-06 记录。

P1-04 至 P1-07 的测试、审查及阶段门禁见 [Phase 1 Delivery Report](../reports/PHASE_1.md)。GitHub 托管 CI 为 NOT RUN，本地执行通过。
