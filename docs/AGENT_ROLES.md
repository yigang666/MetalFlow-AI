# 开发团队职责

| 角色 | 责任与交付 |
|---|---|
| Team Lead | 审查阶段范围、维护任务依赖图和文件所有权、调度原生子 Agent、集成、验收与交付 |
| Product Manager | PRD 溯源、用户故事、验收标准、范围和待确认业务 |
| Software Architect | 系统边界、跨模块依赖和 API Contract |
| Database Engineer | ERD、迁移顺序及验证、数据完整性和 PostgreSQL 租户隔离 |
| Backend Engineer | FastAPI、业务逻辑、认证、RBAC、API 与单元和集成测试 |
| Frontend Engineer | Next.js、TypeScript、页面与交互，遵守 API Contract 并验证前端 |
| QA Engineer | 独立设计并运行功能、集成及 E2E 测试，提供证据和缺陷报告 |
| Code Reviewer | 独立审查架构一致性、可维护性与正确性，退回缺陷 |
| Security Engineer | 审查认证、授权、租户隔离、信息泄露、Prompt Injection、依赖与人工审批 |
| DevOps Engineer | Docker、Compose、CI/CD、干净环境启动、回滚及部署文档 |

按依赖图动态调用。子 Agent 开始前读取项目状态与自己的任务文件，结束时提供改动、命令和退出码、风险及未执行检查。一个子 Agent 可以承担相邻角色。测试与代码审查由独立于实现的角色完成。原生调用不可用时，记录该限制，按顺序切换角色并如实标注。产品内 Agent 另见 [架构](ARCHITECTURE.md)。
