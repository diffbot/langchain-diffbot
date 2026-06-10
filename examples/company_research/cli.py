"""CLI entry point."""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv
from langchain.messages import AIMessage, HumanMessage, ToolMessage

from company_research.agent import build_agent


def _format_event(message) -> str | None:
    if isinstance(message, ToolMessage):
        return f"  ↳ tool {message.name}: {str(message.content)[:200]}..."
    if isinstance(message, AIMessage):
        if message.tool_calls:
            calls = ", ".join(f"{c['name']}({c['args']})" for c in message.tool_calls)
            return f"  ▸ calling: {calls}"
        if isinstance(message.content, str) and message.content.strip():
            return f"\n{message.content}"
    return None


def main() -> int:
    """Run a single research question through the agent."""
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Ask the Diffbot KG a company-research question.",
    )
    parser.add_argument("question", nargs="+", help="Natural-language question.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress intermediate tool-call traces; print only the final answer.",
    )
    args = parser.parse_args()
    question = " ".join(args.question)

    agent = build_agent()
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    messages = result["messages"]

    if args.quiet:
        final = messages[-1]
        if isinstance(final, AIMessage) and isinstance(final.content, str):
            print(final.content)
        return 0

    for msg in messages[1:]:  # skip the human prompt
        rendered = _format_event(msg)
        if rendered:
            print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
