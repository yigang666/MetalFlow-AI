# 技术与部署架构

来源为 [HTML PRD §05、§09、§12](../MetalFlow_AI_Product_Owner_PRD_v1.html)。技术选型为设计基线。Phase 1 本地 Sandbox 已实现，交付边界与验证证据见 [Delivery Report](../reports/PHASE_1.md)。

## 模块边界

| 模块 | 所有权 |
| --- | --- |
| SaaS 基础 | 登录、租户上下文、团队与用户、RBAC 和审计 |
| CRM | 客户、联系人、身份解析、归属、跟进和 Customer 360 |
| 通信 | 连接、同步、线程、消息、附件、关联、总结和回复草稿 |
| 产品与市场 | 产品规格、供应商、报价来源、行情与汇率 |
| 报价 | RFQ、规格检查、确定性定价、不可变版本和审批 |
| 单据与订单 | 报价 PDF、PI/合同草稿、订单、付款节点、交付提醒 |
| 应用 AI | 受控检索、解析、生成建议、工具路由和审批交接 |

采用模块化单体。Next.js、TypeScript、Tailwind CSS、shadcn/ui 负责前端。Python/FastAPI 承载服务，PostgreSQL 与 SQLAlchemy/Alembic 管理持久化及迁移。初期使用 Python workflow，后续评估 LangGraph。异步候选为 Celery + Redis 或托管队列。AI 可配置 Claude API 或 OpenAI API。文件使用 S3，PDF 采用 HTML + WeasyPrint。初期排除 Kubernetes、Kafka、微服务、MongoDB、复杂 RAG 和向量数据库。

邮箱供应商确认后选择官方 API 或 IMAP/SMTP/OAuth。WhatsApp 采用官方 Business Platform。LinkedIn 初期采用授权工作流、人工导入和草稿，禁止未经授权登录、抓取或群发。

## 应用 Agent

| Agent | 职责 |
| --- | --- |
| Orchestrator | 按需路由、并行与汇总，简单任务调用所需能力 |
| Customer Intelligence | 客户理解、邮件摘要、可追溯记忆和后续建议 |
| Market Intelligence | 授权行情、汇率和供应商报价 |
| Quotation | RFQ 解析、规格校验、调用确定性计算和利润风险提示 |
| Document | 邮件草稿、PDF 报价与 PI/合同草稿 |
| Trade Operations（后续） | 订单、付款节点和交货提醒 |

工具层按发起用户权限和租户校验每次动作。对外发送与关键承诺需要人工控制。价格计算由确定性 Pricing Engine 完成。开发 Agent 职责见 [AGENT_ROLES.md](AGENT_ROLES.md)。

## AWS 部署策略

拟采用 Docker 和 AWS。用户经 TLS/WAF/ALB 到 ECS Fargate 前后端，数据层为私有子网 RDS PostgreSQL、S3 与队列，并按需访问授权模型提供方。采用 VPC、Security Groups、Route 53、ACM，S3 使用 SSE-KMS 和租户路径访问控制。选用 Celery 时考虑 ElastiCache。Secrets Manager 或 SSM Parameter Store 管理凭据，OAuth token 加密。使用 CloudWatch 日志、指标和告警，启用 RDS PITR、S3 Versioning 与 Lifecycle。流水线目标为 GitHub Actions → ECR → ECS。投产前计划隔离安全测试、恢复演练、事件响应及隐私删除流程。

AWS Region、预算、跨境处理和中国访问体验均为 TBD。App Runner 可用性与 Vercel 数据适配性待验证。Phase 1 在本地或经授权的 Sandbox 验证部署和回滚。付费资源及生产部署需 Product Owner 批准。
