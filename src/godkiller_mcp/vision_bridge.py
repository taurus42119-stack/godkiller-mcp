"""PIL image inspection + optional OCR for expected_elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from godkiller_mcp.tool_hints import install_hint


try:
    from PIL import Image, ImageStat

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _ocr_text(path: Path) -> tuple[str, str]:
    """Return (text, engine_name). Fail-closed: never invent OCR text."""
    try:
        import shutil

        import pytesseract  # type: ignore

        t_cmd = shutil.which("tesseract")
        if not t_cmd:
            return "", "none"
        pytesseract.pytesseract.tesseract_cmd = t_cmd
        with Image.open(path) as img:
            text = pytesseract.image_to_string(img) or ""
        if text.strip():
            return text, "pytesseract"
        return "", "pytesseract_failed"
    except Exception:
        return "", "pytesseract_failed"


def _element_in_hay(el: str, hay: str) -> bool:
    """Substring for long labels; word-boundary / exact token for short labels."""
    import re

    needle = (el or "").strip().lower()
    if not needle:
        return False
    hay_l = (hay or "").lower()
    if len(needle) < 4:
        return bool(re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay_l))
    if re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", hay_l):
        return True
    return needle in hay_l


@dataclass
class VisionAnalysisResult:
    image_uri: str
    passed: bool
    score: float
    width: int
    height: int
    format: str
    color_mode: str
    is_blank_placeholder: bool
    description: str
    expected_elements: List[str] = field(default_factory=list)
    elements_found: List[str] = field(default_factory=list)
    elements_missing: List[str] = field(default_factory=list)
    ocr_engine: str = "none"
    ocr_text_len: int = 0


class VisionBridge:
    """Image QA: blank/size checks + expected_elements via OCR when available."""

    def analyze_screenshot(
        self, image_uri: str | Path, expected_elements: Optional[List[str]] = None
    ) -> VisionAnalysisResult:
        path = Path(image_uri)
        expected = [str(x).strip() for x in (expected_elements or []) if str(x).strip()]

        if not path.exists():
            return VisionAnalysisResult(
                image_uri=str(image_uri),
                passed=False,
                score=0.0,
                width=0,
                height=0,
                format="UNKNOWN",
                color_mode="UNKNOWN",
                is_blank_placeholder=True,
                description="Image file missing on disk",
                expected_elements=expected,
                elements_missing=expected,
            )

        if not HAS_PIL:
            file_size = path.stat().st_size
            is_valid = file_size > 500
            # Size-only is never claim-grade (with or without expected_elements)
            return VisionAnalysisResult(
                image_uri=str(image_uri),
                passed=False,
                score=0.1 if not is_valid else 0.2,
                width=0,
                height=0,
                format=path.suffix.lstrip(".").upper() or "UNKNOWN",
                color_mode="UNKNOWN",
                is_blank_placeholder=not is_valid,
                description=(
                    "OCR_UNAVAILABLE size_only_not_claim_grade — "
                    + install_hint("tesseract")
                    if expected
                    else (
                        "size_only_not_claim_grade — pip install pillow "
                        f"(saw {file_size} bytes; not claim-grade without PIL)"
                    )
                ),
                expected_elements=expected,
                elements_missing=expected,
                ocr_engine="unavailable",
            )

        try:
            with Image.open(path) as img:
                width, height = img.size
                img_format = img.format or path.suffix.lstrip(".").upper()
                color_mode = img.mode
                stat = ImageStat.Stat(img.convert("L"))
                variance = stat.var[0] if stat.var else 0.0
                is_blank = variance < 5.0
                has_valid_dim = width >= 100 and height >= 100
                base_pass = (not is_blank) and has_valid_dim

            found: List[str] = []
            missing: List[str] = []
            ocr_engine = "none"
            ocr_len = 0
            ocr_text = ""

            if expected:
                ocr_text, ocr_engine = _ocr_text(path)
                ocr_len = len(ocr_text)
                # Sidecar may enrich OCR text but cannot alone be claim-grade
                sidecar = path.with_suffix(path.suffix + ".txt")
                if not sidecar.exists():
                    sidecar = path.with_suffix(".txt")
                sidecar_text = ""
                if sidecar.exists():
                    try:
                        sidecar_text = sidecar.read_text(encoding="utf-8", errors="ignore").strip()
                    except Exception:
                        sidecar_text = ""
                if ocr_engine in ("none", "pytesseract_failed") and not ocr_text:
                    if sidecar_text:
                        return VisionAnalysisResult(
                            image_uri=str(image_uri),
                            passed=False,
                            score=0.2 if base_pass else 0.1,
                            width=width,
                            height=height,
                            format=img_format,
                            color_mode=color_mode,
                            is_blank_placeholder=is_blank,
                            description=(
                                "sidecar_without_ocr_not_claim_grade — "
                                + install_hint("tesseract")
                            ),
                            expected_elements=expected,
                            elements_missing=list(expected),
                            ocr_engine="sidecar_only",
                            ocr_text_len=len(sidecar_text),
                        )
                    return VisionAnalysisResult(
                        image_uri=str(image_uri),
                        passed=False,
                        score=0.2 if base_pass else 0.1,
                        width=width,
                        height=height,
                        format=img_format,
                        color_mode=color_mode,
                        is_blank_placeholder=is_blank,
                        description=(
                            "OCR_UNAVAILABLE — expected_elements cannot be claim-grade — "
                            + install_hint("tesseract")
                        ),
                        expected_elements=expected,
                        elements_missing=list(expected),
                        ocr_engine=ocr_engine,
                        ocr_text_len=0,
                    )

                if sidecar_text:
                    ocr_text = (ocr_text + "\n" + sidecar_text).strip()
                    ocr_engine = f"{ocr_engine}+sidecar"
                    ocr_len = len(ocr_text)

                hay = ocr_text.lower()
                for el in expected:
                    if _element_in_hay(el, hay):
                        found.append(el)
                    else:
                        missing.append(el)

                passed = base_pass and not missing
                score = 0.95 if passed else (0.45 if base_pass else 0.1)
                desc = (
                    f"UI image OK; elements {len(found)}/{len(expected)} via {ocr_engine}"
                    if passed
                    else f"Missing elements {missing} (ocr={ocr_engine})"
                )
            else:
                passed = base_pass
                score = 0.95 if passed else (0.4 if has_valid_dim else 0.1)
                desc = (
                    f"Valid UI image ({width}x{height}, {img_format}, variance={variance:.1f})"
                    if passed
                    else "Rejected: Blank or tiny placeholder image detected"
                )

            return VisionAnalysisResult(
                image_uri=str(image_uri),
                passed=passed,
                score=score,
                width=width,
                height=height,
                format=img_format,
                color_mode=color_mode,
                is_blank_placeholder=is_blank,
                description=desc,
                expected_elements=expected,
                elements_found=found,
                elements_missing=missing,
                ocr_engine=ocr_engine,
                ocr_text_len=ocr_len,
            )
        except Exception as e:
            return VisionAnalysisResult(
                image_uri=str(image_uri),
                passed=False,
                score=0.0,
                width=0,
                height=0,
                format="CORRUPTED",
                color_mode="UNKNOWN",
                is_blank_placeholder=True,
                description=f"Corrupted image error: {str(e)}",
                expected_elements=expected,
                elements_missing=expected,
            )
