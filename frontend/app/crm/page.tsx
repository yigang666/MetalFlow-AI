import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { crmRequest } from "../api";
import { currentToken } from "../server-session";
import { createCustomer } from "./actions";
import ImportForm from "./import-form";
import { crmPermissions, isCustomer, isOwner, items } from "./models";
import { CrmNotice } from "./views";

const pageSize = 50;

export default async function Customers({
  searchParams,
}: {
  searchParams: Promise<{ status?: string | string[]; page?: string | string[] }>;
}) {
  const token = await currentToken();
  if (!token) redirect("/");
  const access = await crmPermissions(token);
  if (access.status === 401) redirect("/");
  if (access.permissions && !access.permissions.includes("crm:read")) notFound();
  const { status, page: value } = await searchParams;
  const page = typeof value === "string" && /^[1-9][0-9]{0,2}$/.test(value)
    ? Math.min(201, Number(value))
    : 1;
  const editable = access.permissions?.includes("crm:assign") ?? false;
  const importable = access.permissions?.includes("crm:import") ?? false;
  const [customersReply, ownersReply] = await Promise.all([
    access.permissions ? crmRequest(`/customers?limit=${pageSize}&offset=${(page - 1) * pageSize}`, token) : null,
    editable ? crmRequest("/customers/owners", token) : null,
  ]);
  if (customersReply?.status === 401 || ownersReply?.status === 401) redirect("/");
  const [customers, owners] = await Promise.all([items(customersReply, isCustomer), items(ownersReply, isOwner)]);

  return (
    <main className="shell grid gap-5 py-9">
      <nav aria-label="工作空间"><Link className="crm-link" href="/">返回工作空间</Link></nav>
      <h1>客户 CRM</h1>
      <CrmNotice status={typeof status === "string" ? status : undefined} />
      <section className="card" aria-labelledby="customers-title">
        <h2 id="customers-title" className="mb-3">客户列表</h2>
        {customers === null ? <p role="status">暂时无法查看客户。</p> :
          customers.length === 0 ? <p className="muted" role="status">暂无客户。</p> : (
            <div className="overflow-x-auto">
              <table aria-labelledby="customers-title">
                <thead><tr><th scope="col">客户名称</th><th scope="col">国家或地区</th><th scope="col">网站</th></tr></thead>
                <tbody>{customers.map((customer) => (
                  <tr key={customer.id}>
                    <td><Link className="crm-link" href={`/crm/${customer.id}`}>{customer.name}</Link></td>
                    <td>{customer.country || "—"}</td><td>{customer.website || "—"}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        {(page > 1 || (customers?.length === pageSize && page < 201)) && (
          <nav className="mt-4 flex gap-5" aria-label="客户分页">
            {page > 1 && <Link className="crm-link" href={`/crm?page=${page - 1}`}>上一页</Link>}
            {customers?.length === pageSize && page < 201 && (
              <Link className="crm-link" href={`/crm?page=${page + 1}`}>下一页</Link>
            )}
          </nav>
        )}
      </section>

      {editable && (
        <section className="card" aria-labelledby="create-title">
          <h2 id="create-title" className="mb-3">新增客户</h2>
          <form action={createCustomer} className="grid gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="field">客户名称<input name="name" maxLength={200} required /></label>
              <label className="field">国家或地区<input name="country" maxLength={100} /></label>
              <label className="field">网站<input name="website" maxLength={300} /></label>
              <label className="field">负责人
                <select name="owner_id" defaultValue="">
                  <option value="">当前账户</option>
                  {owners?.map((owner) => <option value={owner.id} key={owner.id}>{owner.email}</option>)}
                </select>
              </label>
            </div>
            <div><button className="button-primary" type="submit">创建客户</button></div>
          </form>
        </section>
      )}
      {importable && <ImportForm />}
    </main>
  );
}
