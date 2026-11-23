"use server";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { apiRequest, readResponse, record, sessionCookie, sessionLifetime, sessionPattern } from "./api";

async function checkedOrigin() {
  const origin = new URL(process.env.APP_ORIGIN ?? "http://localhost:3000");
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
  if (origin.protocol !== "https:" && (origin.protocol !== "http:" || !loopback)) {
    redirect("/?status=origin");
  }
  if ((await headers()).get("origin") !== origin.origin) {
    redirect("/?status=origin");
  }
  return origin;
}

export async function signIn(form: FormData) {
  const origin = await checkedOrigin();
  const tenant = form.get("tenant_id");
  const email = form.get("email");
  const password = form.get("password");
  if (
    typeof tenant !== "string" || tenant.length !== 36 ||
    typeof email !== "string" || !email.trim() || email.length > 254 ||
    typeof password !== "string" || !password || password.length > 256
  ) {
    redirect("/?status=invalid");
  }

  const login = await apiRequest("/auth/login", undefined, {
    tenant_id: tenant,
    email: email.trim(),
    password,
  });
  if (login?.status === 401 || login?.status === 422) {
    redirect("/?status=invalid");
  }
  const data = await readResponse(login, (value): value is { access_token: string } =>
    record(value) && typeof value.access_token === "string" && sessionPattern.test(value.access_token),
  );
  if (!data) redirect("/?status=unavailable");
  (await cookies()).set(sessionCookie, data.access_token, {
    httpOnly: true,
    sameSite: "strict",
    secure: origin.protocol === "https:",
    path: "/",
    maxAge: sessionLifetime,
  });
  redirect("/");
}

export async function signOut() {
  await checkedOrigin();
  const jar = await cookies();
  const token = jar.get(sessionCookie)?.value;
  if (token && sessionPattern.test(token)) {
    const logout = await apiRequest("/auth/logout", token);
    if (logout?.status !== 204 && logout?.status !== 401) {
      redirect("/?status=signout");
    }
  }
  jar.delete(sessionCookie);
  redirect("/");
}
