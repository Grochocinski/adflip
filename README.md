# adflip

Bidirectional converter between Atlassian Document Format (ADF) and Markdown.

Standard ADF nodes become Markdown. Confluence-specific nodes (panels, expands, status, extensions, macros) become HTML comment directives that round-trip losslessly.

## Install

```
pip install adflip
```

## Usage

### CLI

```bash
# ADF JSON -> Markdown
adflip from-adf page.adf.json -o page.md

# Markdown -> ADF JSON
adflip to-adf page.md -o page.adf.json

# Pipe from stdin
cat page.adf.json | adflip from-adf -
```

### Python API

```python
from adflip import adf_to_markdown, markdown_to_adf

# ADF dict -> Markdown string
markdown = adf_to_markdown(adf_doc)

# Markdown string -> ADF dict
adf_doc = markdown_to_adf(markdown_string)
```

## Extended Markdown format

Confluence-specific features use HTML comment directives (invisible in standard Markdown renderers):

```markdown
<!-- confluence:panel type="info" -->
This is an info panel.
<!-- /confluence:panel -->

<!-- confluence:expand title="Click to see details" -->
Hidden content here.
<!-- /confluence:expand -->

Text with a <!-- confluence:status text="In Progress" color="blue" --> status badge.
```

## License

MIT
