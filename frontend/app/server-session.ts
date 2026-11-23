import "server-only";

import { cookies, headers } from "next/headers";
import { redirect } from "next/navigation";
import { sessionCookie, sessionPattern } from "./api";

export async function checkedOrigin(deniedPath = "/?status=origin") {
  const origin = new URL(process.env.APP_ORIGIN ?? "http://localhost:3000");
  const loopback = ["localhost", "127.0.0.1", "[::1]"].includes(origin.hostname);
  if (origin.protocol !== "https:" && (origin.protocol !== "http:" || !loopback)) {
    redirect(deniedPath);
  }
  if ((await headers()).get("origin") !== origin.origin) {
    redirect(deniedPath);
  }
  return origin;
}

export async function currentToken() {
  const token = (await cookies()).get(sessionCookie)?.value;
  return token && sessionPattern.test(token) ? token : null;
}
