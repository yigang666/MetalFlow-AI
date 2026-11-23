# 开发路线图

每阶段开始前确认 Scope、Non-goals、Task List、Dependencies、Acceptance Criteria、Test Plan 和 Definition of Done。结束时将 Delivery Report 存入 `reports/`，由 Product Owner 决定是否进入下一阶段。Phase 2–8 的业务范围以对应阶段批准为准，原文阶段目标与验收如下。

| 阶段 | 范围及交付 | 原文验收 |
| --- | --- | --- |
| 0 · W1 | Development Harness and Project Planning，业务调研、样本、报价规则、邮箱验证，PRD、ERD、数据字典 | 业务负责人确认流程和样本计算结果 |
| 1 · W2 | SaaS Foundation，登录、RBAC、审计、Docker、CI/CD | 两个测试租户无法互访，部署与回滚成功 |
| 2 · W3 | Customer CRM，Excel 导入、去重建议、Customer 360、负责人和任务 | 样本导入可核对，疑似重复需人工确认 |
| 3 · W4 | Communications and Email Integration，邮箱授权、线程同步、客户关联、AI 总结和草稿 | 同步可重试且不重复，草稿经审批才能发送 |
| 4 · W5 | Products, Suppliers and Market Intelligence，规格、供应商报价、行情、汇率 | 来源、单位、时间戳可追溯 |
| 5 · W6 | Quotation Center and Pricing Engine，快照、利润规则、审批、PDF | 与业务样本一致，历史报价不变，审批权限正确 |
| 6 · W7 | Document and Order Management，轻量订单、PI/合同草稿、付款节点、提醒，属 P1 可选 | 转订单不重复，到账由人工依据可信记录确认 |
| 7 · W8 | Pilot, UAT and Production Readiness，2–3 人试点、UAT、安全检查和培训 | 业务签字、核心流程通过、恢复演练完成 |
| 8 · Post-MVP | SaaS Expansion，WhatsApp、LinkedIn、市场数据、订阅、BI | 基于试点价值和渠道授权逐项验收 |

原文估算为全职约 8 周、兼职约 12–16 周，依赖业务配合、邮箱接口、数据质量、报价规则和安全范围。具体排期 TBD。 [HTML PRD](../MetalFlow_AI_Product_Owner_PRD_v1.html)

## Phase 0 · Development Harness and Project Planning

| 计划项 | 内容 |
| --- | --- |
| Scope | 核对环境和需求来源，建立知识库、开发规则、任务和检查点规范，演练委派、失败、修复、状态保存和报告生成。 |
| Non-goals | 产品实现、生产部署、启动 Phase 1。 |
| Stories | Product Owner 能审阅阶段范围、缺口和证据。Team Lead 能从检查点恢复并追踪任务。QA 能独立重现失败和通过状态。 |
| Dependencies | 业务流程确认和报价复算依赖业务负责人及脱敏样本。邮箱验证依赖供应商和 Sandbox 授权。 |
| Acceptance Criteria | 文档记录全部指定的需求类别，已确认事项可追溯，待确认项标记 TBD。PRD 业务验收由业务负责人确认工作流和样本计算。使用真实子 Agent 委派演练，真实测试失败后由开发角色修复，独立 QA 重跑并留下检查点与报告。 |
| Test Plan | 检查文档链接和检查点，核对失败及重测证据，验证停止门禁，执行独立代码及安全审查。 |
| Definition of Done | 完成上述验收，保存结果、阻塞原因及后续动作，交付报告与 Phase 1 实施计划。缺失业务样本或授权时，业务相关验收项保持 BLOCKED，未执行的验证标记 NOT RUN。 |
| Delivery Report | 以 `reports/` 中对应报告为准，记录通过、失败、NOT RUN 和剩余审批事项。 |

## Phase 1 · SaaS Foundation 实施计划草案

2026-11-24 已批准本地 SaaS Foundation 并完成 Sandbox 验收。实际实施范围及剩余验证见 [Phase 1 Delivery Report](../reports/PHASE_1.md)。Phase 2 等待 Product Owner 明确批准。

### 前置条件与边界

Product Owner 批准进入 Phase 1 后才启动。开始实现前确认 Phase 1 的产品范围、租户模型、身份机制与角色矩阵。下述工作项是基于开发指令的技术实施提案，具体接口、表结构和授权策略须在实现前确定。

- **Scope** 包括可本地启动的 FastAPI、Next.js、PostgreSQL 基础，登录、认证、RBAC 和审计基线，租户隔离、迁移、Docker、CI/CD 和全栈验证。
- **Non-goals** 包括 CRM、邮件、市场情报、报价、订单及产品 Agent 的业务实现。生产部署和付费资源申请受独立审批约束。

### 用户故事及拟议验收

