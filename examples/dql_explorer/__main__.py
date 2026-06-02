"""Launch the DQL Explorer web server: `python -m dql_explorer`."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Run the FastAPI app with uvicorn."""
    host = os.environ.get("DQL_EXPLORER_HOST", "127.0.0.1")
    port = int(os.environ.get("DQL_EXPLORER_PORT", "8000"))
    print(f"DQL Explorer running at http://{host}:{port}")
    uvicorn.run("dql_explorer.server:app", host=host, port=port)


if __name__ == "__main__":
    main()
