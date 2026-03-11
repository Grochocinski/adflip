"""Tests for Markdown -> ADF conversion."""

from adflip.to_adf import markdown_to_adf


def _find_nodes(adf, node_type):
    """Recursively find all nodes of a given type."""
    results = []
    if isinstance(adf, dict):
        if adf.get("type") == node_type:
            results.append(adf)
        for v in adf.values():
            results.extend(_find_nodes(v, node_type))
    elif isinstance(adf, list):
        for item in adf:
            results.extend(_find_nodes(item, node_type))
    return results


def _find_text(adf):
    """Recursively extract all text content."""
    if isinstance(adf, dict):
        if adf.get("type") == "text":
            return adf.get("text", "")
        return "".join(_find_text(v) for v in adf.values())
    elif isinstance(adf, list):
        return "".join(_find_text(item) for item in adf)
    return ""


class TestBasicMarkdown:
    def test_paragraph(self):
        adf = markdown_to_adf("Hello world")
        assert adf["type"] == "doc"
        paragraphs = _find_nodes(adf, "paragraph")
        assert len(paragraphs) >= 1
        assert "Hello world" in _find_text(adf)

    def test_heading(self):
        adf = markdown_to_adf("# Title")
        headings = _find_nodes(adf, "heading")
        assert len(headings) >= 1
        assert headings[0]["attrs"]["level"] == 1
        assert "Title" in _find_text(headings[0])

    def test_code_block(self):
        adf = markdown_to_adf("```python\nx = 42\n```")
        blocks = _find_nodes(adf, "codeBlock")
        assert len(blocks) >= 1
        assert "x = 42" in _find_text(blocks[0])

    def test_blockquote(self):
        adf = markdown_to_adf("> Quoted text")
        quotes = _find_nodes(adf, "blockquote")
        assert len(quotes) >= 1
        assert "Quoted text" in _find_text(quotes[0])

    def test_bullet_list(self):
        adf = markdown_to_adf("- Item 1\n- Item 2")
        lists = _find_nodes(adf, "bulletList")
        assert len(lists) >= 1
        items = _find_nodes(lists[0], "listItem")
        assert len(items) == 2

    def test_ordered_list(self):
        adf = markdown_to_adf("1. First\n2. Second")
        lists = _find_nodes(adf, "orderedList")
        assert len(lists) >= 1

    def test_horizontal_rule(self):
        adf = markdown_to_adf("Before\n\n---\n\nAfter")
        rules = _find_nodes(adf, "rule")
        assert len(rules) >= 1


class TestInlineMarks:
    def test_bold(self):
        adf = markdown_to_adf("**bold**")
        text_nodes = _find_nodes(adf, "text")
        bold_nodes = [n for n in text_nodes if any(
            m.get("type") == "strong" for m in n.get("marks", [])
        )]
        assert len(bold_nodes) >= 1
        assert "bold" in bold_nodes[0]["text"]

    def test_italic(self):
        adf = markdown_to_adf("*italic*")
        text_nodes = _find_nodes(adf, "text")
        em_nodes = [n for n in text_nodes if any(
            m.get("type") == "em" for m in n.get("marks", [])
        )]
        assert len(em_nodes) >= 1

    def test_inline_code(self):
        adf = markdown_to_adf("`code`")
        text_nodes = _find_nodes(adf, "text")
        code_nodes = [n for n in text_nodes if any(
            m.get("type") == "code" for m in n.get("marks", [])
        )]
        assert len(code_nodes) >= 1

    def test_link(self):
        adf = markdown_to_adf("[click](https://example.com)")
        text_nodes = _find_nodes(adf, "text")
        link_nodes = [n for n in text_nodes if any(
            m.get("type") == "link" for m in n.get("marks", [])
        )]
        assert len(link_nodes) >= 1
        link_mark = next(
            m for m in link_nodes[0]["marks"] if m["type"] == "link"
        )
        assert link_mark["attrs"]["href"] == "https://example.com"


class TestConfluenceDirectives:
    def test_panel(self):
        md = (
            '<!-- confluence:panel type="info" -->\n'
            "Panel content\n"
            "<!-- /confluence:panel -->"
        )
        adf = markdown_to_adf(md)
        panels = _find_nodes(adf, "panel")
        assert len(panels) == 1
        assert panels[0]["attrs"]["panelType"] == "info"
        assert "Panel content" in _find_text(panels[0])

    def test_expand(self):
        md = (
            '<!-- confluence:expand title="Details" -->\n'
            "Hidden content\n"
            "<!-- /confluence:expand -->"
        )
        adf = markdown_to_adf(md)
        expands = _find_nodes(adf, "expand")
        assert len(expands) == 1
        assert expands[0]["attrs"]["title"] == "Details"
        assert "Hidden content" in _find_text(expands[0])

    def test_status_inline(self):
        md = 'Status: <!-- confluence:status text="Done" color="green" -->'
        adf = markdown_to_adf(md)
        statuses = _find_nodes(adf, "status")
        assert len(statuses) >= 1
        assert statuses[0]["attrs"]["text"] == "Done"
        assert statuses[0]["attrs"]["color"] == "green"

    def test_mention_inline(self):
        md = 'Assigned to <!-- confluence:mention id="abc123" text="@Alice" -->'
        adf = markdown_to_adf(md)
        mentions = _find_nodes(adf, "mention")
        assert len(mentions) >= 1
        assert mentions[0]["attrs"]["id"] == "abc123"

    def test_nested_panel_in_expand(self):
        md = (
            '<!-- confluence:expand title="Outer" -->\n'
            '<!-- confluence:panel type="warning" -->\n'
            "Nested content\n"
            "<!-- /confluence:panel -->\n"
            "<!-- /confluence:expand -->"
        )
        adf = markdown_to_adf(md)
        expands = _find_nodes(adf, "expand")
        assert len(expands) == 1
        panels = _find_nodes(expands[0], "panel")
        assert len(panels) == 1
        assert panels[0]["attrs"]["panelType"] == "warning"


class TestDocStructure:
    def test_doc_wrapper(self):
        adf = markdown_to_adf("Hello")
        assert adf["type"] == "doc"
        assert adf["version"] == 1
        assert "content" in adf
