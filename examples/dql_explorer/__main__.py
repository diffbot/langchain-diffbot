"""Launch the DQL Explorer web server: `python -m dql_explorer`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the FastAPI app with uvicorn."""
    host = os.environ.get("DQL_EXPLORER_HOST", "127.0.0.1")
    port = int(os.environ.get("DQL_EXPLORER_PORT", "8000"))
    # Auto-reload the backend on code changes (set by ./dev.sh).
    reload = os.environ.get("DQL_EXPLORER_RELOAD") == "1"
    if reload:
        vite_url = os.environ.get("DQL_EXPLORER_VITE_URL", "http://localhost:5173/")
        print(
            f"DQL Explorer dev: API on http://{host}:{port}, open the UI at {vite_url}"
        )
    else:
        print(f"DQL Explorer running at http://{host}:{port}")
    uvicorn.run("dql_explorer.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
