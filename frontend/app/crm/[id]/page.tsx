import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { crmRequest, readResponse } from "../../api";
import { currentToken } from "../../server-session";
import { addContact, assignOwner, completeFollowUp, createFollowUp } from "../actions";
import { crmPermissions, isDetail, isOwner, items, uuid } from "../models";
import { CrmNotice } from "../views";

export default async function CustomerDetail({
  params, searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ status?: string | string[] }>;
}) {
  const token = await currentToken();
  if (!token) redirect("/");
  const { id } = await params;
  if (!uuid.test(id)) notFound();
  const access = await crmPermissions(token);
  if (access.status === 401) redirect("/");
  if (access.permissions && !access.permissions.includes("crm:read")) notFound();
  const assignable = access.permissions?.includes("crm:assign") ?? false;
  const writable = access.permissions?.includes("crm:write") ?? false;
  const [detailReply, ownersReply] = await Promise.all([
    access.permissions ? crmRequest(`/customers/${id}/360`, token) : null,
    assignable ? crmRequest("/customers/owners", token) : null,
  ]);
  if (detailReply?.status === 401 || ownersReply?.status === 401) redirect("/");
  if (detailReply?.status === 404 || detailReply?.status === 403) notFound();
  const [detail, owners] = await Promise.all([readResponse(detailReply, isDetail), items(ownersReply, isOwner)]);
  const { status } = await searchParams;

  return (
    <main className="shell grid gap-5 py-9">
      <nav aria-label="客户"><Link className="crm-link" href="/crm">返回客户列表</Link></nav>
      <CrmNotice status={typeof status === "string" ? status : undefined} />
      {!detail ? <p className="notice" role="alert">暂时无法加载客户详情。</p> : (
        <>
          <section className="card" aria-labelledby="detail-title">
            <p className="muted">Customer 360</p>
            <h1 id="detail-title" className="break-words">{detail.customer.name}</h1>
            <dl className="mt-3 grid gap-4 sm:grid-cols-3">
              <div><dt className="muted">负责人</dt><dd className="break-words">{detail.owner.email}{!detail.owner.active && "（已禁用）"}</dd></div>
              <div><dt className="muted">国家或地区</dt><dd>{detail.customer.country || "—"}</dd></div>
              <div><dt className="muted">网站</dt><dd className="break-words">{detail.customer.website || "—"}</dd></div>
            </dl>
            {assignable && owners && owners.length > 0 && (
              <form action={assignOwner} className="mt-4 flex flex-wrap items-end gap-3">
                <input type="hidden" name="customer_id" value={id} />
                <label className="field">负责人
                  <select name="owner_id" defaultValue={detail.owner.active ? detail.owner.id : ""} required>
                    {!owners.some((owner) => owner.id === detail.owner.id) && (
                      <option value="" disabled>选择负责人</option>
                    )}
                    {owners.map((owner) => <option key={owner.id} value={owner.id}>{owner.email}</option>)}
                  </select>
                </label>
                <button className="button-secondary" type="submit">保存负责人</button>
              </form>
            )}
          </section>

          <section className="card" aria-labelledby="contacts-title">
            <h2 id="contacts-title" className="mb-3">联系人</h2>
            {detail.contacts.length === 0 ? <p className="muted">暂无联系人。</p> : (
              <div className="overflow-x-auto">
                <table aria-labelledby="contacts-title">
                  <thead><tr><th scope="col">姓名</th><th scope="col">邮箱</th><th scope="col">电话</th><th scope="col">LinkedIn</th></tr></thead>
                  <tbody>{detail.contacts.map((contact) => (
                    <tr key={contact.id}><td>{contact.name}</td><td>{contact.email || "—"}</td>
                      <td>{contact.phone || "—"}</td><td>{contact.linkedin_url || "—"}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            {writable && (
              <form action={addContact} className="mt-4 grid gap-4">
                <input type="hidden" name="customer_id" value={id} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="field">联系人姓名<input name="name" maxLength={200} required /></label>
                  <label className="field">联系人邮箱<input type="email" name="email" maxLength={254} /></label>
                  <label className="field">联系电话<input type="tel" name="phone" maxLength={50} /></label>
                  <label className="field">LinkedIn URL<input type="url" name="linkedin_url" maxLength={300} /></label>
                </div>
                <div><button className="button-secondary" type="submit">添加联系人</button></div>
              </form>
            )}
          </section>

          <section className="card" aria-labelledby="follow-up-title">
            <h2 id="follow-up-title" className="mb-3">跟进任务</h2>
            {detail.follow_ups.length === 0 ? <p className="muted">暂无跟进任务。</p> : (
              <div className="overflow-x-auto">
                <table aria-labelledby="follow-up-title">
                  <thead><tr><th scope="col">任务</th><th scope="col">截止日期</th><th scope="col">状态</th>{writable && <th scope="col">操作</th>}</tr></thead>
                  <tbody>{detail.follow_ups.map((task) => (
                    <tr key={task.id}><td>{task.title}</td><td>{task.due_date || "—"}</td>
                      <td>{task.completed_at ? "已完成" : "待跟进"}</td>
                      {writable && <td>{!task.completed_at && (
                        <form action={completeFollowUp}>
                          <input type="hidden" name="customer_id" value={id} />
                          <input type="hidden" name="task_id" value={task.id} />
                          <button className="button-secondary" type="submit">完成跟进</button>
                        </form>
                      )}</td>}
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
            {writable && (
              <form action={createFollowUp} className="mt-4 grid gap-4">
                <input type="hidden" name="customer_id" value={id} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="field">任务标题<input name="title" maxLength={200} required /></label>
                  <label className="field">截止日期<input type="date" name="due_date" /></label>
                </div>
                <div><button className="button-secondary" type="submit">创建跟进</button></div>
              </form>
            )}
          </section>
        </>
      )}
    </main>
  );
}
