/* Mirrors the JSON returned by the FastAPI backend (`POST /api/query`). */

export interface Column {
  path: string;
  label: string;
}

export interface Step {
  tool: string;
  args: Record<string, unknown>;
  output: string;
}

export interface QueryResponse {
  question: string;
  entity_type: string;
  dql: string;
  notes: string | null;
  columns: Column[];
  rows: Array<Record<string, string>>;
  hits: number;
  steps: Step[];
  trace_url: string | null;
  error: string | null;
}
