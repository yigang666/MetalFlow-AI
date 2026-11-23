const assert = require("node:assert/strict");
const { chromium } = require(process.env.PLAYWRIGHT_CORE_PATH || "playwright-core");

const web = process.env.METALFLOW_WEB_URL || "http://localhost:3000";
const api = process.env.METALFLOW_API_URL || "http://127.0.0.1:8000";
const password = process.env.SANDBOX_PASSWORD;
const tag = process.env.CRM_TEST_TAG;
const workbook = process.env.CRM_TEST_WORKBOOK;
const largeWorkbook = process.env.CRM_LARGE_WORKBOOK;
const tenantA = "11111111-1111-4111-8111-111111111111";
const tenantB = "22222222-2222-4222-8222-222222222222";
const customer = `Browser Customer ${tag}`;
assert(password && tag && workbook && largeWorkbook);
for (const url of [web, api]) {
  assert(["localhost", "127.0.0.1", "[::1]"].includes(new URL(url).hostname));
}

async function signIn(page, tenant, account) {
  await page.goto(web);
  await page.getByLabel("租户").selectOption(tenant);
  await page.getByLabel("邮箱").fill(`${account}@example.test`);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await page.getByRole("link", { name: "客户 CRM", exact: true }).waitFor();
}

function button(page, name) {
  return page.getByRole("button", { name, exact: true });
}

function heading(page, name) {
  return page.getByRole("heading", { name, exact: true });
}

async function prepareLargeMatches(context) {
  const session = (await context.cookies(web)).find((cookie) => cookie.name === "metalflow_session");
  assert(session?.httpOnly, "Expected a browser session");
  for (let index = 0; index < 20; index += 1) {
    const response = await fetch(`${api}/api/v1/customers`, {
      method: "POST",
      signal: AbortSignal.timeout(5000),
      headers: { authorization: `Bearer ${session.value}`, "content-type": "application/json" },
      body: JSON.stringify({
        name: `Duplicate candidate ${tag} ${index} ${"m".repeat(145)}`,
        website: `https://large-${tag}.example.test`,
      }),
    });
    assert.equal(response.status, 201);
  }
}

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true });
  try {
    const ownerContext = await browser.newContext();
    const owner = await ownerContext.newPage();
    owner.setDefaultTimeout(20000);
    await signIn(owner, tenantA, "owner");
    await owner.getByRole("link", { name: "客户 CRM", exact: true }).click();
    await owner.getByLabel("客户名称").fill(customer);
    await button(owner, "创建客户").click();
    await heading(owner, customer).waitFor();
    const customerUrl = owner.url().split("?")[0];

    await owner.getByLabel("负责人").selectOption({ label: "sales@example.test" });
    await button(owner, "保存负责人").click();
    await owner.getByText("sales@example.test", { exact: true }).first().waitFor();
    await owner.getByLabel("联系人姓名").fill("Browser Buyer");
    await owner.getByLabel("联系人邮箱").fill(`buyer-${tag}@example.test`);
    await button(owner, "添加联系人").click();
    await owner.getByRole("cell", { name: "Browser Buyer", exact: true }).waitFor();
    await owner.getByLabel("任务标题").fill("Browser follow-up");
    await owner.getByLabel("截止日期").fill("2026-12-01");
    await button(owner, "创建跟进").click();
    await button(owner, "完成跟进").click();
    await owner.getByText("已完成", { exact: true }).waitFor();
    console.log("PASS Customer 360, sales owner assignment, contact creation, and follow-up completion");

    const sales = await browser.newPage();
    await signIn(sales, tenantA, "sales");
    await sales.goto(customerUrl);
    await heading(sales, customer).waitFor();
    assert.equal(await button(sales, "保存负责人").count(), 0);
    await sales.close();
    const other = await browser.newPage();
    await signIn(other, tenantB, "owner");
    await other.goto(customerUrl);
    await other.getByText(/客户不存在|当前账号无法查看|无权查看|客户不可见|This page could not be found/).first().waitFor();
    assert.equal(await heading(other, customer).count(), 0);
    await other.close();
    console.log("PASS assigned sales can read the customer; second tenant cannot");

    await owner.getByRole("link", { name: "返回客户列表" }).click();
    await owner.getByLabel("Excel 文件").setInputFiles(workbook);
    await button(owner, "预览导入").click();
    await owner.getByRole("heading", { name: "导入预览" }).waitFor();
    await owner.getByText("疑似重复", { exact: true }).waitFor();
    await owner.getByRole("checkbox", { name: "第 3 行作为独立客户创建" }).check();
    await owner.getByLabel("确认文件").setInputFiles(largeWorkbook);
    await button(owner, "确认导入").click();
    await owner.getByRole("alert").filter({ hasText: "同一份文件" }).waitFor();
    await owner.getByLabel("确认文件").setInputFiles(workbook);
    await button(owner, "确认导入").click();
    await owner.getByRole("heading", { name: "导入结果" }).waitFor();
    await owner.getByText(/已创建 2 条客户记录/).waitFor();
    console.log("PASS Excel preview, wrong-file rejection, and explicit duplicate confirmation");

    await prepareLargeMatches(ownerContext);
    await owner.getByLabel("Excel 文件").setInputFiles(largeWorkbook);
    await button(owner, "预览导入").click();
    await owner.getByRole("heading", { name: "导入预览" }).waitFor();
    const rows = owner.getByRole("table", { name: "导入预览" }).locator("tbody tr");
    assert.equal(await rows.count(), 500);
    await owner.getByLabel("确认文件").setInputFiles(largeWorkbook);
    await button(owner, "确认导入").click();
    await owner.getByRole("heading", { name: "导入结果" }).waitFor();
    await owner.getByText(/已创建 0 条客户记录/).waitFor();
    console.log("PASS 500-row preview plus near-limit workbook submits without uploading preview results");
    await ownerContext.close();
  } finally {
    await browser.close();
  }
}
main().catch((error) => {
  console.error(String(error.stack ?? error).replaceAll(password, "[redacted]"));
  process.exitCode = 1;
});
