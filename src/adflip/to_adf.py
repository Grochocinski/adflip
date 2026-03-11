"""Convert extended Markdown (with Confluence directives) to ADF JSON.

Parses HTML comment directives back into proper ADF nodes, and converts
standard Markdown into ADF block/inline nodes using mistune.
"""

from __future__ import annotations

import json
import re
from typing import Any

import mistune
from mistune.plugins.table import table as mistune_table_plugin

# Regex patterns for directive parsing
_DIRECTIVE_OPEN = re.compile(
    r"<!-- confluence:(\w+)(.*?) -->"
)
_DIRECTIVE_CLOSE = re.compile(
    r"<!-- /confluence:(\w+) -->"
)
_DIRECTIVE_SELF_CLOSING = re.compile(
    r"<!-- confluence:(\w+)(.*?) /-->"
)
_DIRECTIVE_INLINE = re.compile(
    r'<!-- confluence:(\w+)(.*?) -->'
)
_DIRECTIVE_INLINE_CLOSE = re.compile(
    r'<!-- /confluence:(\w+) -->'
)

# Attribute parsing from directive strings like: type="info" title="Note"
_ATTR_PATTERN = re.compile(r'(\w+)="([^"]*)"')


def markdown_to_adf(markdown: str) -> dict[str, Any]:
    """Convert extended Markdown to an ADF document.

    Args:
        markdown: Markdown string, optionally containing Confluence directives.

    Returns:
        ADF document dict with "type": "doc".
    """
    blocks = _split_into_blocks(markdown)
    content = _convert_blocks_to_adf(blocks)
    return {"type": "doc", "version": 1, "content": content}


def _parse_directive_attrs(attr_str: str) -> dict[str, str]:
    """Parse key="value" pairs from a directive attribute string."""
    return dict(_ATTR_PATTERN.findall(attr_str))


def _split_into_blocks(text: str) -> list[dict[str, Any]]:
    """Split text into a sequence of markdown blocks and directive blocks.

    Returns a list of dicts:
      - {"kind": "markdown", "text": "..."}
      - {"kind": "directive", "name": "panel", "attrs": {...}, "body": "..."}
      - {"kind": "self_closing_directive", "name": "extension", "attrs": {...}, "json_body": "..."}
    """
    blocks: list[dict[str, Any]] = []
    lines = text.split("\n")
    i = 0
    md_buffer: list[str] = []

    while i < len(lines):
        line = lines[i]

        # Check for self-closing directive (single-line): <!-- confluence:xxx ... /-->
        sc_match = _DIRECTIVE_SELF_CLOSING.search(line)
        if sc_match:
            _flush_md_buffer(md_buffer, blocks)
            name = sc_match.group(1)
            attr_str = sc_match.group(2)
            blocks.append({
                "kind": "self_closing_directive",
                "name": name,
                "attrs": _parse_directive_attrs(attr_str),
                "json_body": attr_str.strip(),
            })
            i += 1
            continue

        # Check for opening directive: <!-- confluence:xxx ... -->
        open_match = _DIRECTIVE_OPEN.match(line.strip())
        if open_match:
            close_tag = f"<!-- /confluence:{open_match.group(1)} -->"
            # Find matching close
            depth = 1
            body_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                if lines[j].strip() == close_tag:
                    depth -= 1
                    if depth == 0:
                        break
                elif _DIRECTIVE_OPEN.match(lines[j].strip()):
                    check_name = _DIRECTIVE_OPEN.match(lines[j].strip())
                    if check_name and check_name.group(1) == open_match.group(1):
                        depth += 1
                body_lines.append(lines[j])
                j += 1

            if depth == 0:
                _flush_md_buffer(md_buffer, blocks)
                blocks.append({
                    "kind": "directive",
                    "name": open_match.group(1),
                    "attrs": _parse_directive_attrs(open_match.group(2)),
                    "body": "\n".join(body_lines),
                })
                i = j + 1
                continue

        md_buffer.append(line)
        i += 1

    _flush_md_buffer(md_buffer, blocks)
    return blocks


