"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import re
from typing import Any, Dict, List

class LogTraceEngine:
    """Sentry/Postman-inspired Traceback Exception & Log Parser."""

    def parse_log(self, log_output: str) -> Dict[str, Any]:
        frames: List[Dict[str, Any]] = []
        matches = re.findall(r'File "([^"]+)", line (\d+), in (\w+)\n\s*(.*)', log_output)
        for filepath, lineno, func, snippet in matches:
            frames.append({
                "file": filepath,
                "line": int(lineno),
                "function": func,
                "snippet": snippet.strip(),
            })

        exc_match = re.search(r'([A-Za-z_]\w*Error|[A-Za-z_]\w*Exception):\s*(.*)', log_output)
        exc_type = exc_match.group(1) if exc_match else "UnknownException"
        exc_msg = exc_match.group(2) if exc_match else (log_output.strip().splitlines()[-1] if log_output.strip() else "")

        return {
            "engine": "traceback_parser",
            "exception_type": exc_type,
            "message": exc_msg,
            "frame_count": len(frames),
            "stack_frames": frames,
        }
