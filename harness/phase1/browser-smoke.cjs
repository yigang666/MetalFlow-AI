const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || "playwright-core");

const web = process.env.METALFLOW_WEB_URL || "http://localhost:3000";
const api = process.env.METALFLOW_API_URL || "http://127.0.0.1:8000";
const password = process.env.SANDBOX_PASSWORD;
const tenantA = "11111111-1111-4111-8111-111111111111";
const tenantB = "22222222-2222-4222-8222-222222222222";
const cookieName = "metalflow_session";

assert(password, "Set the generated Sandbox test password");
for (const url of [web, api]) {
  assert(["localhost", "127.0.0.1", "[::1]"].includes(new URL(url).hostname));
}

async function signIn(page, tenant, email, suppliedPassword = password) {
  await page.getByLabel("租户").selectOption(tenant);
  await page.getByLabel("邮箱").fill(email);
  await page.getByLabel("密码").fill(suppliedPassword);
  await page.getByRole("button", { name: "登录", exact: true }).click();
}

function heading(page, name) {
  return page.getByRole("heading", { name, exact: true });
}

async function getSession(context) {
  return (await context.cookies(web)).find((cookie) => cookie.name === cookieName);
}

async function main() {
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_PATH,
    headless: true,
    timeout: 20000,
  });
  try {
    const context = await browser.newContext();
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    await page.goto(web, { timeout: 15000 });
    await heading(page, "登录工作空间").waitFor();
    await signIn(page, tenantA, "owner@example.test", "incorrect-sandbox-password");
    await page.getByRole("alert").filter({ hasText: "登录失败" }).waitFor();
    assert(!(await getSession(context)), "Failed login must not create a session cookie");
    console.log("PASS invalid login shows feedback and creates no browser session");

    await signIn(page, tenantA, "owner@example.test");
    await heading(page, "Sandbox Tenant A").waitFor();
    await heading(page, "用户").waitFor();
    await heading(page, "审计日志").waitFor();
    assert.equal(await page.getByRole("table", { name: "用户" }).locator("tbody tr").count(), 5);
    const session = await getSession(context);
    assert(session?.httpOnly && session.sameSite === "Strict");
    assert.equal((await page.content()).includes(session.value), false);
    assert.equal(await page.evaluate(() => document.cookie.includes("metalflow_session=")), false);
    await page.reload();
    await heading(page, "Sandbox Tenant A").waitFor();
    console.log("PASS tenant A Owner sees scoped users and audit; HttpOnly session survives reload");

    await page.getByRole("button", { name: "退出登录" }).click();
    await heading(page, "登录工作空间").waitFor();
    assert(!(await getSession(context)), "Logout must clear the session cookie");
    const afterLogout = await fetch(`${api}/api/v1/me`, {
      headers: { authorization: `Bearer ${session.value}` },
      signal: AbortSignal.timeout(5000),
    });
    assert.equal(afterLogout.status, 401);
    console.log("PASS browser logout clears cookie and API revokes the server session");

    await signIn(page, tenantB, "sales@example.test");
    await heading(page, "Sandbox Tenant B").waitFor();
    assert.equal(await heading(page, "用户").count(), 0);
    assert.equal(await heading(page, "审计日志").count(), 0);
    await page.getByRole("button", { name: "退出登录" }).click();
    await heading(page, "登录工作空间").waitFor();
    await signIn(page, tenantB, "auditor@example.test");
    await heading(page, "Sandbox Tenant B").waitFor();
    await heading(page, "审计日志").waitFor();
    assert.equal(await heading(page, "用户").count(), 0);
    await context.close();
    console.log("PASS tenant B Sales and Auditor see role-appropriate views");

    const noJsContext = await browser.newContext({ javaScriptEnabled: false });
    const noJsPage = await noJsContext.newPage();
    noJsPage.setDefaultTimeout(8000);
    await noJsPage.goto(web, { timeout: 15000 });
    await signIn(noJsPage, tenantA, "owner@example.test");
    await heading(noJsPage, "Sandbox Tenant A").waitFor();
    await noJsPage.getByRole("button", { name: "退出登录" }).click();
    await heading(noJsPage, "登录工作空间").waitFor();
    await noJsContext.close();
    console.log("PASS native same-origin forms support login and logout without JavaScript");
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(String(error.stack ?? error).replaceAll(password, "[redacted]"));
  process.exitCode = 1;
});
