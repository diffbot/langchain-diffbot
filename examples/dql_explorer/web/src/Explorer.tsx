import { useState } from "react";
import { postQuery } from "./api";
import type { QueryResponse } from "./types";

const EXAMPLES = [
  "US robotics companies with the most employees",
  "AI companies headquartered in San Francisco",
  "Articles about large language models, newest first",
  "Most recent IPOs by companies with more than 4,000 employees",
  "Latest mergers and acquisitions involving companies with 4,000+ employees",
];

export function Explorer() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  async function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await postQuery(trimmed));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">DQL Builder</h1>
        <p className="mt-1 max-w-prose text-slate-500 dark:text-slate-400">
          Ask in plain English. An agent inspects the Knowledge Graph ontology,
          probes query variants, writes the DQL, and the results come back as a
          table.
        </p>
      </header>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          void run(question);
        }}
      >
        <input
          type="text"
          value={question}
          placeholder="e.g. US robotics companies with the most employees"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={loading}
          autoFocus
          className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-base outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:placeholder:text-slate-500"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Working…" : "Run"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            disabled={loading}
            onClick={() => {
              setQuestion(ex);
              void run(ex);
            }}
            className="rounded-full border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {ex}
          </button>
        ))}
      </div>

      {loading && (
        <p className="mt-6 text-slate-500 dark:text-slate-400">
          Authoring DQL and querying the graph…
        </p>
      )}
      {error && <ErrorBox>{error}</ErrorBox>}

      {result && <Results result={result} />}
    </div>
  );
}

function ErrorBox({ children }: { children: React.ReactNode }) {
  return (
    <p className="mt-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2.5 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
      {children}
    </p>
  );
}

function Results({ result }: { result: QueryResponse }) {
  return (
    <section className="mt-8">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <span className="rounded-md bg-blue-100 px-2 py-0.5 text-sm font-semibold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          {result.entity_type || "—"}
        </span>
        {result.error == null && (
          <span className="text-sm text-slate-500 dark:text-slate-400">
            {result.hits.toLocaleString()} total match
            {result.hits === 1 ? "" : "es"} · showing {result.rows.length}
          </span>
        )}
        {result.trace_url && (
          <a
            href={result.trace_url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto text-sm text-blue-600 hover:underline dark:text-blue-400"
          >
            View trace in LangSmith ↗
          </a>
        )}
      </div>

      {result.dql && (
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-[13px] leading-relaxed text-slate-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-100">
          {result.dql}
        </pre>
      )}
      {result.notes && (
        <p className="mt-2 text-sm italic text-slate-500 dark:text-slate-400">
          {result.notes}
        </p>
      )}

      {result.steps.length > 0 && (
        <details className="my-3 text-sm">
          <summary className="cursor-pointer text-slate-500 dark:text-slate-400">
            {result.steps.length} agent step(s)
          </summary>
          <ol className="my-2 list-decimal space-y-1.5 pl-6">
            {result.steps.map((s, i) => (
              <li key={i}>
                <code className="font-mono">{s.tool}</code>
                <span className="text-slate-500 dark:text-slate-400">
                  ({JSON.stringify(s.args)})
                </span>
                {s.output && (
                  <div className="font-mono text-xs text-slate-400 dark:text-slate-500">
                    → {s.output}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </details>
      )}

      {result.error ? (
        <ErrorBox>{result.error}</ErrorBox>
      ) : result.rows.length === 0 ? (
        <p className="mt-4 text-slate-500 dark:text-slate-400">No results.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                {result.columns.map((c) => (
                  <th
                    key={c.path}
                    className="border-b-2 border-slate-300 px-2.5 py-2 text-left font-semibold dark:border-slate-600"
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                  {result.columns.map((c) => (
                    <td
                      key={c.path}
                      className="border-b border-slate-200 px-2.5 py-2 align-top dark:border-slate-700"
                    >
                      {renderCell(row[c.path], c.path)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function renderCell(value: string | undefined, path: string) {
  if (!value) return <span className="text-slate-300 dark:text-slate-600">—</span>;
  const link = (href: string) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-blue-600 hover:underline dark:text-blue-400"
    >
      {value}
    </a>
  );
  if (/^https?:\/\//.test(value)) return link(value);
  // Heuristic: *Uri / *url columns holding a bare domain become links.
  if (/uri$|url$/i.test(path) && /\./.test(value) && !value.includes(" ")) {
    return link(`https://${value}`);
  }
  return value;
}
