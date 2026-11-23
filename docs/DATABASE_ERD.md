# 逻辑 ERD 与 Phase 1 数据边界

[HTML PRD §06](../MetalFlow_AI_Product_Owner_PRD_v1.html) 提供逻辑模型。表定义、字段约束与索引将在对应阶段落实。

| 领域 | PRD 实体 |
| --- | --- |
| SaaS / RBAC | tenants, tenant_settings, subscriptions, users, roles, permissions, user_roles, role_permissions, teams |
| CRM | customers, customer_contacts, customer_identifiers, customer_owners, customer_tags, customer_notes |
| 通信 | communication_accounts, message_threads, messages, message_attachments, interaction_events, customer_memories, customer_memory_sources, follow_up_tasks |
| 产品 / 市场 | products, product_specs, suppliers, supplier_contacts, supplier_quotes, supplier_quote_items, market_prices, exchange_rates |
| 报价 | quotations, quotation_items, quotation_costs, quotation_versions, quotation_approvals |
| 订单 | orders, order_items, payments, payment_milestones, shipments, documents |
| AI / 审计 | ai_tasks, ai_suggestions, approval_requests, workflow_events, audit_logs |

- Tenant 对 Customer、User、Product、Supplier、Quotation、Order 均为一对多。
- Customer 对 Contact、Interaction、Memory、Follow-up、Quotation、Order 均为一对多。
- Supplier 对 Supplier Quote、Supplier Quote 对 Quote Item 均为一对多。
- Communication Account 对 Thread、Thread 对 Message、Message 对 Attachment 均为一对多。
- Quotation 对 Item、Cost、Version、Approval 均为一对多，支持转 Order。Order 对 Payment、Shipment、Document 均为一对多。
- Customer Memory 通过 Memory Source 追溯原始消息。历史报价采用不可变版本快照。敏感数据加密，软删除与保留策略待按数据类别确认。

## Phase 1 候选

| 能力 | 表与最小字段候选 |
| --- | --- |
| 租户和用户 | tenants(id, name, status)，users(id, tenant_id, identity_key, status) |
| 团队 | teams(id, tenant_id, name)，团队成员关系和归属规则待定 |
| 权限 | roles(id, tenant_id, key)，permissions(id, key)，user_roles(tenant_id, user_id, role_id)，role_permissions(tenant_id, role_id, permission_id) |
| 审计 | audit_logs(id, tenant_id, actor_id, action, resource_type, resource_id, outcome, request_id, occurred_at) |
| 账户生命周期 | 邀请、会话吊销相关数据取决于身份方案，待合同冻结 |

登录身份和租户绑定方式待定。permissions 可作为全局权限标识目录，租户持有角色与授权关系。所有租户业务表含非空 tenant_id，跨业务表采用租户一致性外键，例如 (tenant_id, user_id)。候选方案为应用查询显式约束租户，加上 PostgreSQL RLS 与非 owner 运行角色。租户上下文限制在事务内，验证连接池复用安全。用两个合成租户覆盖直接数据库验证和 API 验证。Database Engineer 负责迁移，顺序为租户/身份/团队 → 权限目录和授权 → 审计与隔离策略 → 双租户种子和回滚验证。最终方案与 [API 合同](API_CONTRACTS.md) 及 [安全要求](SECURITY.md) 一并冻结。

本地 Sandbox 迁移以 [0001_foundation](../backend/alembic/versions/0001_foundation.py) 为准。当前使用 `tenants`、`users`、`sessions` 和 `audit_logs`。账号只在所属租户内按规范化邮箱唯一，角色保存在账号记录。会话以租户和令牌摘要为复合主键，账号关系使用租户一致性外键。种子使用两个合成租户。团队作用域和可配置业务角色待对应业务阶段确认。

## 初步数据字典

| 字段候选 | 含义和约束 |
| --- | --- |
| id | 稳定的不透明资源标识，数据库类型在迁移冻结 |
| tenant_id | 租户外键，租户业务表非空，关系须匹配同租户 |
| name | 租户或团队展示名，长度及唯一性规则待定 |
| identity_key | 身份提供方或本地身份的稳定引用，唯一性范围取决于身份方案 |
| status | 租户或用户生命周期状态，状态集合和转换待定 |
| role_id / user_id / permission_id | 授权关系外键，同租户角色和用户匹配，权限键由平台目录定义 |
| key | 稳定的角色或权限机器标识，角色按租户限定 |
| actor_id / action / resource_type / resource_id | 审计操作者、动作、目标类型和标识，系统动作如何归因待定 |
| outcome / request_id / occurred_at | 审计结果、请求追踪标识及事件时间，时间以 UTC 存储为候选 |
| currency / unit / quantity | 交易币种、计价单位、数量。换算、精度、最小起订量及规格规则 TBD |
| supplier_cost / market_reference / exchange_rate | 供应商成本、行情参考与换算输入。成本、行情各自保留来源和时间戳。汇率方向、日期口径和供应商渠道 TBD |
| freight / insurance / other_fees / profit | 运费、保险、其他费用和利润。纳入条件、税费、佣金、精度与利润口径 TBD |
| incoterm / validity / quoted_at | 贸易条款（FOB、CIF、CFR）、报价有效期及报价时点。费用归属和有效期策略 TBD |
| memory_source / payment_evidence | 客户记忆回溯原消息。到账确认引用可信记录，记录来源与授权 TBD |

业务字段为后续阶段参考。报价计算口径、客户历史样本和数据合规详见 [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md)。
