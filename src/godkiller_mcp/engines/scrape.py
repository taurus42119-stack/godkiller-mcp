"""Engine extracted from code_intel god-module."""
from __future__ import annotations

import re
from typing import Any, Dict

class DeepScrapeEngine:
    """Web scraper that converts HTML to clean markdown for LLM context."""

    def scrape(self, url_or_html: str, max_length: int = 5000) -> Dict[str, Any]:
        if url_or_html.startswith("http://") or url_or_html.startswith("https://"):
            from godkiller_mcp.ssrf import assert_public_url

            ok, reason = assert_public_url(url_or_html)
            if not ok:
                return {"error": reason, "ssrf_blocked": True}
            try:
                from godkiller_mcp.ssrf import SafeHTTPError, safe_urlopen

                with safe_urlopen(
                    url_or_html,
                    timeout=10,
                    headers={"User-Agent": "GODKILLER-Agent/2.0"},
                ) as resp:
                    html_content = resp.read().decode("utf-8", errors="ignore")
            except SafeHTTPError as e:
                return {"error": e.reason, "ssrf_blocked": True}
            except Exception as e:
                return {"error": f"Failed to fetch URL: {e}"}
        else:
            html_content = url_or_html

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, "html.parser")
            for elem in soup(["script", "style", "nav", "footer", "header", "aside", "svg"]):
                elem.decompose()
            text = soup.get_text(separator="\n")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_md = "\n".join(lines)
            if len(clean_md) > max_length:
                clean_md = clean_md[:max_length] + "\n... [Content Truncated for Token Limit]"
            return {"engine": "bs4_cleaner", "markdown": clean_md, "length": len(clean_md)}
        except Exception:
            pass

        clean_text = re.sub(r"<(script|style).*?>.*?</\1>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", " ", clean_text)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
        clean_md = "\n".join(lines)
        if len(clean_md) > max_length:
            clean_md = clean_md[:max_length] + "\n... [Content Truncated for Token Limit]"
        return {"engine": "python_regex_stripper_fallback", "markdown": clean_md, "length": len(clean_md)}
