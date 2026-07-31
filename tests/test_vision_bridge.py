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


def test_expected_elements_sidecar_alone_not_claim_grade(tmp_path: Path):
    try:
        from PIL import Image
    except ImportError:
        return

    path = tmp_path / "ui.png"
    img = Image.new("RGB", (200, 200))
    pixels = img.load()
    for y in range(200):
        for x in range(200):
            pixels[x, y] = ((x * 3) % 256, (y * 5) % 256, (x + y) % 256)
    img.save(path)
    r = VisionBridge().analyze_screenshot(path, expected_elements=["Save"])
    assert r.passed is False
    (path.with_suffix(".txt")).write_text("Save button visible", encoding="utf-8")
    r2 = VisionBridge().analyze_screenshot(path, expected_elements=["Save"])
    assert r2.passed is False, r2.description
    assert "sidecar_without_ocr" in (r2.description or "")


def test_element_match_word_boundary():
    from godkiller_mcp.vision_bridge import _element_in_hay

    assert _element_in_hay("Save", "click Save now") is True
    assert _element_in_hay("ok", "token ok here") is True
    assert _element_in_hay("ok", "tokenbook") is False
