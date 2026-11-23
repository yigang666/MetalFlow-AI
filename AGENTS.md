# MetalFlow AI 开发规则

先读 [当前状态](harness/context/STATE.md)、[业务需求](docs/PRD.md)、[阶段计划](docs/ROADMAP.md) 和 [任务图](tasks/README.md)。按任务读取架构、数据库、API 与安全文档。需求以 [HTML PRD](MetalFlow_AI_Product_Owner_PRD_v1.html) 和 Product Owner 后续书面确认作为依据。业务不明确时登记为 TBD，请勿推断。低风险、可逆的技术选择记录在 [决策记录](docs/DECISIONS.md)。

遵循 [开发流程](docs/DEVELOPMENT_WORKFLOW.md) 和 [Agent 职责](docs/AGENT_ROLES.md)。任务只能在前置依赖完成且处于已批准阶段时启动。每项任务指定文件所有权。有冲突风险时，经 Team Lead 协调使用独立分支或 worktree。Team Lead 负责集成。按 [API 契约](docs/API_CONTRACTS.md) 协同前后端，迁移指定唯一负责人及执行顺序。

开发仅使用 mock 数据与 sandbox。以下操作须 Product Owner 批准后执行：修改核心业务规则、调整已批准架构、扩大范围、访问真实客户数据、使用生产凭据、创建付费资源、发送真实客户邮件、修改或删除生产数据、部署生产、合并 main。有未解决的高风险安全问题时暂停相关操作。始终保留 sandbox 和审批机制。

仅凭实际证据把任务标为 DONE。未经执行的检查记为 NOT RUN。每个失败最多自动修复三轮，仍失败则记录 BLOCKED，并继续独立任务。每个阶段交付报告后等待 Product Owner 批准下一阶段。
