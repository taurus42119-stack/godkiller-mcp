"""PIL image inspection + optional OCR for expected_elements."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


try:
    from PIL import Image, ImageStat

    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def _ocr_text(path: Path) -> tuple[str, str]:
    """Return (text, engine_name)."""
    try:
        import pytesseract  # type: ignore
    except ImportError:
        return "", "none"
    try:
        with Image.open(path) as img:
            text = pytesseract.image_to_string(img) or ""
        return text, "pytesseract"
    except Exception:
        return "", "pytesseract_failed"


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
            # Fail closed if caller asked for element checks without Pillow/OCR
            if expected:
                return VisionAnalysisResult(
                    image_uri=str(image_uri),
                    passed=False,
                    score=0.1,
                    width=0,
                    height=0,
                    format=path.suffix.lstrip(".").upper() or "UNKNOWN",
                    color_mode="UNKNOWN",
                    is_blank_placeholder=not is_valid,
                    description="expected_elements require Pillow+OCR; cannot verify",
                    expected_elements=expected,
                    elements_missing=expected,
                    ocr_engine="unavailable",
                )
            return VisionAnalysisResult(
                image_uri=str(image_uri),
                passed=is_valid,
                score=0.5 if is_valid else 0.1,
                width=0,
                height=0,
                format=path.suffix.lstrip(".").upper() or "UNKNOWN",
                color_mode="UNKNOWN",
                is_blank_placeholder=not is_valid,
                description=(
                    f"Pillow not installed; size-only check ({file_size} bytes)"
                    if is_valid
                    else "Tiny image placeholder detected (Pillow unavailable)"
                ),
                expected_elements=expected,
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
                # Also accept a sidecar .txt next to the image (agent-exported a11y dump)
                sidecar = path.with_suffix(path.suffix + ".txt")
                if not sidecar.exists():
                    sidecar = path.with_suffix(".txt")
                if sidecar.exists():
                    try:
                        ocr_text = (ocr_text + "\n" + sidecar.read_text(encoding="utf-8", errors="ignore")).strip()
                        ocr_engine = f"{ocr_engine}+sidecar" if ocr_engine != "none" else "sidecar_txt"
                        ocr_len = len(ocr_text)
                    except Exception:
                        pass

                hay = ocr_text.lower()
                if ocr_engine in ("none", "pytesseract_failed") and not hay:
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
                            "expected_elements provided but OCR unavailable "
                            "(pip install pytesseract + Tesseract binary, or write sidecar .txt)"
                        ),
                        expected_elements=expected,
                        elements_missing=list(expected),
                        ocr_engine=ocr_engine,
                        ocr_text_len=0,
                    )

                for el in expected:
                    if el.lower() in hay:
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
