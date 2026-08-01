"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class Tag:
    name: str
    kind: str  # "class", "def", "import"
    file: str
    line: int


class RepoMapGenerator:
    """Aider-inspired Repo Map generator using AST parsing & symbol tagging."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def generate_tags(self) -> List[Tag]:
        tags: List[Tag] = []
        if not self.root.exists():
            return tags
        for py_file in self.root.rglob("*.py"):
            if any(part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist") for part in py_file.parts):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(content, filename=str(py_file))
                rel_path = str(py_file.relative_to(self.root))
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        tags.append(Tag(name=node.name, kind="class", file=rel_path, line=node.lineno))
                    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        tags.append(Tag(name=node.name, kind="def", file=rel_path, line=node.lineno))
            except Exception:
                pass
        return tags

    def get_repo_map(self, max_tokens: int = 1000) -> str:
        tags = self.generate_tags()
        files_map: Dict[str, List[Tag]] = {}
        for t in tags:
            files_map.setdefault(t.file, []).append(t)

        lines: List[str] = [f"=== GODKILLER REPO MAP ({len(tags)} symbols across {len(files_map)} files) ==="]
        for fpath, file_tags in files_map.items():
            lines.append(f"\n📄 {fpath}:")
            for t in file_tags:
                prefix = "  class" if t.kind == "class" else "  def"
                lines.append(f"{prefix} {t.name} (L{t.line})")

        full_text = "\n".join(lines)
        if len(full_text) > max_tokens * 4:
            full_text = full_text[: max_tokens * 4] + "\n... [Repo Map Truncated for Token Limit]"
        return full_text
