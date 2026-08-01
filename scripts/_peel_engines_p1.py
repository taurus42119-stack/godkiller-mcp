"""One-shot peel: split code_intel engines into godkiller_mcp.engines.*"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "godkiller_mcp"
src_path = ROOT / "code_intel.py"
src = src_path.read_text(encoding="utf-8").splitlines(keepends=True)


def slice_lines(a: int, b: int) -> str:
    return "".join(src[a - 1 : b])


engines = ROOT / "engines"
engines.mkdir(exist_ok=True)

COMMON = '"""Engine extracted from code_intel god-module."""\nfrom __future__ import annotations\n\n'

mods = [
    (
        "repo_map.py",
        283,
        332,
        "import ast\nfrom dataclasses import dataclass\nfrom pathlib import Path\nfrom typing import Dict, List\n",
    ),
    (
        "search.py",
        335,
        514,
        "import json\nimport os\nimport re\nimport shutil\nimport subprocess\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n",
    ),
    (
        "ast_grep.py",
        516,
        584,
        "import ast\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n",
    ),
    (
        "security.py",
        586,
        798,
        "import ast\nimport re\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n",
    ),
    ("scrape.py", 800, 846, "import re\nfrom typing import Any, Dict\n"),
    ("log_trace.py", 849, 873, "import re\nfrom typing import Any, Dict, List\n"),
    (
        "autofix.py",
        876,
        945,
        "from pathlib import Path\nfrom typing import Any, Dict, Optional\n",
    ),
    (
        "pipeline.py",
        948,
        1051,
        "import graphlib\nimport json\nfrom typing import Any, Dict, List\n",
    ),
    (
        "self_heal.py",
        1054,
        1217,
        "from pathlib import Path\nfrom typing import Any, Dict, List, Optional\n\n"
        "from godkiller_mcp.engines.log_trace import LogTraceEngine\n",
    ),
    (
        "readiness.py",
        1220,
        1370,
        "import ast\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n",
    ),
    (
        "exhaustive.py",
        1373,
        1485,
        "import concurrent.futures\nimport os as _os\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional\n",
    ),
    (
        "skillify.py",
        1488,
        1533,
        "from pathlib import Path\nfrom typing import Any, Dict\n",
    ),
]

for name, a, b, imports in mods:
    body = slice_lines(a, b)
    cleaned = []
    for line in body.splitlines(keepends=True):
        if (
            line.startswith("import graphlib")
            or line.startswith("import concurrent")
            or line.startswith("import os as _os")
        ):
            continue
        cleaned.append(line)
    text = COMMON + imports + "\n" + "".join(cleaned)
    if name == "skillify.py":
        text = text.replace(
            "gate = check_edit_safe([str(skill_file)], root)",
            "from godkiller_mcp.code_intel import check_edit_safe\n"
            "        gate = check_edit_safe([str(skill_file)], root)",
        )
    if not text.endswith("\n"):
        text += "\n"
    (engines / name).write_text(text, encoding="utf-8")
    print("wrote", name, a, "-", b)

(engines / "__init__.py").write_text(
    '''"""GODKILLER engines — peeled from code_intel god-module."""
from __future__ import annotations

from godkiller_mcp.council_agents import CouncilDebateEngine
from godkiller_mcp.engines.ast_grep import AstGrepEngine
from godkiller_mcp.engines.autofix import AutoFixEngine
from godkiller_mcp.engines.exhaustive import ExhaustiveReaderEngine
from godkiller_mcp.engines.log_trace import LogTraceEngine
from godkiller_mcp.engines.pipeline import PipelineRunner
from godkiller_mcp.engines.readiness import EpistemicConfidenceGate
from godkiller_mcp.engines.repo_map import RepoMapGenerator, Tag
from godkiller_mcp.engines.scrape import DeepScrapeEngine
from godkiller_mcp.engines.search import (
    ContextPreviewEngine,
    FastFindEngine,
    HyperSearchEngine,
    _default_tools_dir,
    _find_dev_binary,
)
from godkiller_mcp.engines.security import SecurityScanEngine
from godkiller_mcp.engines.self_heal import SelfHealingEngine
from godkiller_mcp.engines.skillify import AutoSkillifyEngine

__all__ = [
    "Tag",
    "RepoMapGenerator",
    "HyperSearchEngine",
    "FastFindEngine",
    "ContextPreviewEngine",
    "AstGrepEngine",
    "SecurityScanEngine",
    "DeepScrapeEngine",
    "LogTraceEngine",
    "AutoFixEngine",
    "PipelineRunner",
    "SelfHealingEngine",
    "EpistemicConfidenceGate",
    "ExhaustiveReaderEngine",
    "AutoSkillifyEngine",
    "CouncilDebateEngine",
    "_find_dev_binary",
    "_default_tools_dir",
]
''',
    encoding="utf-8",
)

# Keep core through line 274 (before mid-file imports), drop Tag+engines
core_lines = src[:274]
core = "".join(core_lines)
# Remove CouncilDebateEngine import from top if present — re-exported via engines
# Keep it for __all__ compatibility via reexport

reexport = """
# Engines live in godkiller_mcp.engines.* — re-export for stable import paths.
from godkiller_mcp.engines import (  # noqa: E402
    AstGrepEngine,
    AutoFixEngine,
    AutoSkillifyEngine,
    ContextPreviewEngine,
    CouncilDebateEngine,
    DeepScrapeEngine,
    EpistemicConfidenceGate,
    ExhaustiveReaderEngine,
    FastFindEngine,
    HyperSearchEngine,
    LogTraceEngine,
    PipelineRunner,
    RepoMapGenerator,
    SecurityScanEngine,
    SelfHealingEngine,
    Tag,
    _default_tools_dir,
    _find_dev_binary,
)
"""

out = core.rstrip() + "\n" + reexport
if not out.endswith("\n"):
    out += "\n"
src_path.write_text(out, encoding="utf-8")
print("code_intel lines now", len(out.splitlines()))
