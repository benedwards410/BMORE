"""Beacon sends a QuickBooks "View and pay" link, no PDF. Best effort: open the
link in headless Chromium (Playwright), click a Download/Print control if the
page offers one, otherwise render the invoice page itself to PDF (it keeps a
text layer, which is all the pipeline needs). Anything else → _needs_manual/."""
from __future__ import annotations

import logging
import re
from pathlib import Path

from ..config import Config
from ..state import iso, utcnow

log = logging.getLogger("kce_intake.quickbooks")

DOWNLOAD_SELECTORS = [
    'a:has-text("Download")',
    'button:has-text("Download")',
    'a:has-text("Save as PDF")',
    'button:has-text("Save as PDF")',
    '[aria-label*="download" i]',
    'a[href$=".pdf"]',
    'a[href*="/pdf"]',
]


def playwright_available() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def fetch_invoice_pdf(link: str, timeout_ms: int = 60000) -> tuple[bytes | None, str]:
    """Return (pdf_bytes, how) — how is 'download', 'rendered' or an error text."""
    if not playwright_available():
        return None, "playwright not installed"
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(accept_downloads=True)
                page.goto(link, wait_until="networkidle", timeout=timeout_ms)
                for selector in DOWNLOAD_SELECTORS:
                    locator = page.locator(selector).first
                    try:
                        if locator.count() == 0:
                            continue
                        with page.expect_download(timeout=20000) as download:
                            locator.click()
                        path = download.value.path()
                        data = Path(path).read_bytes()
                        if data[:5] == b"%PDF-":
                            return data, "download"
                    except Exception:  # noqa: BLE001 - try the next control
                        continue
                page.emulate_media(media="print")
                data = page.pdf(format="Letter", print_background=True)
                if data[:5] == b"%PDF-":
                    return data, "rendered"
                return None, "page rendered but produced no PDF"
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def record_needs_manual(cfg: Config, subject: str, sender: str, link: str, reason: str,
                        invoice_number: str = "unknown") -> Path:
    cfg.needs_manual_dir.mkdir(parents=True, exist_ok=True)
    stamp = utcnow().strftime("%Y-%m-%d")
    slug = re.sub(r"[^a-z0-9]+", "-", invoice_number.lower()).strip("-") or "unknown"
    path = cfg.needs_manual_dir / f"{stamp}-beacon-invoice-{slug}.md"
    if path.exists():
        return path
    path.write_text(
        "# Supplier invoice needs a manual download\n\n"
        f"- **Subject:** {subject}\n- **From:** {sender}\n- **Invoice:** {invoice_number}\n"
        f"- **Link:** {link}\n- **Why:** {reason}\n- **Noted:** {iso(utcnow())}\n\n"
        "Open the link, save the PDF into the project folder (or the drop folder), then delete this note.\n",
        encoding="utf-8",
    )
    return path
