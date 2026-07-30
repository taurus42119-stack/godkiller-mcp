from __future__ import annotations

from godkiller_mcp.code_intel import _find_dev_binary, _default_tools_dir
from godkiller_mcp.safe_exec import split_command
from godkiller_mcp.verify_bundle import VerifyBundleRunner


def test_no_hardcoded_asus_paths():
    assert _default_tools_dir() is None or "ASUS" not in str(_default_tools_dir())
    # default constructor must not embed a user Desktop path
    import inspect
    from godkiller_mcp import code_intel

    src = inspect.getsource(code_intel)
    assert "C:\\Users\\ASUS" not in src
    assert r"C:\Users\ASUS" not in src


def test_split_command_basic():
    assert split_command("python -m pytest -q")[:3] == ["python", "-m", "pytest"]


def test_verify_runner_blocks_todo_echo(tmp_path):
    runner = VerifyBundleRunner(timeout_sec=5)
    result = runner.run(tmp_path, ["echo TODO"])
    assert result.passed is False
    assert result.hack_blocked is True