| 故事 | 可验证验收 |
| --- | --- |
| 开发者能在 Sandbox 启动应用 | 按仓库文档从干净环境启动，迁移执行成功，前端与 API 完成代表性请求。 |
| 管理人员能追溯关键操作 | 审计记录可按授权读取，拒绝跨租户访问，日志不泄露凭据。 |
| DevOps 能验证部署和回滚 | 使用 Sandbox 验证部署到新版本和回滚到前一版本，保留可复查的应用及迁移检查证据。 |
| 用户能按授权访问所属租户的资源 | 使用经确认的角色矩阵执行允许及拒绝用例。未认证、角色权限不足及跨租户请求按 API Contract 返回结果。 |
| QA 能在合并前发现租户隔离回归 | 用两个 Mock 租户验证访问边界，确认响应及错误信息无跨租户数据。代码与安全独立审查有记录。 |

### 任务和依赖

| ID | 负责人 | 前置依赖 | 交付物 |
| --- | --- | --- | --- |
| P1-01 | Product Manager、Architect、Security | Phase 1 获批，相关业务范围及安全约束可确认 | Scope、验收、身份和租户边界、RBAC 矩阵与 API Contract |
| P1-02 | Database Engineer | P1-01 | ERD、迁移顺序、测试数据与隔离约束 |
| P1-03 | Backend Engineer | P1-01、P1-02 | FastAPI 认证、授权、租户上下文、审计及契约实现 |
| P1-04 | Frontend Engineer | P1-01 | Next.js 登录与权限交互，使用已确认的契约 |
| P1-05 | DevOps Engineer | P1-01 | 开发环境、Docker Compose、CI 及 Sandbox 部署回滚演练 |
| P1-06 | QA、Code Reviewer、Security | P1-02 至 P1-05 | 干净环境验证、测试、独立审查与缺陷记录 |
| P1-07 | Team Lead | P1-06 通过 | 检查点及 Phase 1 Delivery Report，等待验收 |

P1-02、P1-04、P1-05 在契约确定后可并行。Database Engineer 负责迁移顺序。QA 可提前编写验收用例，最终测试在集成后执行。

### 测试计划与完成标准

- 编排干净实例启动，经健康检查及已确认的代表性前后端请求验证。执行前后端 Lint、类型检查、单元测试和构建。
- 对 PostgreSQL 验证空库迁移及已批准的升级路径。执行 API 集成、授权及租户隔离负向测试、审计访问边界和登录 E2E。验证 Sandbox 部署及回滚，付费资源或生产动作另行审批。
- 独立代码与安全审查覆盖授权绕过、敏感信息和租户边界。每项失败均按项目流程修复重测或标记 BLOCKED。
- 所有必要验收有运行证据。交付报告记录命令、结果、审查、未执行项目及运行方式，提交 Product Owner 验收后等待后续授权。

## Phase 2–8 条件计划

以下是阶段范围获批前的计划。各阶段的 Scope 与验收见路线图总表。每阶段共同完成定义为满足对应验收、执行适用质量门、记录失败及阻塞、通过独立代码和安全审查，并交付 Markdown 报告给 Product Owner。交付报告在各阶段实际验证后生成。

| 阶段 | 前置依赖 | 任务安排 | 非目标 | 验证计划 |
| --- | --- | --- | --- | --- |
| 2 | Phase 1 验收、脱敏 Excel、字段与身份规则 | 导入校验、去重建议、Customer 360、负责人和任务 | 自动合并疑似重复、邮件同步 | 核对样本、无效行、重复导入与人工去重路径 |
| 3 | Phase 2 验收、邮箱 Sandbox 授权 | 连接、同步线程、关联客户、总结和草稿 | 真实邮件自动发送、未经授权渠道采集 | 重试幂等、验签、审批和不可信正文处理 |
| 4 | Phase 3 验收、规格与授权数据源 | 规格和供应商、供应商报价、行情与汇率 | 用行情替代工厂成本、未经授权抓取 | 溯源、单位、报价时效、同步重试与租户权限 |
| 5 | Phase 4 验收、已确认规则与报价样本 | 确定性定价、全量快照、审批、PDF | 自动对外承诺、自动发报价 | 样本复算、历史不可变、审批拒绝与 PDF 核对 |
| 6 | Phase 5 验收、P1 范围获批、脱敏订单样本 | 报价转单、PI/合同草稿、付款节点、交货提醒 | 完整报关、银行和物流集成 | 幂等转单、交付提醒、到账确认权限 |
| 7 | 核心 P0 通过、已获准试点环境和参与者 | 培训、试点、UAT、恢复演练与安全检查 | 未获准生产部署，P1 模块不阻塞核心 P0 | 业务签字、端到端试点、备份还原与安全验证 |
| 8 | Phase 7 验收、试点证据、各渠道授权 | 逐项评估 WhatsApp、LinkedIn、市场数据、订阅、BI | 未批准商业规则、未经授权的渠道自动化 | 按获批项目验证功能、隐私及权限，核对试点 KPI |
