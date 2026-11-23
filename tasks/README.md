# Phase 0 开发 Harness 与项目规划

## 范围与非目标

在已有云环境中建立可恢复的开发治理、PRD 提取、候选技术契约与计划，真实验证一次失败、修复、恢复和报告生成。业务验证按照 PRD 保留，依赖 Product Owner 提供脱敏样本与确认。本阶段不实现 SaaS 业务、不接入真实服务、不进入 Phase 1。

## 故事与验收

- 作为 Product Owner，我能追溯需求、验收和 TBD。验收时应对照 HTML 正文和脚本 API，并单独标明需业务验证的事项。
- 作为开发 Agent，我能从仓库恢复任务、前置依赖、负责人、决策和下一步。验收时应能从 AGENTS.md 找到这些信息。
- 作为 QA，我能独立复跑确定性失败、修复、重测和报告。验收记录应包括相同测试、退出码、轮次和恢复状态。
- 作为 Product Owner，我能审查 Phase 1 计划和是否放行。验收时应看到范围、任务依赖、测试计划、完成定义与人工门禁。

## 任务图

| 任务 | 前置 | 负责人 | 文件或证据 |
|---|---|---|---|
| P0-01 环境和原始 PRD | 无 | Team Lead | 构建日志 |
| P0-02 产品与路线图 | P0-01 | Product Manager | PRD、ROADMAP、OPEN_QUESTIONS |
| P0-03 技术契约 | P0-01 | Architect / Database | ARCHITECTURE、DATABASE_ERD、API_CONTRACTS、SECURITY |
| P0-04 开发规则与恢复 | P0-01 | Team Lead | AGENTS、角色、开发流程、决策、状态 |
| P0-05 烟测 harness | P0-01 | Harness 工程 Agent | harness/smoke |
| P0-06 独立验证与缺陷修复 | P0-02、03、04、05 | QA、Reviewer、Security、Team Lead | 构建日志、烟测产物 |
| P0-07 交付及人工门禁 | P0-06 | Team Lead | Phase 0 交付报告 |
| P0-B1 业务流程及报价样本验收 | 脱敏样本、业务规则、业务负责人 | Product Owner | 业务确认及样本计算证据 |

## 测试计划与完成定义

核查需求覆盖和 Markdown 链接，进行原生委派、失败重测、跨进程恢复和报告验证，独立复核代码、结果及安全边界。记录应用质量门的实际状态。规划与 harness 的验收以证据和交付报告为准。PRD 的业务验收须另外具备业务负责人确认及样本计算证据。Phase 1 须经 Product Owner 批准。
