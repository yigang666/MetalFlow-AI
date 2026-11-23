import { cookies } from "next/headers";
import { signIn, signOut } from "./actions";
import { apiRequest, readResponse, record, sessionCookie, sessionPattern } from "./api";

type Identity = {
  email: string;
  role: string;
  permissions: string[];
};
type Tenant = { name: string };
type User = { id: string; email: string; role: string; active: boolean };
type AuditEvent = {
  id: string;
  action: string;
  outcome: string;
  occurred_at: string;
};

const notices = {
  invalid: "登录失败。请检查工作区、邮箱和密码。",
  unavailable: "连接服务失败。请稍后重试。",
  origin: "登录或退出须从配置的 Sandbox 地址操作。",
  signout: "退出失败。请确认服务可用后重试。",
} as const;
const eventTime = new Intl.DateTimeFormat("zh-CN", {
  dateStyle: "medium", timeStyle: "medium", timeZone: "UTC",
});

function Login({ message }: { message?: string }) {
  return (
    <main className="shell">
      <section className="card login-card" aria-labelledby="login-title">
        <h1 id="login-title">登录工作空间</h1>
        <p className="muted mt-2 mb-6">请选择 Sandbox 租户，使用测试账户登录。</p>
        {message && <p className="notice mb-4" role="alert">{message}</p>}
        <form action={signIn} className="grid gap-4">
          <label className="field">
            租户
            <select name="tenant_id" required defaultValue="">
              <option value="" disabled>选择租户</option>
              <option value="11111111-1111-4111-8111-111111111111">Sandbox A</option>
              <option value="22222222-2222-4222-8222-222222222222">Sandbox B</option>
            </select>
          </label>
          <label className="field">
            邮箱
            <input name="email" type="email" autoComplete="username" maxLength={254} required />
          </label>
          <label className="field">
            密码
            <input name="password" type="password" autoComplete="current-password" maxLength={256} required />
          </label>
          <button className="button-primary mt-2" type="submit">登录</button>
        </form>
      </section>
    </main>
  );
}

function Users({ response }: { response: User[] | null }) {
  return (
    <section className="card" aria-labelledby="users-title">
      <h2 id="users-title" className="mb-3">用户</h2>
      {response === null ? <p role="status">暂时无法查看用户。</p> :
        response.length === 0 ? <p className="muted">暂无用户。</p> :
          <div className="overflow-x-auto">
            <table aria-labelledby="users-title">
              <thead><tr><th scope="col">邮箱</th><th scope="col">角色</th><th scope="col">状态</th></tr></thead>
              <tbody>
                {response.map((user) => <tr key={user.id}><td>{user.email}</td><td>{user.role}</td><td>{user.active ? "已启用" : "已禁用"}</td></tr>)}
              </tbody>
            </table>
          </div>}
    </section>
  );
}

function Audit({ response }: { response: AuditEvent[] | null }) {
  return (
    <section className="card" aria-labelledby="audit-title">
      <h2 id="audit-title" className="mb-3">审计日志</h2>
      {response === null ? <p role="status">暂时无法查看审计日志。</p> :
        response.length === 0 ? <p className="muted">暂无审计记录。</p> :
          <div className="overflow-x-auto">
            <table aria-labelledby="audit-title">
              <thead><tr><th scope="col">事件</th><th scope="col">结果</th><th scope="col">时间 (UTC)</th></tr></thead>
              <tbody>
                {response.map((event) => (
                  <tr key={event.id}>
                    <td>{event.action}</td><td>{event.outcome}</td>
                    <td><time dateTime={event.occurred_at}>{eventTime.format(new Date(event.occurred_at))}</time></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
    </section>
  );
}

function isUser(value: unknown): value is User {
  return record(value) && typeof value.id === "string" && typeof value.email === "string" &&
    typeof value.role === "string" && typeof value.active === "boolean";
}

function isAuditEvent(value: unknown): value is AuditEvent {
  return record(value) && typeof value.id === "string" && typeof value.action === "string" &&
    typeof value.outcome === "string" && typeof value.occurred_at === "string" &&
    Number.isFinite(Date.parse(value.occurred_at));
}

async function items<T>(response: Response | null, accepts: (value: unknown) => value is T) {
  const data = await readResponse(response, (value): value is { items: T[] } =>
    record(value) && Array.isArray(value.items) && value.items.every(accepts),
  );
  return data?.items ?? null;
}

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ status?: string | string[] }>;
}) {
  const token = (await cookies()).get(sessionCookie)?.value;
  const { status } = await searchParams;
  const message = typeof status === "string" && Object.hasOwn(notices, status)
    ? notices[status as keyof typeof notices]
    : undefined;

  if (!token || !sessionPattern.test(token)) return <Login message={message} />;
  const me = await apiRequest("/me", token);
  const identity = await readResponse(me, (value): value is Identity =>
    record(value) && typeof value.email === "string" && typeof value.role === "string" &&
    Array.isArray(value.permissions) && value.permissions.every((permission) => typeof permission === "string"),
  );
  if (!identity) return <Login message={me?.status === 401 ? message : notices.unavailable} />;

  const seeUsers = identity.permissions.includes("users:read");
  const seeAudit = identity.permissions.includes("audit:read");
  const [tenant, users, audit] = await Promise.all([
    apiRequest("/tenant", token),
    seeUsers ? apiRequest("/users", token) : null,
    seeAudit ? apiRequest("/audit-logs", token) : null,
  ]);
  const [workspace, userItems, auditItems] = await Promise.all([
    readResponse(tenant, (value): value is Tenant => record(value) && typeof value.name === "string"),
    items(users, isUser),
    items(audit, isAuditEvent),
  ]);

  return (
    <main className="shell grid gap-5 py-9">
      <section className="card flex flex-wrap items-start justify-between gap-5">
        <div className="min-w-0 break-words">
          <h1>{workspace?.name ?? "工作空间"}</h1>
          <p className="mt-1 muted">{identity.email} · {identity.role}</p>
        </div>
        <form action={signOut}>
          <button className="button-secondary" type="submit">退出登录</button>
        </form>
      </section>
      {message && <p className="notice" role="alert">{message}</p>}
      {seeUsers && <Users response={userItems} />}
      {seeAudit && <Audit response={auditItems} />}
    </main>
  );
}
