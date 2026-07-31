"""Install hints for optional external binaries (Win / Mac / Linux)."""

from __future__ import annotations

from typing import Dict

_HINTS: Dict[str, str] = {
    "rg": (
        "ripgrep (rg) not on PATH — using slower Python fallback. Install: "
        "Windows: winget install BurntSushi.ripgrep.MSVC · "
        "Mac: brew install ripgrep · "
        "Linux: apt install ripgrep / dnf install ripgrep"
    ),
    "fd": (
        "fd not on PATH — using os.scandir fallback. Install: "
        "Windows: winget install sharkdp.fd · "
        "Mac: brew install fd · "
        "Linux: apt install fd-find (binary often fdfind) / dnf install fd-find"
    ),
    "tesseract": (
        "Tesseract OCR not available — expected_elements cannot be claim-grade. Install: "
        "Windows: winget install UB-Mannheim.TesseractOCR · "
        "Mac: brew install tesseract · "
        "Linux: apt install tesseract-ocr / dnf install tesseract · "
        "then: pip install pillow pytesseract"
    ),
    "ast-grep": (
        "ast-grep (sg) not on PATH — using Python AST fallback. Install: "
        "Windows: scoop install ast-grep / npm i -g @ast-grep/cli · "
        "Mac: brew install ast-grep · "
        "Linux: cargo install ast-grep / npm i -g @ast-grep/cli"
    ),
}


def install_hint(tool: str) -> str:
    key = (tool or "").strip().lower()
    if key in ("sg", "ast_grep"):
        key = "ast-grep"
    return _HINTS.get(key, f"{tool} not found on PATH — install the binary for your OS.")
