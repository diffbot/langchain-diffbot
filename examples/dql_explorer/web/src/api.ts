import type {
  DashboardRequest,
  DashboardResponse,
  QueryResponse,
} from "./types";

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const parsed = await res.json();
      detail = parsed.detail ?? detail;
    } catch {
      /* response wasn't JSON; keep the status text */
    }
    throw new Error(`Request failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export function postQuery(question: string): Promise<QueryResponse> {
  return postJSON<QueryResponse>("/api/query", { question });
}

export function postDashboard(
  req: DashboardRequest,
): Promise<DashboardResponse> {
  return postJSON<DashboardResponse>("/api/dashboard", req);
}
