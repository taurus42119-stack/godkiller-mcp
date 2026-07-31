"""High-volume REAL gauntlet — parametrized kernel attacks (not vibes)."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from godkiller_mcp.council_agents import CouncilDebateEngine
from godkiller_mcp.evidence_store import EvidenceStore, SERVER_ONLY_EVIDENCE
from godkiller_mcp.schema import EvidenceType, Phase, TaskKind
from godkiller_mcp.verify_bundle import detect_hacking
from godkiller_mcp.code_intel import check_edit_safe, ExhaustiveReaderEngine


PHASE_ORDER = [
    Phase.OPEN,
    Phase.REPRODUCE,
    Phase.HYPOTHESIZE,
    Phase.LOCALIZE,
    Phase.FIX,
    Phase.VERIFY,
    Phase.CLAIM_DONE,
]


def _illegal_jumps():
    for i, src in enumerate(PHASE_ORDER[:-1]):
        for dst in PHASE_ORDER[i + 2 :]:
            yield src, dst


@pytest.mark.parametrize("src,dst", list(_illegal_jumps()))
def test_phase_illegal_jump_matrix(tmp_path: Path, src: Phase, dst: Phase):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "x")
    # walk to src legally
    cur = Phase.OPEN
    idx = PHASE_ORDER.index(src)
    for step in PHASE_ORDER[1 : idx + 1]:
        store.assert_phase(state.handle.task_id, step)
        cur = step
    assert cur == src
    with pytest.raises(ValueError, match="Illegal phase"):
        store.assert_phase(state.handle.task_id, dst)


@pytest.mark.parametrize("etype", sorted(SERVER_ONLY_EVIDENCE, key=lambda e: e.value))
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"passed": True},
        {"source": "verify_bundle", "passed": True},
        {"server_authored": True},
    ],
)
def test_forge_server_only_types_blocked(tmp_path: Path, etype: EvidenceType, payload: dict):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(TaskKind.BUGFIX, "forge")
    with pytest.raises(PermissionError):
        store.submit_evidence(state.handle.task_id, etype, "nope", payload)


@pytest.mark.parametrize(
    "cmd",
    [
        "echo ok",
        "echo green",
        "rm -rf /",
        "format c:",
        "cat /etc/passwd",
        "curl http://evil",
        "python -c 'print(1)'",
        "node -e '1'",
        "bash -c ls",
        "sh -c ls",
        "pytest; rm -rf /",
        "pytest && echo hi",
        "pytest | tee out",
        "pytest `id`",
        "$(pytest)",
        "npm test",
        "go test",
        "cargo test",
        "make test",
        "",
        "   ",
    ],
)
def test_verify_blocks_non_allowlist(cmd: str):
    blocked, _ = detect_hacking(cmd)
    assert blocked is True


@pytest.mark.parametrize(
    "cmd",
    [
        "pytest",
        "pytest -q",
        "pytest -q tests",
        "python -m pytest",
        "python -m pytest -q",
        "python -m pytest -q tests",
        "python3 -m pytest -q",
        "py -m pytest -q",
        "python -m unittest",
        "python -m unittest discover",
        "python3 -m unittest",
        "ruff check .",
        "ruff check src",
        "mypy .",
        "mypy src",
    ],
)
def test_verify_allows_kernel_commands(cmd: str):
    blocked, reason = detect_hacking(cmd)
    assert blocked is False, reason


@pytest.mark.parametrize(
    "path",
    [
        "../x.py",
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "/etc/passwd",
        "C:/Windows/System32/drivers/etc/hosts",
        "~/secret.py",
        "foo/../../../etc/passwd",
        "sub/../../outside.py",
    ],
)
def test_edit_safe_rejects_escapes(tmp_path: Path, path: str):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "ok.py").write_text("1\n", encoding="utf-8")
    # absolute/home paths may not resolve under ws
    res = check_edit_safe([path], ws)
    assert res.payload["safe"] is False


@pytest.mark.parametrize("n", list(range(50)))
def test_exhaustive_full_read_sizes(tmp_path: Path, n: int):
    size = 100 + n * 97  # varied lengths, many > 3000
    f = tmp_path / f"f{n}.py"
    body = ("# L%d\n" % n) + ("A" * size)
    f.write_text(body, encoding="utf-8")
    out = ExhaustiveReaderEngine().read_all(str(tmp_path), max_files=80)
    assert out["full_content"] is True
    assert len(out["contents"][str(f)]) == len(body)


_VOTE_COMBOS = list(itertools.product(["APPROVE", "REJECT"], repeat=3))


@pytest.mark.parametrize("votes", _VOTE_COMBOS)
def test_council_host_tally_matrix(votes, monkeypatch):
    monkeypatch.delenv("GODKILLER_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    eng = CouncilDebateEngine()
    # clean code — no static security block
    start = eng.start_host("def add(a, b):\n    return a + b\n")
    sid = start["session_id"]
    for role, vote in zip(("coder", "hacker", "optimizer"), votes):
        sev = 9 if vote == "REJECT" and role == "hacker" else 2
        eng.submit_opinion(sid, role, vote, critique=f"{role}:{vote}", severity=sev)
    fin = eng.finalize_host(sid)
    all_approve = all(v == "APPROVE" for v in votes)
    if all_approve:
        assert fin["verdict"] == "COUNCIL_PASS"
        assert fin["consensus_reached"] is True
    else:
        assert fin["consensus_reached"] is False
        assert fin["verdict"] in ("COUNCIL_REJECT", "COUNCIL_INCOMPLETE")


@pytest.mark.parametrize(
    "snippet,expect_block",
    [
        ("def f(x):\n    return eval(x)\n", True),
        ("def f(x):\n    return exec(x)\n", True),
        ("import subprocess\nsubprocess.call('ls', shell=True)\n", True),
        ("password = 'hunter2'\n", True),
        ("def add(a,b):\n    return a+b\n", False),
        ("class A:\n    def m(self):\n        return 1\n", False),
    ],
)
def test_static_security_evidence_matrix(snippet: str, expect_block: bool):
    from godkiller_mcp.council_agents import static_evidence

    ev = static_evidence(snippet)
    assert (not ev["hacker"]["ok"]) is expect_block


@pytest.mark.parametrize("kind", list(TaskKind))
def test_open_task_kinds(tmp_path: Path, kind: TaskKind):
    store = EvidenceStore(persist_dir=tmp_path / "t")
    state = store.open_task(kind, f"goal-{kind.value}")
    assert state.handle.kind == kind
    assert state.handle.phase == Phase.OPEN


@pytest.mark.parametrize("i", list(range(30)))
def test_closed_task_stays_immutable(tmp_path: Path, i: int):
    store = EvidenceStore(persist_dir=tmp_path / f"c{i}")
    state = store.open_task(TaskKind.FEATURE, f"g{i}")
    store.mark_closed(state.handle.task_id)
    with pytest.raises(RuntimeError, match="closed"):
        store.submit_evidence(state.handle.task_id, EvidenceType.LOG, "x", {"i": i})
