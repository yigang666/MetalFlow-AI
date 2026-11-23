# REST API 合同

[HTML PRD §07 与页面脚本](../MetalFlow_AI_Product_Owner_PRD_v1.html) 为接口来源。统一前缀为 /api/v1，实现阶段提供 OpenAPI/Swagger。组合方法中每个方法对应一个操作。

业务调用服从租户范围与 RBAC。Webhook 必须验签、防重放。关键动作使用幂等键，对外发送与审批须记录审计。路径中的 {id} 由服务端按当前租户和资源范围解析。

## PRD 接口清单

### Auth / Tenant

- `POST /auth/login`
- `POST /auth/refresh`
- `GET /me`
- `GET /tenant`
- `POST /tenant/invitations`
- `GET /users`
- `POST /users`
- `PATCH /users/{id}`

### CRM

- `GET/POST /customers`
- `GET/PATCH/DELETE /customers/{id}`
- `GET /customers/{id}/360`
- `POST /customers/import`
- `GET /customers/{id}/interactions`
- `POST /customers/{id}/notes`
- `GET/POST /customers/{id}/follow-ups`

### Communications

- `POST /integrations/email/connect`
- `POST /integrations/email/sync`
- `GET /messages`
- `GET /messages/{id}`
- `POST /messages/{id}/summarize`
- `POST /messages/{id}/draft-reply`
- `POST /drafts/{id}/approve-send`
- `POST /integrations/webhooks/email`

### Products / Market

- `GET/POST /products`
- `GET/POST /suppliers`
- `GET/POST /supplier-quotes`
- `GET/POST /market-prices`
- `GET /exchange-rates`

### Quotation

- `POST /quotations/parse-rfq`
- `GET/POST /quotations`
- `GET /quotations/{id}`
- `POST /quotations/{id}/calculate`
- `POST /quotations/{id}/submit-approval`
- `POST /quotations/{id}/approve`
- `POST /quotations/{id}/reject`
- `GET /quotations/{id}/pdf`

### Order

- `GET/POST /orders`
- `POST /quotations/{id}/convert-to-order`
- `GET/PATCH /orders/{id}`
- `GET/POST /orders/{id}/payment-milestones`
- `POST /orders/{id}/documents`

### AI / Audit

- `POST /ai/customer-brief`
- `POST /ai/email-summary`
- `POST /ai/draft-email`
- `POST /ai/quotation-review`
- `GET /ai/tasks/{id}`
- `GET /audit-logs`

## Phase 1 合同候选

| 路径 | 行为与初步边界 |
| --- | --- |
| POST /auth/login，POST /auth/refresh | 认证、刷新和确定当前租户。请求体、会话机制及租户选择规则待身份方案确认。 |
| GET /me，GET /tenant | 返回当前身份、租户及授权上下文。禁止以客户端任意租户标识切换范围。 |
| POST /tenant/invitations | 授权管理员在当前租户建立邀请，重复请求与有效期规则需冻结。Sandbox 模拟投递。 |
| GET /users，POST /users，PATCH /users/{id} | 按授权读写同租户用户，限制角色分配和状态更改并记录审计。创建用户与邀请的关系待冻结。 |
| GET /audit-logs | 按租户与审计权限分页查询，返回字段依照日志脱敏要求冻结。 |

拟采用 401 表示无有效身份、403 表示操作无权限、404 表示当前租户不可见的资源。相同幂等键与相同请求在所属租户和操作范围内返回同结果，键重复且内容不同时返回 409。错误响应、分页字段、请求体、状态码、会话和幂等保留期须在实现前以 OpenAPI 冻结。业务端点按 [ROADMAP.md](ROADMAP.md) 分阶段验收。

## Phase 1 Sandbox 实现

[已冻结的 Sandbox 合同](../tasks/PHASE_1.md)记录请求、主字段和角色权限。运行 API 后，`/openapi.json` 和 `/docs` 提供可执行实现生成的 OpenAPI。邀请、用户写操作及后续业务接口保留设计状态。
