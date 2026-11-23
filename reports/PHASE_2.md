# Phase 2 Delivery Report

**日期** 2026-11-24 SGT

**状态** Customer CRM 已完成本地 Sandbox 验收。真实业务样本验收保留为 BLOCKED。Phase 3 等待 Product Owner 明确批准。

## 交付

- Excel 导入支持固定模板、工作簿校验、逐行预览、重复建议及显式确认。未确认的疑似重复行跳过；确认后创建独立客户。相同提交可幂等重放。
- Customer 360 汇总客户、当前负责人、联系人和跟进任务。Owner/Admin 管理本租户客户和负责人，Sales 仅可访问本人负责的客户并添加联系人、创建与完成跟进。负责人变更记录客户 ID 及前后负责人 ID。
- Alembic 迁移扩展现有 PostgreSQL 数据库，并以应用层约束、租户一致性外键和数据库强制 RLS 保护客户记录。[接口与权限合同](../tasks/PHASE_2.md)

## 验收与证据

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 本机 PostgreSQL 16 | PASS | 从已种入两租户的 Phase 1 升级，38 项通过。回滚至 Phase 1 后核对原有租户、账号及 CRM 表撤销，再升级，38 项再次通过。[日志](../harness/build/phase-2/postgres-crm.log) |
| Docker Compose 与 PostgreSQL 17 | PASS | 验收栈数据库、API、Next.js 构建和健康检查通过。完整测试在迁移回滚到 base 并重新升级前后各 38 项通过。[日志](../harness/build/phase-2/compose.log) |
| CRM 浏览器验收 | PASS | 4 组通过，验证 Customer 360、负责人、联系人、跟进、跨租户拒绝、Excel 错误文件拒绝和重复行人工确认，含 500 行且接近 2 MiB 的工作簿提交。[Chrome 日志](../harness/build/phase-2/browser.log) |
| Phase 1 浏览器回归 | PASS | 5 组通过，涵盖错误密码、角色、HttpOnly 会话、登出吊销及关闭 JavaScript 后的登录与退出。[日志](../harness/build/phase-2/foundation-browser-regression.log) |
| 质量与依赖 | PASS | Ruff、mypy、前端 ESLint 和 TypeScript 通过。本次新增 Python 运行依赖复检无已知漏洞，前端锁文件未变更。[质量日志](../harness/build/phase-2/quality.log) · [依赖扫描](../harness/build/phase-2/python-dependencies.log) |
| 独立代码与安全审查 | PASS（Sandbox 范围） | Reviewer 审查并复核全部修复，独立复跑 Excel 解析与匹配测试 15 项通过。[审查记录](../harness/build/phase-2/review.md) |
| 真实 Excel 数据和业务验收 | BLOCKED | 缺少 Product Owner 提供的脱敏客户样本、实际列映射与去重判定。 |
| GitHub 托管 CI 和生产验证 | NOT RUN | 本次执行环境为本机 Sandbox。 |

### 验收过程中的修正

- 初次集成的两项测试共用同一电话号码，正确触发重复提示。隔离合成测试数据后通过。[首次日志](../harness/build/phase-2/postgres-crm-initial.log)
- Docker 首跑中 Ruff 对项目首方模块分类与宿主不一致。固定同一份导入配置，复跑通过。[首次日志](../harness/build/phase-2/compose-initial.log)
- 浏览器首跑的模板生成代码使用了 Python 3.9 不支持的参数。修正后已验证本机 Python 3.9 生成模板，以及实际浏览器导入。[首次日志](../harness/build/phase-2/browser-initial.log)
- 独立审查指出的问题已修复并复核，包括共享字符串逻辑长度、完整预览状态对上传大小的影响、负责人变更审计和 LinkedIn 字段校验一致性。每个问题在三轮内解决。

## 启动与已知边界

执行 `./scripts/dev.sh up`，再运行 `./scripts/dev.sh password` 获取合成密码。以 Owner 或 Admin 登录 [本地工作空间](http://localhost:3000)，打开 **客户 CRM**。可用账号、模板生成命令和全量验收命令见 [README](../README.md)。

Sandbox 去重按固定字段精确提示，团队分配和业务身份规则仍待确认。导入界面需要 JavaScript，每份工作簿最多 500 条数据、2 MiB。真实业务样本验收之前应继续使用合成数据。Phase 0 业务流程与报价复算仍待确认。

## 分工及阶段控制

Database Agent 负责迁移与隔离。Import Agent 负责 Excel 解析、重复建议、提交与单测。Frontend Agent 实现 CRM 界面。Team Lead 实现 API、集成、复验和交付，独立 Reviewer 审查代码及安全并复跑导入测试。

四小时预算自约 06:00 SGT 起算，截止为 10:00 SGT，本次提前完成。会话工具没有全局硬超时，验证命令采用各自的超时。当前目录无 Git 元数据，检查点保存在 [启动记录](../harness/checkpoints/2026-11-24-phase-2-start.md)、[集成记录](../harness/checkpoints/2026-11-24-phase-2-integration.md) 与 [交付记录](../harness/checkpoints/2026-11-24-phase-2-delivery.md)。本次浏览器验收容器及合成数据卷已清理。[清理日志](../harness/build/phase-2/browser-cleanup.log)
