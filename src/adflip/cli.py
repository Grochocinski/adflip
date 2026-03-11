"""CLI entrypoint for adflip."""

from __future__ import annotations

import argparse
import json
import sys

from adflip.from_adf import adf_to_markdown
from adflip.to_adf import markdown_to_adf


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="adflip",
        description="Bidirectional converter between Atlassian Document Format (ADF) and Markdown",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # from-adf: ADF JSON -> Markdown
    from_adf_parser = subparsers.add_parser(
        "from-adf",
        help="Convert ADF JSON to extended Markdown",
    )
    from_adf_parser.add_argument(
        "input",
        help="ADF JSON file (use - for stdin)",
    )
    from_adf_parser.add_argument(
        "-o", "--output",
        help="Output Markdown file (default: stdout)",
    )

    # to-adf: Markdown -> ADF JSON
    to_adf_parser = subparsers.add_parser(
        "to-adf",
        help="Convert extended Markdown to ADF JSON",
    )
    to_adf_parser.add_argument(
        "input",
        help="Markdown file (use - for stdin)",
    )
    to_adf_parser.add_argument(
        "-o", "--output",
        help="Output ADF JSON file (default: stdout)",
    )

    args = parser.parse_args(argv)

    if args.command == "from-adf":
        _cmd_from_adf(args)
    elif args.command == "to-adf":
        _cmd_to_adf(args)


def _cmd_from_adf(args: argparse.Namespace) -> None:
    adf = _read_json(args.input)
    markdown = adf_to_markdown(adf)
    _write_text(args.output, markdown)


def _cmd_to_adf(args: argparse.Namespace) -> None:
    markdown = _read_text(args.input)
    adf = markdown_to_adf(markdown)
    _write_text(args.output, json.dumps(adf, indent=2))


def _read_json(path: str) -> dict:
    if path == "-":
        return json.load(sys.stdin)
    with open(path) as f:
        return json.load(f)


def _read_text(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path) as f:
        return f.read()


def _write_text(path: str | None, text: str) -> None:
    if path is None:
        sys.stdout.write(text)
        if not text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        with open(path, "w") as f:
            f.write(text)
            if not text.endswith("\n"):
                f.write("\n")
