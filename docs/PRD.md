# MetalFlow AI 产品需求

需求原文为仓库中的 MetalFlow AI Product Owner PRD v1.0，日期为 2026-11-24。本文按原文各章节提取，经确认的业务背景与设计草案均沿用原有状态。开发阶段的批准以 Product Owner 的决定为准。 [HTML PRD](../MetalFlow_AI_Product_Owner_PRD_v1.html)

## 产品愿景和已确认业务背景（§01、§02、§14）

MetalFlow AI 是面向金属贸易公司的 SaaS 工作空间，用于维护既有客户关系，提高报价效率和准确性，管理外贸文件和订单，并将 Excel、Email、WhatsApp、LinkedIn 的零散信息沉淀为可追溯的团队工作记录。试点面向解放公司，长期可将成熟能力提供给其他金属贸易公司。

| 维度 | 业务背景 |
| --- | --- |
| 企业与市场 | 陕西西安金属贸易公司，上游工厂在陕北，面向美国、欧洲、东南亚、日本等市场 |
| 团队 | 10–30 人 |
| 产品 | Magnesium、Aluminum、Magnesium Alloy、Aluminum Alloy |
| 贸易条款 | FOB、CIF、CFR |
| 客户及渠道 | 老客户为主，使用 Email、WhatsApp、LinkedIn |
| 现行管理 | Excel，人工制作报价单 |
| 定价 | 结合工厂报价与市场行情，具体供应商报价渠道 TBD |
| 邮箱 | 第三方企业邮箱，供应商 TBD |
| 询价量 | 10–50/月，统计口径及补充数字 30 的含义 TBD |

## 业务流程和功能（§03、§14）

主流程为 Excel 导入 → Customer 360 → Email / WhatsApp 沟通 → AI 总结和客户记忆 → 动态报价 → PDF 草稿和人工审批 → 发送与跟进 → 订单管理。

| 流程 | 功能和控制 |
| --- | --- |
| Customer Lifecycle | 采集沟通，形成 Customer 360 和 Relationship Brief，由业务员维护关系。保留采购与沟通历史、采购规格偏好、报价、付款习惯及跟进事项。AI 总结邮件、起草回复、提醒跟进，发送由人工确认。用邮箱、电话、LinkedIn URL、域名、公司名称解析身份，疑似同名公司需业务员人工确认，禁止自动合并。价格、库存、交期、账期承诺以及重大客诉、信用决策由人工处理。 |
| Quotation Lifecycle | RFQ → 规格校验 → 工厂报价 → 行情和汇率参考 → 确定性成本利润计算 → 审批与 PDF → 跟进。支持四类产品和 FOB、CIF、CFR。工厂报价用于成本，行情用于参考。LLM 负责解析、解释与风险提示。报价版本保存供应商成本、行情来源、汇率、运费、保险、其他费用、利润、Incoterm、币种、有效期和时间戳，历史版本保持不可变。PDF 可以自动生成，对外发送需人工审批。 |
| Order Lifecycle | 已接受报价 → PI/合同草稿 → 付款条款批准 → 预付款核实 → 工厂备货 → QC → 装运 → 单据 → 尾款核实 → 交付 → 售后。初期轻量模块包括转订单、PI/合同草稿、订单状态、付款节点和交货提醒。到账以可信记录确认，合同由人工签署。完整报关、物流和银行集成排除在初期范围外。 |

报价公式仅作设计说明。总成本由货物成本、适用物流费、适用保险及其他费用组成。若业务确认采用销售额毛利率 m，候选售价公式为总成本 / (1 − m)。费用归属、单位、币种、汇率取值和利润口径仍为 TBD。

## 导航和 MVP（§04）

产品导航包括 Dashboard、Customer CRM、Communications、Market Intelligence、Quotation Center、Document Center、Order Management、AI Copilot。

| 优先级 | 范围 |
| --- | --- |
| P0 核心 MVP | 企业登录、团队角色权限、Excel 导入清洗、Customer 360、产品规格和供应商管理、供应商报价管理、Interaction、邮件集成、AI 邮件总结与草稿、可追溯客户记忆、跟进任务、Pricing Engine、PDF 报价、审批、审计日志、基础多租户隔离 |
| P1 | WhatsApp Business Platform、LinkedIn 授权流程与人工导入、PI/合同草稿、订单管理、付款节点、装运及交货提醒、丰富行情数据源 |
| P2 | 自动拓客、Volza 等贸易数据、BI、高级多 Agent 自动化、商业计费与订阅 |

P1 轻量订单可在试点前尝试，以 P0 上线为发布门槛。P0/P1/P2 为产品优先级，开发阶段定义见 [开发路线图](ROADMAP.md)。

## 技术需求索引（§05–§10、§12）

| 分类 | PRD 要求及详细文档 |
| --- | --- |
| 产品 Agent 架构 | Orchestrator 按需路由、汇总及并行调用客户、行情、报价、文档 Agent。后续引入贸易运营 Agent。受控工具继承发起人的权限，关键操作进入人工审批。详见 [架构](ARCHITECTURE.md)。 |
| 数据库与 ERD | PostgreSQL，租户业务表带 `tenant_id`，应用层和数据库层双重隔离，考虑 RLS。保留客户记忆原始消息引用及不可变报价快照。详见 [ERD](DATABASE_ERD.md)。 |
| API | REST `/api/v1`，OpenAPI，注入租户作用域及 RBAC，关键操作幂等，Webhook 验签和防重放。候选端点详见 [API 契约](API_CONTRACTS.md)。 |
| RBAC 与安全 | 角色及 owner/team 作用域，成本、毛利、付款分别授权。对外操作人工控制，敏感数据加密，审批和外发留有审计。详见 [安全](SECURITY.md)。 |
| 技术架构 | Next.js、TypeScript、Tailwind CSS、shadcn/ui、FastAPI、SQLAlchemy/Alembic、可配置 AI provider，初期采用模块化单体。详见 [架构](ARCHITECTURE.md)。 |
| AWS 部署 | Docker、ECS Fargate、私网 RDS、S3、按需队列和缓存，经 TLS/WAF/ALB 入口，GitHub Actions 经 ECR 部署 ECS。区划和成本 TBD。详见 [架构](ARCHITECTURE.md)。 |
| 开发和验收 | 先定义 schema、contract、tests，再实现和审查。各阶段产品验收及 Phase 1 的实施边界见 [开发路线图](ROADMAP.md)。 |

## KPI 与试点（§13、§14）

试点选 2–3 位业务员及少量老客户，先记录人工基线，再对照试点数据。报价从 30 分钟到 7–10 分钟属于待验证假设。ROI 根据开发运营成本、节省工时、报价速度、错误率和复购数据测算，收益目标 TBD。

| 指标 | 统计方式 |
| --- | --- |
| Customer Data Coverage | 完整客户档案 / 试点客户 |
| Communication Capture Rate | 归档沟通 / 应归档沟通 |
| AI Draft Acceptance Rate | 采用草稿 / 生成草稿 |
| Quotation Turnaround Time | 完整询价到审批完成 |
| Quotation Error Rate | 有错误报价 / 抽检报价 |
| Follow-up Completion Rate | 按时完成 / 到期任务 |
| Repeat Purchase Rate | 复购客户 / 合适观察期内客户 |
| Order Processing Time | 报价接受到订单建立 |

待确认项和原文资料清单见 [待确认事项](OPEN_QUESTIONS.md)。
