import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { streamAsk } from "./api";

const EXAMPLES = [
  "Who founded Diffbot, and when?",
  "What does Diffbot's Knowledge Graph contain?",
  "Summarize OpenAI's funding history.",
  "Which companies acquired robotics startups in the last year?",
];

export function Ask() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track the active stream so a new question (or unmount) cancels the old one.
  const abortRef = useRef<AbortController | null>(null);

  async function run(q: string) {
    const trimmed = q.trim();
    if (!trimmed || streaming) return;

    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setStreaming(true);
    setError(null);
    setAnswer("");
    try {
      await streamAsk(trimmed, (text) => setAnswer((a) => a + text), ctrl.signal);
    } catch (e) {
      if (!ctrl.signal.aborted) {
        setError(e instanceof Error ? e.message : String(e));
      }
    } finally {
      if (abortRef.current === ctrl) abortRef.current = null;
      setStreaming(false);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Ask Diffbot</h1>
        <p className="mt-1 max-w-prose text-slate-500 dark:text-slate-400">
          Where the DQL Builder authors a precise query, this just asks Diffbot's
          own LLM — grounded in the Knowledge Graph and the live web. Powered by{" "}
          <code className="font-mono text-[0.95em]">ChatDiffbot</code>, which
          streams tokens natively.
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
          placeholder="e.g. Who founded Diffbot, and when?"
          onChange={(e) => setQuestion(e.target.value)}
          disabled={streaming}
          autoFocus
          className="flex-1 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-base outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/30 disabled:opacity-50 dark:border-slate-600 dark:bg-slate-800 dark:placeholder:text-slate-500"
        />
        <button
          type="submit"
          disabled={streaming || !question.trim()}
          className="rounded-lg bg-blue-600 px-5 py-2.5 font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {streaming ? "Asking…" : "Ask"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            disabled={streaming}
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

      {error && (
        <p className="mt-4 rounded-lg border border-red-300 bg-red-50 px-3 py-2.5 text-red-700 dark:border-red-900 dark:bg-red-950/50 dark:text-red-300">
          {error}
        </p>
      )}

      {(answer || streaming) && (
        <section className="mt-8">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-700 dark:bg-slate-800/60">
            {/*
              Diffbot's RAG LLM emits markdown (headings, lists, links, tables),
              so render it as such — re-parsing the full string each token is
              cheap for these short answers. `prose` (Tailwind typography) styles
              the elements; `dark:prose-invert` flips it for dark mode.
            */}
            <div className="prose prose-slate max-w-none text-[15px] leading-relaxed dark:prose-invert">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
            </div>
            {streaming && (
              <span className="inline-block animate-pulse text-slate-800 dark:text-slate-100">
                ▌
              </span>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
