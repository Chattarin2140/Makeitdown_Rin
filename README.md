# Makeitdown_Rin

Install the local package with:

```bash
pip install -e packages/markitdown[all]
```

Convert an Excel file to Markdown with:

```bash
markitdown "5. May'26.xlsx" > document.md
```

If `markitdown` is not on your `PATH`, use:

```bash
python -m markitdown.cli "5. May'26.xlsx" > document.md
```

You can also send the output to a file directly:

```bash
markitdown "5. May'26.xlsx" -o document.md
```