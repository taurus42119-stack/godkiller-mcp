"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import concurrent.futures
import os as _os
from pathlib import Path
from typing import Any, Dict, List, Optional



class ExhaustiveReaderEngine:
    """Full-file directory reader with byte budget (fail-visible when exceeded)."""

    DEFAULT_MAX_TOTAL_BYTES = 400_000
    DEFAULT_MAX_FILES = 24
    DEFAULT_MAX_CHARS_PER_FILE = 4_000

    def read_all(
        self,
        dir_path: str,
        max_files: int = 24,
        max_chars_per_file: Optional[int] = None,
        max_total_bytes: Optional[int] = None,
        max_workers: Optional[int] = None,
    ) -> Dict[str, Any]:
        root = Path(dir_path)
        if not root.exists():
            return {"error": f"Directory path does not exist: {dir_path}"}

        budget = int(max_total_bytes if max_total_bytes is not None else self.DEFAULT_MAX_TOTAL_BYTES)
        # None = no per-file char cap (tests / explicit full dumps). MCP dispatch sets a default.
        workers_env = _os.environ.get("GODKILLER_EXHAUSTIVE_WORKERS", "").strip()
        workers = int(max_workers if max_workers is not None else (workers_env or 10))
        workers = max(1, min(workers, 32))

        file_list: List[Path] = []
        skipped_binary: List[str] = []
        if root.is_file():
            file_list.append(root)
        else:
            for pfile in root.rglob("*"):
                if pfile.is_file():
                    if any(
                        part.startswith(".") or part in ("venv", "__pycache__", "node_modules", "dist")
                        for part in pfile.parts
                    ):
                        continue
                    # Skip obvious binaries by suffix
                    if pfile.suffix.lower() in (
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".gif",
                        ".webp",
                        ".pdf",
                        ".zip",
                        ".exe",
                        ".dll",
                        ".so",
                        ".pyc",
                        ".whl",
                    ):
                        skipped_binary.append(str(pfile))
                        continue
                    file_list.append(pfile)

        truncated_listing = len(file_list) > max_files
        file_list = file_list[:max_files]
        contents: Dict[str, str] = {}
        truncated_files: List[str] = []
        total_bytes = 0
        budget_exceeded = False

        def _read_single(p: Path) -> Tuple[str, str, bool, int, bool]:
            try:
                # Peek binary
                head = p.read_bytes()[:8192]
                if b"\x00" in head:
                    return (str(p), "", False, 0, True)
                txt = p.read_text(encoding="utf-8", errors="ignore")
                raw_len = p.stat().st_size
                was_trunc = False
                if max_chars_per_file is not None and len(txt) > max_chars_per_file:
                    txt = txt[:max_chars_per_file]
                    was_trunc = True
                return (str(p), txt, was_trunc, raw_len, False)
            except Exception as e:
                return (str(p), f"[Error reading file: {e}]", False, 0, False)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for path_str, txt, was_trunc, raw_len, is_bin in executor.map(_read_single, file_list):
                if is_bin:
                    skipped_binary.append(path_str)
                    continue
                if total_bytes + raw_len > budget and contents:
                    budget_exceeded = True
                    break
                contents[path_str] = txt
                total_bytes += raw_len
                if was_trunc:
                    truncated_files.append(path_str)

        return {
            "engine": "exhaustive_reader_engine",
            "target": str(root),
            "total_files_read": len(contents),
            "files": list(contents.keys()),
            "contents": contents,
            "full_content": max_chars_per_file is None and not budget_exceeded,
            "max_chars_per_file": max_chars_per_file,
            "max_total_bytes": budget,
            "max_workers": workers,
            "truncated_files": truncated_files,
            "truncated_file_listing": truncated_listing,
            "total_bytes_on_disk": total_bytes,
            "budget_exceeded": budget_exceeded,
            "skipped_binary": skipped_binary[:50],
            "truncated": budget_exceeded or truncated_listing or bool(truncated_files),
        }
