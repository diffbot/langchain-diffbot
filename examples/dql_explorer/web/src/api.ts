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

/*
  Stream an answer from ChatDiffbot (`POST /api/ask`). The backend emits
  Server-Sent Events — `token` frames carry text, an `error` frame carries a
  failure message, and a `done` frame ends the stream. `onToken` is called with
  each piece of text as it arrives; the promise resolves when the stream ends and
  rejects on an error frame (or a transport failure). Pass `signal` to abort.
*/
export async function streamAsk(
  question: string,
  onToken: (text: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Request failed (${res.status}): ${res.statusText}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    /*
      SSE frames are separated by a blank line. Process every complete frame in
      the buffer and keep the trailing partial frame for the next read.
    */
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);

      let event = "message";
      const dataLines: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      }
      const payload = dataLines.join("\n");

      if (event === "done") return;
      if (event === "error") {
        const message = payload ? JSON.parse(payload).message : "stream error";
        throw new Error(message);
      }
      if (event === "token" && payload) {
        onToken(JSON.parse(payload).text);
      }
    }
  }
}
