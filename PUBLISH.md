# Publishing godkiller-mcp to PyPI

Build is already CI-ready. Local build:

```bash
pip install build
python -m build
```

Publish (needs a PyPI API token):

```bash
# PowerShell
$env:UV_PUBLISH_TOKEN = "pypi-..."
uv publish
# or
twine upload dist/*
```

GitHub Actions: add repository secret `PYPI_API_TOKEN`, then use `.github/workflows/publish.yml` on release tags.
