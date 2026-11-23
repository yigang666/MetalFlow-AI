# Phase 2 · Customer CRM

Product Owner 于 2026-11-24 批准 Sandbox Excel 导入、Customer 360、联系人、客户负责人和跟进任务。工作以 06:00 SGT 为预算起点，10:00 SGT 为截止线。真实客户样本、生产数据、团队映射、通讯/报价/订单和自动合并位于本次实现边界之外。实际客户字段映射与身份判定仍待脱敏样本和业务确认。

| ID | 交付 | 所有权 | 状态 |
| --- | --- | --- | --- |
| P2-01 | 合同、依赖、验收 | Team Lead，tasks 与 docs | DONE |
| P2-02 | 单一 Alembic 迁移和数据库隔离 | Database Agent，backend/alembic/versions/0002_crm.py | DONE |
| P2-03 | CRM API 和集成 | Team Lead，backend/app/main.py、backend/app/crm.py、requirements | DONE |
| P2-04 | XLSX 校验及导入服务 | Import Agent，backend/app/crm_import.py、对应单测 | DONE |
| P2-05 | 工作空间 CRM 界面 | Frontend Agent，frontend/ | DONE |
| P2-06 | 验收、独立代码与安全审查 | Team Lead、独立 Reviewer，测试与证据 | DONE |
| P2-07 | 交付、启动说明与阶段门禁 | Team Lead，状态及报告 | DONE |
| P2-B1 | 真实客户样本与业务去重确认 | Product Owner，脱敏样本及字段规则 | BLOCKED |

## Sandbox 合同

以下端点以 /api/v1 开头。owner/admin 有租户内 CRM 读写、分配和导入权限。sales 只能读取自己负责的客户、添加联系人和创建/完成其跟进；无转移或导入权限。auditor 的既有审计权限不变。额外权限名称为 crm:read、crm:write、crm:assign、crm:import。其他租户或负责人不可见的资源返回 404，缺少角色权限返回 403。所有写入原子完成并追加审计。

- GET /customers 返回 {items:[{id,name,country,website,owner_id,created_at}]}，支持 limit/offset。POST /customers 接收 {name,country?,website?,owner_id?}，owner/admin 使用，默认负责人是发起人。
- GET /customers/{id}/360 返回 {customer:{id,name,country,website,owner_id,created_at},owner:{id,email,active},contacts:[{id,name,email,phone,linkedin_url}],follow_ups:[{id,title,due_date,completed_at}]}。
- GET /customers/owners 返回 {items:[{id,email}]}，限有分配权限，列同租户启用的 owner/admin/sales。
- PATCH /customers/{id}/owner 接收 {owner_id}，成功返回更新的客户。
- POST /customers/{id}/contacts 接收 {name,email?,phone?,linkedin_url?}。POST /customers/{id}/follow-ups 接收 {title,due_date?}。PATCH /customers/{id}/follow-ups/{task_id} 接收 {completed: true}，重复完成保留原时间。
- POST /customers/import?mode=preview 或 mode=commit，原始 XLSX HTTP 请求体，Content-Type application/vnd.openxmlformats-officedocument.spreadsheetml.sheet。commit 可传重复参数 confirm_row=N，用于操作员明确将候选重复行作为独立客户创建。疑似重复默认跳过，系统不合并已有记录。
- 工作表 Customers，精确列顺序 name,country,website,contact_name,email,phone,linkedin_url。最多 500 数据行，最多 2 MiB。返回 {rows:[{row,name,status,matches:[{id,name}],errors:[string]}], replayed:boolean}。状态 ready/duplicate/invalid/created。整份文件严格校验结构，逐行给出结果，只有 ready 或已明确确认的 duplicate 行创建。相同租户、相同文件字节、相同确认行集合的 commit 重放返回既有结果。可能重复依据精确规范化公司名、域名、联系人邮箱/电话/LinkedIn 命中提示，属于待业务验证的 Sandbox 建议。导入负责人默认为发起人。
- 新建/读取支持合成模板；真实 Excel 格式、列映射、团队授权及去重规则以业务验收为准。

验收包括升级/降级、无权限和跨租户/跨负责人、导入校验/预览/重复确认及重放、联系人和跟进状态、审计、前端交互及 Phase 1 回归。每个问题最多修复三轮。

运行证据、审查记录和业务待确认事项见 [Phase 2 Delivery Report](../reports/PHASE_2.md)。