def _flush_md_buffer(buffer: list[str], blocks: list[dict[str, Any]]) -> None:
    """Flush accumulated markdown lines into a markdown block."""
    if buffer:
        text = "\n".join(buffer).strip()
        if text:
            blocks.append({"kind": "markdown", "text": text})
        buffer.clear()


def _convert_blocks_to_adf(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert parsed blocks into ADF content nodes."""
    adf_nodes: list[dict[str, Any]] = []

    for block in blocks:
        if block["kind"] == "markdown":
            adf_nodes.extend(_markdown_to_adf_nodes(block["text"]))
        elif block["kind"] == "directive":
            adf_nodes.append(_directive_to_adf(block))
        elif block["kind"] == "self_closing_directive":
            adf_nodes.append(_self_closing_directive_to_adf(block))
        elif block["kind"] == "opaque_adf":
            adf_nodes.append(block["node"])

    return adf_nodes


def _directive_to_adf(block: dict[str, Any]) -> dict[str, Any]:
    """Convert a directive block back to its ADF node."""
    name = block["name"]
    attrs = block["attrs"]
    body = block["body"]

    if name == "panel":
        inner_blocks = _split_into_blocks(body)
        content = _convert_blocks_to_adf(inner_blocks)
        return {
            "type": "panel",
            "attrs": {"panelType": attrs.get("type", "info")},
            "content": content,
        }

    if name == "expand":
        inner_blocks = _split_into_blocks(body)
        content = _convert_blocks_to_adf(inner_blocks)
        return {
            "type": "expand",
            "attrs": {"title": attrs.get("title", "")},
            "content": content,
        }

    if name == "layout":
        return _parse_layout_directive(body)

    if name == "extension":
        # Try to parse body as JSON (opaque extension params)
        try:
            json_body = json.loads(body.strip()) if body.strip() else {}
        except json.JSONDecodeError:
            # Body is Markdown content (bodied extension)
            inner_blocks = _split_into_blocks(body)
            content = _convert_blocks_to_adf(inner_blocks)
            return {
                "type": "bodiedExtension",
                "attrs": attrs,
                "content": content,
            }
        return {
            "type": "extension",
            "attrs": {**attrs, **json_body} if isinstance(json_body, dict) else attrs,
        }

    if name == "adf":
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"type": "paragraph", "content": [{"type": "text", "text": body}]}

    # Unknown directive: wrap as extension
    return {
        "type": "extension",
        "attrs": {"extensionType": f"confluence:{name}", **attrs},
    }


def _self_closing_directive_to_adf(block: dict[str, Any]) -> dict[str, Any]:
    """Convert a self-closing directive to ADF."""
    name = block["name"]
    json_body = block.get("json_body", "")
    attrs = block.get("attrs", {})

    if name == "extension":
        try:
            parsed = json.loads(json_body) if json_body else {}
            if isinstance(parsed, dict):
                return {"type": "extension", "attrs": parsed}
        except json.JSONDecodeError:
            pass
        return {"type": "extension", "attrs": attrs}

    if name == "media":
        try:
            parsed = json.loads(json_body) if json_body else {}
            if isinstance(parsed, dict):
                return {"type": "media", "attrs": parsed}
        except json.JSONDecodeError:
            pass

    return {"type": "extension", "attrs": {"extensionType": f"confluence:{name}", **attrs}}


def _parse_layout_directive(body: str) -> dict[str, Any]:
    """Parse layout directive body into layoutSection/layoutColumn ADF nodes."""
    columns: list[dict[str, Any]] = []
    col_blocks = re.split(r'<!-- confluence:column.*? -->', body)
    col_attrs = _ATTR_PATTERN.findall(body)

    width_idx = 0
    for col_body in col_blocks:
        col_body = re.sub(r'<!-- /confluence:column -->', '', col_body).strip()
        if not col_body:
            continue
        inner = _convert_blocks_to_adf(_split_into_blocks(col_body))
        col_node: dict[str, Any] = {
            "type": "layoutColumn",
            "content": inner,
        }
        if width_idx < len(col_attrs):
            col_node["attrs"] = {"width": col_attrs[width_idx][1]}
            width_idx += 1
        columns.append(col_node)

    return {"type": "layoutSection", "content": columns}


def _unescape_table_pipes(nodes: list[dict[str, Any]]) -> None:
    """Remove backslash-escaped pipes in table cell text.

    Markdown tables require \\| to prevent | from being parsed as a cell
    delimiter. ADF tables are structural, so the escapes must be stripped.
    """
    for node in nodes:
        if "text" in node and "\\|" in node["text"]:
            node["text"] = node["text"].replace("\\|", "|")
        if "content" in node and isinstance(node["content"], list):
            _unescape_table_pipes(node["content"])


# -- Markdown to ADF using mistune --

def _markdown_to_adf_nodes(text: str) -> list[dict[str, Any]]:
    """Convert a plain Markdown string to ADF block nodes."""
    # Pre-process inline directives to protect them from mistune
    text, inline_map = _protect_inline_directives(text)

    md = mistune.create_markdown(renderer=_AdfRenderer(), plugins=[mistune_table_plugin])
    result = md(text)

    if not isinstance(result, list):
        return [{"type": "paragraph", "content": [{"type": "text", "text": str(result)}]}]

    # Restore inline directives
    _restore_inline_directives(result, inline_map)
    return result


_INLINE_PLACEHOLDER_PREFIX = "\x00ADFLIP_INLINE_"
_INLINE_DIRECTIVE_RE = re.compile(
    r'<!-- confluence:(\w+)(.*?) -->'
    r'(.*?)'
    r'<!-- /confluence:\1 -->',
    re.DOTALL,
)
_INLINE_SELF_RE = re.compile(
    r'<!-- confluence:(\w+)(.*?) -->'
)


def _protect_inline_directives(text: str) -> tuple[str, dict[str, dict[str, Any]]]:
    """Replace inline directives with placeholders to protect them from Markdown parsing."""
    inline_map: dict[str, dict[str, Any]] = {}
    counter = 0

    def replace_paired(m: re.Match) -> str:
        nonlocal counter
        key = f"{_INLINE_PLACEHOLDER_PREFIX}{counter}\x00"
        counter += 1
        name = m.group(1)
        attrs = _parse_directive_attrs(m.group(2))
        inner_text = m.group(3)
        inline_map[key] = _inline_directive_to_adf(name, attrs, inner_text)
        return key

    text = _INLINE_DIRECTIVE_RE.sub(replace_paired, text)

    def replace_self(m: re.Match) -> str:
        nonlocal counter
        key = f"{_INLINE_PLACEHOLDER_PREFIX}{counter}\x00"
        counter += 1
        name = m.group(1)
        attrs = _parse_directive_attrs(m.group(2))
        inline_map[key] = _inline_directive_to_adf(name, attrs, "")
        return key

    text = _INLINE_SELF_RE.sub(replace_self, text)

    return text, inline_map


def _inline_directive_to_adf(
    name: str, attrs: dict[str, str], inner_text: str
) -> dict[str, Any]:
    """Convert an inline directive to its ADF node."""
    if name == "status":
        return {
            "type": "status",
            "attrs": {"text": attrs.get("text", ""), "color": attrs.get("color", "")},
        }
    if name == "mention":
        return {
            "type": "mention",
            "attrs": {"id": attrs.get("id", ""), "text": attrs.get("text", "")},
        }
    if name == "date":
        return {
            "type": "date",
            "attrs": {"timestamp": attrs.get("timestamp", "")},
        }
    if name == "color":
        return {
            "type": "text",
            "text": inner_text,
            "marks": [{"type": "textColor", "attrs": {"color": attrs.get("color", "")}}],
        }
    # Generic inline directive
    return {
        "type": "text",
        "text": inner_text or f"[{name}]",
        "marks": [],
    }


def _restore_inline_directives(
    nodes: list[dict[str, Any]], inline_map: dict[str, dict[str, Any]]
) -> None:
    """Walk ADF nodes and replace placeholder strings with inline ADF nodes."""
    for i, node in enumerate(nodes):
        if node.get("type") == "text":
            text = node.get("text", "")
            if _INLINE_PLACEHOLDER_PREFIX in text:
                expanded = _expand_placeholders(text, inline_map, node.get("marks", []))
                if expanded:
                    nodes[i:i + 1] = expanded
        if "content" in node and isinstance(node["content"], list):
            _restore_inline_directives(node["content"], inline_map)


def _expand_placeholders(
    text: str, inline_map: dict[str, dict[str, Any]], marks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Split text on placeholders and expand them into ADF nodes."""
    result: list[dict[str, Any]] = []
    parts = re.split(f"({re.escape(_INLINE_PLACEHOLDER_PREFIX)}\\d+\x00)", text)

    for part in parts:
        if part in inline_map:
            result.append(inline_map[part])
        elif part:
            node: dict[str, Any] = {"type": "text", "text": part}
            if marks:
                node["marks"] = marks
            result.append(node)

    return result


class _AdfRenderer(mistune.BaseRenderer):
    """Mistune renderer that produces ADF nodes instead of HTML."""

    NAME = "adf"

    def __call__(self, tokens: list[dict[str, Any]], state: Any) -> list[dict[str, Any]]:
        adf_nodes: list[dict[str, Any]] = []
        for tok in tokens:
            children = tok.get("children")
            result = self._render_token(tok, children, state)
            if result is not None:
                if isinstance(result, list):
                    adf_nodes.extend(result)
                else:
                    adf_nodes.append(result)
        return adf_nodes

    def _render_token(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        tok_type = token.get("type", "")
        method = getattr(self, f"_render_{tok_type}", None)
        if method:
            return method(token, children, state)
        return None

    def _render_paragraph(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        inline = self._render_children_inline(children, state)
        return {"type": "paragraph", "content": inline} if inline else {"type": "paragraph"}

    def _render_block_text(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        inline = self._render_children_inline(children, state)
        return {"type": "paragraph", "content": inline} if inline else {"type": "paragraph"}

    def _render_heading(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        level = token.get("attrs", {}).get("level", 1)
        inline = self._render_children_inline(children, state)
        node: dict[str, Any] = {
            "type": "heading",
            "attrs": {"level": level},
        }
        if inline:
            node["content"] = inline
        return node

    def _render_thematic_break(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        return {"type": "rule"}

    def _render_block_code(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        info = token.get("attrs", {}).get("info", "")
        raw = token.get("raw", token.get("text", ""))
        if raw.endswith("\n"):
            raw = raw[:-1]
        node: dict[str, Any] = {"type": "codeBlock", "content": [{"type": "text", "text": raw}]}
        if info:
            node["attrs"] = {"language": info}
        return node

    def _render_block_quote(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        inner = self(children, state) if children else []
        return {"type": "blockquote", "content": inner}

    def _render_list(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        attrs = token.get("attrs", {})
        ordered = attrs.get("ordered", False)
        items = []
        if children:
            for child in children:
                if child.get("type") == "list_item":
                    item_children = child.get("children", [])
                    item_content = self(item_children, state) if item_children else []
                    items.append({"type": "listItem", "content": item_content})

        list_type = "orderedList" if ordered else "bulletList"
        node: dict[str, Any] = {"type": list_type, "content": items}
        if ordered:
            start = attrs.get("start", 1)
            if start != 1:
                node["attrs"] = {"order": start}
        return node

    def _render_table(
        self, token: dict[str, Any], children: Any, state: Any
    ) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        if not children:
            return {"type": "table", "content": rows}

        for section in children:
            section_type = section.get("type", "")
            if section_type == "table_head":
                header_cells = self._render_table_cells(
                    section.get("children", []), is_header=True, state=state
                )
                rows.append({"type": "tableRow", "content": header_cells})
            elif section_type == "table_body":
                for row in section.get("children", []):
                    if row.get("type") == "table_row":
                        body_cells = self._render_table_cells(
                            row.get("children", []), is_header=False, state=state
                        )
                        rows.append({"type": "tableRow", "content": body_cells})

        return {"type": "table", "content": rows}

    def _render_table_cells(
        self,
        cells: list[dict[str, Any]],
        is_header: bool,
        state: Any,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        cell_type = "tableHeader" if is_header else "tableCell"
        for cell in cells:
            if cell.get("type") != "table_cell":
                continue
            inline = self._render_children_inline(cell.get("children"), state)
            _unescape_table_pipes(inline)
            para = {"type": "paragraph", "content": inline} if inline else {"type": "paragraph"}
            result.append({"type": cell_type, "content": [para]})
        return result

    def _render_children_inline(
        self, children: Any, state: Any
    ) -> list[dict[str, Any]]:
        """Render inline children into ADF inline nodes."""
        if not children:
            return []
        nodes: list[dict[str, Any]] = []
        for child in children:
            rendered = self._render_inline_token(child)
            if rendered:
                if isinstance(rendered, list):
                    nodes.extend(rendered)
                else:
                    nodes.append(rendered)
        return nodes

    def _render_inline_token(
        self, token: dict[str, Any]
    ) -> dict[str, Any] | list[dict[str, Any]] | None:
        tok_type = token.get("type", "")

        if tok_type == "text":
            raw = token.get("raw", token.get("text", ""))
            if not raw:
                return None
            return {"type": "text", "text": raw}

        if tok_type == "codespan":
            raw = token.get("raw", token.get("text", ""))
            return {"type": "text", "text": raw, "marks": [{"type": "code"}]}

        if tok_type == "strong":
            inner = self._flatten_inline(token.get("children", []))
            for node in inner:
                marks = node.get("marks", [])
                marks.append({"type": "strong"})
                node["marks"] = marks
            return inner

        if tok_type == "emphasis":
            inner = self._flatten_inline(token.get("children", []))
            for node in inner:
                marks = node.get("marks", [])
                marks.append({"type": "em"})
                node["marks"] = marks
            return inner

        if tok_type == "strikethrough":
            inner = self._flatten_inline(token.get("children", []))
            for node in inner:
                marks = node.get("marks", [])
                marks.append({"type": "strike"})
                node["marks"] = marks
            return inner

        if tok_type == "link":
            attrs = token.get("attrs", {})
            href = attrs.get("url", "")
            title = attrs.get("title")
            inner = self._flatten_inline(token.get("children", []))
            link_mark: dict[str, Any] = {"type": "link", "attrs": {"href": href}}
            if title:
                link_mark["attrs"]["title"] = title
            for node in inner:
                marks = node.get("marks", [])
                marks.append(link_mark)
                node["marks"] = marks
            return inner

        if tok_type == "image":
            attrs = token.get("attrs", {})
            src = attrs.get("src", attrs.get("url", ""))
            alt = attrs.get("alt", "")
            return {
                "type": "mediaSingle",
                "content": [{
                    "type": "media",
                    "attrs": {"url": src, "type": "external", "alt": alt},
                }],
            }

        if tok_type == "softbreak":
            return {"type": "text", "text": " "}

        if tok_type == "linebreak":
            return {"type": "hardBreak"}

        raw = token.get("raw", token.get("text", ""))
        if raw:
            return {"type": "text", "text": raw}
        return None

    def _flatten_inline(self, children: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Flatten inline children into a list of text nodes."""
        nodes: list[dict[str, Any]] = []
        for child in children:
            rendered = self._render_inline_token(child)
            if rendered:
                if isinstance(rendered, list):
                    nodes.extend(rendered)
                else:
                    nodes.append(rendered)
        return nodes
