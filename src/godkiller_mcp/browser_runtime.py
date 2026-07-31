"""Real browser automation via Playwright (optional dependency)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BrowserSessionState:
    url: str = ""
    last_snapshot: str = ""
    screenshots: List[str] = field(default_factory=list)


class PlaywrightBrowser:
    """Minimal Playwright wrapper. Falls back with clear error if not installed."""

    def __init__(self, artifact_dir: Optional[str | Path] = None):
        self.artifact_dir = Path(artifact_dir) if artifact_dir else Path("arena/results/ui_artifacts")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self._pw = None
        self._browser = None
        self._page = None
        self.state = BrowserSessionState()

    def _ensure(self) -> Dict[str, Any] | None:
        if self._page is not None:
            return None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "ok": False,
                "engine": "none",
                "error": "Playwright not installed. pip install 'godkiller-mcp[browser]' && playwright install chromium",
            }
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        return None

    def navigate(self, url: str) -> Dict[str, Any]:
        from godkiller_mcp.ssrf import assert_public_url, guard_url_or_error

        blocked = guard_url_or_error(url)
        if blocked:
            return blocked
        err = self._ensure()
        if err:
            return err
        assert self._page is not None
        self._page.goto(url, wait_until="domcontentloaded")
        final = self._page.url
        ok, reason = assert_public_url(final, resolve=True)
        if not ok:
            try:
                self._page.goto("about:blank")
            except Exception:
                pass
            self.state.url = ""
            return {"ok": False, "error": reason, "ssrf_blocked": True, "final_url": final}
        self.state.url = final
        return {
            "ok": True,
            "engine": "playwright",
            "url": final,
            "requested": url,
            "title": self._page.title(),
        }

    def snapshot(self) -> Dict[str, Any]:
        err = self._ensure()
        if err:
            return err
        assert self._page is not None
        text = self._page.inner_text("body")[:8000]
        self.state.last_snapshot = text
        return {"ok": True, "engine": "playwright", "url": self.state.url, "text": text}

    def screenshot(self, name: str = "shot.png") -> Dict[str, Any]:
        err = self._ensure()
        if err:
            return err
        assert self._page is not None
        path = self.artifact_dir / name
        self._page.screenshot(path=str(path), full_page=True)
        self.state.screenshots.append(str(path.resolve()))
        return {"ok": True, "engine": "playwright", "path": str(path.resolve())}

    def _guard_current_url(self) -> Optional[Dict[str, Any]]:
        from godkiller_mcp.ssrf import assert_public_url

        assert self._page is not None
        final = self._page.url or ""
        if not final or final.startswith("about:"):
            self.state.url = final
            return None
        ok, reason = assert_public_url(final, resolve=True)
        if not ok:
            try:
                self._page.goto("about:blank")
            except Exception:
                pass
            self.state.url = ""
            return {"ok": False, "error": reason, "ssrf_blocked": True, "final_url": final}
        self.state.url = final
        return None

    def click(self, selector: str) -> Dict[str, Any]:
        err = self._ensure()
        if err:
            return err
        assert self._page is not None
        self._page.click(selector)
        blocked = self._guard_current_url()
        if blocked:
            return blocked
        return {"ok": True, "engine": "playwright", "clicked": selector, "url": self.state.url}

    def fill(self, selector: str, value: str) -> Dict[str, Any]:
        err = self._ensure()
        if err:
            return err
        assert self._page is not None
        self._page.fill(selector, value)
        blocked = self._guard_current_url()
        if blocked:
            return blocked
        return {
            "ok": True,
            "engine": "playwright",
            "filled": selector,
            "value_len": len(value),
            "url": self.state.url,
        }

    def close(self) -> None:
        try:
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        finally:
            self._page = None
            self._browser = None
            self._pw = None
