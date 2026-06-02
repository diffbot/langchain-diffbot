import type { QueryResponse } from "./types";

export async function postQuery(question: string): Promise<QueryResponse> {
  const res = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* response wasn't JSON; keep the status text */
    }
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json();
}
