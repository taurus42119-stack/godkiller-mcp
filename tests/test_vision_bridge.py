from __future__ import annotations

from pathlib import Path

from godkiller_mcp.vision_bridge import VisionBridge


def test_missing_image_fails():
    result = VisionBridge().analyze_screenshot("definitely-missing-file.png")
    assert result.passed is False
    assert result.is_blank_placeholder is True


def test_solid_color_rejected(tmp_path: Path):
    try:
        from PIL import Image
    except ImportError:
        return

    path = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), color=(128, 128, 128)).save(path)
    result = VisionBridge().analyze_screenshot(path)
    assert result.passed is False
    assert result.is_blank_placeholder is True
