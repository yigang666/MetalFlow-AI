import "server-only";

import { apiRequest, readResponse, record } from "../api";

export const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type OwnerChoice = { id: string; email: string };
export type Customer = { id: string; name: string; country: string | null; website: string | null; owner_id: string };
type Contact = { id: string; name: string; email: string | null; phone: string | null; linkedin_url: string | null };
type FollowUp = { id: string; title: string; due_date: string | null; completed_at: string | null };
type Detail = {
  customer: Customer;
  owner: OwnerChoice & { active: boolean };
  contacts: Contact[];
  follow_ups: FollowUp[];
};

export type ImportRow = {
  row: number;
  name: string | null;
  status: "ready" | "duplicate" | "invalid" | "created";
  matches: { id: string; name: string }[];
  errors: string[];
};
type ImportResult = { rows: ImportRow[]; replayed: boolean };

function id(value: unknown): value is string {
  return typeof value === "string" && uuid.test(value);
}

function nullableText(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

export async function crmPermissions(token: string) {
  const response = await apiRequest("/me", token);
  const data = await readResponse(response, (value): value is { permissions: string[] } =>
    record(value) && Array.isArray(value.permissions) &&
    value.permissions.every((permission) => typeof permission === "string"),
  );
  return { status: response?.status, permissions: data?.permissions };
}

export function isCustomer(value: unknown): value is Customer {
  return record(value) && id(value.id) && id(value.owner_id) && typeof value.name === "string" &&
    nullableText(value.country) && nullableText(value.website);
}

export function isOwner(value: unknown): value is OwnerChoice {
  return record(value) && id(value.id) && typeof value.email === "string";
}

function isContact(value: unknown): value is Contact {
  return record(value) && id(value.id) && typeof value.name === "string" &&
    nullableText(value.email) && nullableText(value.phone) && nullableText(value.linkedin_url);
}

function isFollowUp(value: unknown): value is FollowUp {
  return record(value) && id(value.id) && typeof value.title === "string" &&
    nullableText(value.due_date) && nullableText(value.completed_at);
}

export function isDetail(value: unknown): value is Detail {
  return record(value) && record(value.owner) && typeof value.owner.active === "boolean" && isOwner(value.owner) &&
    isCustomer(value.customer) && Array.isArray(value.contacts) && value.contacts.every(isContact) &&
    Array.isArray(value.follow_ups) && value.follow_ups.every(isFollowUp);
}

export function isImportResult(value: unknown): value is ImportResult {
  return record(value) && typeof value.replayed === "boolean" && Array.isArray(value.rows) &&
    value.rows.every((row) => record(row) && typeof row.row === "number" && Number.isSafeInteger(row.row) &&
      nullableText(row.name) && typeof row.status === "string" &&
      ["ready", "duplicate", "invalid", "created"].includes(row.status) &&
      Array.isArray(row.matches) &&
      row.matches.every((match) => record(match) && id(match.id) && typeof match.name === "string") &&
      Array.isArray(row.errors) && row.errors.every((error) => typeof error === "string"),
    );
}

export async function items<T>(response: Response | null, accepts: (value: unknown) => value is T) {
  const data = await readResponse(response, (value): value is { items: T[] } =>
    record(value) && Array.isArray(value.items) && value.items.every(accepts),
  );
  return data?.items ?? null;
}
