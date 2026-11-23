"use server";

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { crmRequest, readResponse } from "../api";
import { checkedOrigin, currentToken } from "../server-session";
import { isCustomer, isImportResult, uuid } from "./models";
import type { ImportRow } from "./models";

const maxUpload = 2 * 1024 * 1024;

export type ImportState = {
  phase: "idle" | "preview" | "committed";
  proof?: string;
  rows: ImportRow[];
  replayed?: boolean;
  error?: string;
};

function field(form: FormData, key: string) {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

async function writeToken() {
  await checkedOrigin("/crm?status=origin");
  const token = await currentToken();
  if (!token) redirect("/");
  return token;
}

function outcome(response: Response | null) {
  if (response?.status === 401) redirect("/");
  if (response?.status === 403) return "forbidden";
  if (response?.status === 404) return "notfound";
  if (response?.status === 422 || response?.status === 400) return "invalid";
  return response?.ok ? "saved" : "unavailable";
}

function customerPath(form: FormData) {
  const id = field(form, "customer_id");
  if (!uuid.test(id)) redirect("/crm?status=invalid");
  return `/customers/${id}` as const;
}

async function customerWrite(
  form: FormData,
  action: {
    method: "POST" | "PATCH";
    suffix: string;
    body: object;
  },
) {
  const token = await writeToken();
  const path = customerPath(form);
  const response = await crmRequest(`${path}${action.suffix}`, token, action.method, action.body);
  redirect(`/crm/${path.split("/").at(-1)}?status=${outcome(response)}`);
}

export async function createCustomer(form: FormData) {
  const token = await writeToken();
  const owner = field(form, "owner_id");
  if (owner && !uuid.test(owner)) redirect("/crm?status=invalid");
  const response = await crmRequest("/customers", token, "POST", {
    name: field(form, "name"),
    country: field(form, "country") || null,
    website: field(form, "website") || null,
    ...(owner ? { owner_id: owner } : {}),
  });
  const customer = await readResponse(response, isCustomer);
  if (customer) redirect(`/crm/${customer.id}?status=saved`);
  const status = outcome(response);
  redirect(`/crm?status=${status === "saved" ? "unavailable" : status}`);
}

export async function assignOwner(form: FormData) {
  const owner = field(form, "owner_id");
  if (!uuid.test(owner)) redirect("/crm?status=invalid");
  return customerWrite(form, { method: "PATCH", suffix: "/owner", body: { owner_id: owner } });
}

export async function addContact(form: FormData) {
  return customerWrite(form, {
    method: "POST",
    suffix: "/contacts",
    body: {
      name: field(form, "name"),
      email: field(form, "email") || null,
      phone: field(form, "phone") || null,
      linkedin_url: field(form, "linkedin_url") || null,
    },
  });
}

export async function createFollowUp(form: FormData) {
  return customerWrite(form, {
    method: "POST",
    suffix: "/follow-ups",
    body: { title: field(form, "title"), due_date: field(form, "due_date") || null },
  });
}

export async function completeFollowUp(form: FormData) {
  const task = field(form, "task_id");
  if (!uuid.test(task)) redirect("/crm?status=invalid");
  return customerWrite(form, {
    method: "PATCH",
    suffix: `/follow-ups/${task}`,
    body: { completed: true },
  });
}

const uploadErrors: Record<number, string> = {
  400: "工作簿无法处理。请检查模板列、格式和限制。",
  403: "当前角色无法导入客户。",
  413: "工作簿超过大小限制。",
  415: "请选择 .xlsx 工作簿。",
  422: "工作簿无法处理。请检查模板列、格式和限制。",
};

function signPreview(token: string, digest: string, rows: ImportRow[]) {
  const duplicates = rows.filter((row) => row.status === "duplicate").map((row) => row.row);
  const claims = `${digest}.${duplicates.join(",")}`;
  const signature = createHmac("sha256", token).update(`crm-preview:${claims}`).digest("hex");
  return `${claims}.${signature}`;
}

function previewDuplicates(token: string, digest: string, proof: unknown) {
  if (typeof proof !== "string" || proof.length > 4200) return null;
  const parts = proof.split(".");
  if (parts.length !== 3) return null;
  const [fileDigest, duplicates, signed] = parts;
  if (fileDigest !== digest || !/^[0-9a-f]{64}$/.test(signed)) return null;
  const expected = createHmac("sha256", token)
    .update(`crm-preview:${fileDigest}.${duplicates}`).digest();
  if (!timingSafeEqual(expected, Buffer.from(signed, "hex"))) return null;
  return new Set(duplicates ? duplicates.split(",") : []);
}

export async function importCustomers(form: FormData, proof?: string): Promise<ImportState> {
  const token = await writeToken();
  const mode = field(form, "mode");
  const previewError = (error: string): ImportState => ({ phase: "idle", rows: [], error });
  if (mode !== "preview" && mode !== "commit") return previewError("请选择导入操作。");
  const file = form.get("file");
  if (!(file instanceof File) || !/\.xlsx$/i.test(file.name) || file.size === 0 || file.size > maxUpload) {
    return previewError("请选择非空的 .xlsx 文件，文件大小上限为 2 MiB。");
  }

  const bytes = await file.arrayBuffer();
  const digest = createHash("sha256").update(Buffer.from(bytes)).digest("hex");
  const query = new URLSearchParams({ mode });
  if (mode === "commit") {
    const duplicates = previewDuplicates(token, digest, proof);
    if (!duplicates) {
      return previewError("请选择刚才预览过的同一份文件。");
    }
    for (const row of new Set(form.getAll("confirm_row"))) {
      if (typeof row !== "string" || !duplicates.has(row)) {
        return previewError("只可确认预览中标为疑似重复的行。");
      }
      query.append("confirm_row", row);
    }
  }

  const response = await crmRequest(`/customers/import?${query}`, token, "POST", bytes);
  if (response?.status === 401) redirect("/");
  const result = await readResponse(response, isImportResult);
  if (!result) {
    return previewError(uploadErrors[response?.status ?? 0] ?? "导入服务暂时无法处理请求，请重试。");
  }
  if (mode === "commit") {
    revalidatePath("/crm");
    return { phase: "committed", rows: result.rows, replayed: result.replayed };
  }
  return { phase: "preview", proof: signPreview(token, digest, result.rows), rows: result.rows };
}
