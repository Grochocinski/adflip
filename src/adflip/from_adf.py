"""Convert ADF (Atlassian Document Format) JSON to extended Markdown.

Standard ADF nodes become Markdown. Confluence-specific nodes (panels, expands,
status, extensions, etc.) become HTML comment directives that round-trip losslessly.
"""

from __future__ import annotations

import json
from typing import Any


def adf_to_markdown(adf: dict[str, Any]) -> str:
    """Convert an ADF document to extended Markdown.

    Args:
        adf: ADF document dict with "type": "doc" and "content" list.

    Returns:
        Markdown string with Confluence directives as HTML comments.
    """
    if adf.get("type") != "doc":
        raise ValueError(f"Expected ADF doc node, got {adf.get('type')!r}")
    return _convert_block_nodes(adf.get("content", []))


def _convert_block_nodes(nodes: list[dict[str, Any]], indent: str = "") -> str:
    """Convert a list of block-level ADF nodes to Markdown."""
    parts: list[str] = []
    for node in nodes:
        result = _convert_block_node(node, indent)
        if result is not None:
            parts.append(result)
    return "\n\n".join(parts)


def _convert_block_node(node: dict[str, Any], indent: str = "") -> str | None:
    """Convert a single block-level ADF node to Markdown."""
    node_type = node.get("type", "")
    converter = _BLOCK_CONVERTERS.get(node_type)
    if converter:
        return converter(node, indent)
    return _convert_unknown_block(node, indent)


def _convert_paragraph(node: dict[str, Any], indent: str = "") -> str:
    text = _convert_inline_nodes(node.get("content", []))
    return indent + text if text else ""


def _convert_heading(node: dict[str, Any], indent: str = "") -> str:
    level = node.get("attrs", {}).get("level", 1)
    text = _convert_inline_nodes(node.get("content", []))
    return indent + "#" * level + " " + text


def _convert_bullet_list(node: dict[str, Any], indent: str = "") -> str:
    items = []
    for item in node.get("content", []):
        items.append(_convert_list_item(item, indent, bullet="- "))
    return "\n".join(items)


def _convert_ordered_list(node: dict[str, Any], indent: str = "") -> str:
    items = []
    order = node.get("attrs", {}).get("order", 1)
    for i, item in enumerate(node.get("content", []), start=order):
        items.append(_convert_list_item(item, indent, bullet=f"{i}. "))
    return "\n".join(items)


def _convert_list_item(node: dict[str, Any], indent: str, bullet: str) -> str:
    content = node.get("content", [])
    lines: list[str] = []
    for i, child in enumerate(content):
        if i == 0 and child.get("type") == "paragraph":
            text = _convert_inline_nodes(child.get("content", []))
            lines.append(f"{indent}{bullet}{text}")
        elif child.get("type") in ("bulletList", "orderedList"):
            nested = _convert_block_node(child, indent + "  ")
            if nested:
                lines.append(nested)
        else:
            text = _convert_block_node(child, indent + "  ")
            if text:
                lines.append(text)
    return "\n".join(lines)


def _convert_task_list(node: dict[str, Any], indent: str = "") -> str:
    items = []
    for item in node.get("content", []):
        attrs = item.get("attrs", {})
        checked = attrs.get("state") == "DONE"
        checkbox = "[x]" if checked else "[ ]"
        text = _convert_inline_nodes(
            _first_paragraph_content(item.get("content", []))
        )
        items.append(f"{indent}- {checkbox} {text}")

        for child in item.get("content", [])[1:]:
            nested = _convert_block_node(child, indent + "  ")
            if nested:
                items.append(nested)
    return "\n".join(items)


def _first_paragraph_content(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract inline content from the first paragraph in a list of nodes."""
    for node in content:
        if node.get("type") == "paragraph":
            return node.get("content", [])
    return []


def _convert_code_block(node: dict[str, Any], indent: str = "") -> str:
    lang = node.get("attrs", {}).get("language") or ""
    text = _extract_text(node)
    return f"{indent}```{lang}\n{text}\n{indent}```"


def _convert_blockquote(node: dict[str, Any], indent: str = "") -> str:
    inner = _convert_block_nodes(node.get("content", []))
    lines = inner.split("\n")
    return "\n".join(f"{indent}> {line}" for line in lines)


def _convert_rule(node: dict[str, Any], indent: str = "") -> str:
    return indent + "---"


def _convert_table(node: dict[str, Any], indent: str = "") -> str:
    rows = node.get("content", [])
    if not rows:
        return ""

    table_lines: list[str] = []
    first_row = True

    for row in rows:
        cells = row.get("content", [])
        cell_texts = []
        for cell in cells:
            cell_content = _convert_block_nodes(cell.get("content", []))
            cell_content = cell_content.replace("\n", " ")
            cell_texts.append(cell_content)

        table_lines.append(indent + "| " + " | ".join(cell_texts) + " |")

        if first_row:
            separators = ["---"] * len(cell_texts)
            table_lines.append(indent + "| " + " | ".join(separators) + " |")
            first_row = False

    return "\n".join(table_lines)


def _convert_media_single(node: dict[str, Any], indent: str = "") -> str:
    for child in node.get("content", []):
        if child.get("type") == "media":
            return _convert_media_node(child, indent)
    return ""


def _convert_media_node(node: dict[str, Any], indent: str = "") -> str:
    attrs = node.get("attrs", {})
    media_type = attrs.get("type", "")
    alt = attrs.get("alt", "")

    if media_type == "external":
        url = attrs.get("url", "")
        return f"{indent}![{alt}]({url})"

    # Confluence-hosted media: preserve as self-closing directive
    attrs_json = json.dumps(attrs, separators=(",", ":"))
    return f"{indent}<!-- confluence:media {attrs_json} /-->"


# -- Confluence-specific block nodes: wrap in HTML comment directives --

def _convert_panel(node: dict[str, Any], indent: str = "") -> str:
    attrs = node.get("attrs", {})
    panel_type = attrs.get("panelType", "info")
    inner = _convert_block_nodes(node.get("content", []), indent)
    return (
        f'{indent}<!-- confluence:panel type="{panel_type}" -->\n'
        f"{inner}\n"
        f"{indent}<!-- /confluence:panel -->"
    )


def _convert_expand(node: dict[str, Any], indent: str = "") -> str:
    attrs = node.get("attrs", {})
    title = attrs.get("title", "")
    inner = _convert_block_nodes(node.get("content", []), indent)
    return (
        f'{indent}<!-- confluence:expand title="{title}" -->\n'
        f"{inner}\n"
        f"{indent}<!-- /confluence:expand -->"
    )


def _convert_layout_section(node: dict[str, Any], indent: str = "") -> str:
    columns: list[str] = []
    for col in node.get("content", []):
        if col.get("type") == "layoutColumn":
            width = col.get("attrs", {}).get("width", "")
            inner = _convert_block_nodes(col.get("content", []), indent)
            columns.append(
                f'{indent}<!-- confluence:column width="{width}" -->\n'
                f"{inner}\n"
                f"{indent}<!-- /confluence:column -->"
            )
    return (
        f"{indent}<!-- confluence:layout -->\n"
        + "\n\n".join(columns)
        + f"\n{indent}<!-- /confluence:layout -->"
    )


def _convert_extension(node: dict[str, Any], indent: str = "") -> str:
    attrs = node.get("attrs", {})
    attrs_json = json.dumps(attrs, separators=(",", ":"))

    if node.get("type") == "bodiedExtension":
        inner = _convert_block_nodes(node.get("content", []), indent)
        return (
            f"{indent}<!-- confluence:extension {attrs_json} -->\n"
            f"{inner}\n"
            f"{indent}<!-- /confluence:extension -->"
        )

    return f"{indent}<!-- confluence:extension {attrs_json} /-->"


def _convert_unknown_block(node: dict[str, Any], indent: str = "") -> str:
    """Fallback: preserve unknown block nodes as opaque ADF JSON."""
    node_json = json.dumps(node, separators=(",", ":"))
    return (
        f"{indent}<!-- confluence:adf -->\n"
        f"{node_json}\n"
        f"{indent}<!-- /confluence:adf -->"
    )


# -- Inline node conversion --

def _convert_inline_nodes(nodes: list[dict[str, Any]]) -> str:
    """Convert a list of inline ADF nodes to Markdown."""
    parts: list[str] = []
    for node in nodes:
        parts.append(_convert_inline_node(node))
    return "".join(parts)


def _convert_inline_node(node: dict[str, Any]) -> str:
    node_type = node.get("type", "")

    if node_type == "text":
        return _convert_text_with_marks(node)
    if node_type == "hardBreak":
        return "  \n"
    if node_type == "emoji":
        attrs = node.get("attrs", {})
        short_name = attrs.get("shortName", "")
        return short_name
    if node_type == "status":
        attrs = node.get("attrs", {})
        text = attrs.get("text", "")
        color = attrs.get("color", "")
        return f'<!-- confluence:status text="{text}" color="{color}" -->'
    if node_type == "mention":
        attrs = node.get("attrs", {})
        mention_id = attrs.get("id", "")
        text = attrs.get("text", mention_id)
        return f'<!-- confluence:mention id="{mention_id}" text="{text}" -->'
    if node_type == "inlineCard":
        attrs = node.get("attrs", {})
        url = attrs.get("url", "")
        return f"[{url}]({url})"
    if node_type == "date":
        attrs = node.get("attrs", {})
        timestamp = attrs.get("timestamp", "")
        return f'<!-- confluence:date timestamp="{timestamp}" -->'
    if node_type == "media":
        return _convert_media_node(node)

    # Unknown inline: preserve as opaque
    return f"<!-- confluence:inline {json.dumps(node, separators=(',', ':'))} -->"


def _convert_text_with_marks(node: dict[str, Any]) -> str:
    text = node.get("text", "")
    marks = node.get("marks", [])

    if not marks:
        return text

    for mark in marks:
        mark_type = mark.get("type", "")
        attrs = mark.get("attrs", {})

        if mark_type == "strong":
            text = f"**{text}**"
        elif mark_type == "em":
            text = f"*{text}*"
        elif mark_type == "strike":
            text = f"~~{text}~~"
        elif mark_type == "code":
            text = f"`{text}`"
        elif mark_type == "link":
            href = attrs.get("href", "")
            title = attrs.get("title")
            if title:
                text = f'[{text}]({href} "{title}")'
            else:
                text = f"[{text}]({href})"
        elif mark_type == "subsup":
            variant = attrs.get("type", "sub")
            if variant == "sup":
                text = f"<sup>{text}</sup>"
            else:
                text = f"<sub>{text}</sub>"
        elif mark_type == "underline":
            text = f"<u>{text}</u>"
        elif mark_type == "textColor":
            color = attrs.get("color", "")
            text = f'<!-- confluence:color color="{color}" -->{text}<!-- /confluence:color -->'
        else:
            # Unknown mark: preserve as directive
            mark_json = json.dumps(mark, separators=(",", ":"))
            text = f"<!-- confluence:mark {mark_json} -->{text}<!-- /confluence:mark -->"

    return text


def _extract_text(node: dict[str, Any]) -> str:
    """Recursively extract raw text from an ADF node."""
    if node.get("type") == "text":
        return node.get("text", "")
    parts = []
    for child in node.get("content", []):
        parts.append(_extract_text(child))
    return "".join(parts)


_BLOCK_CONVERTERS = {
    "paragraph": _convert_paragraph,
    "heading": _convert_heading,
    "bulletList": _convert_bullet_list,
    "orderedList": _convert_ordered_list,
    "taskList": _convert_task_list,
    "codeBlock": _convert_code_block,
    "blockquote": _convert_blockquote,
    "rule": _convert_rule,
    "table": _convert_table,
    "mediaSingle": _convert_media_single,
    "media": _convert_media_node,
    "panel": _convert_panel,
    "expand": _convert_expand,
    "nestedExpand": _convert_expand,
    "layoutSection": _convert_layout_section,
    "extension": _convert_extension,
    "bodiedExtension": _convert_extension,
}
