#!/usr/bin/env python3
"""
Enhanced Cold-store idle Chrome/Edge tabs script - WORKING VERSION
"""

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import platform
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# ─── Configuration ──────────────────────────────────────────────────────────
class Config:
    def __init__(self):
        self.days_idle = 0
        self.debug_port = 9222
        self.pdf_root = self.get_default_pdf_root()
        self.profile_dir = self.get_default_profile_dir()
        self.max_filename_length = 80
        self.pdf_timeout = 30000
        self.connection_timeout = 10
        self.max_retries = 3
        self.dry_run = False
        self.verbose = False
        
    def get_default_pdf_root(self) -> Path:
        if platform.system() == "Windows":
            return Path.home() / "Documents" / "TabColdStore"
        else:
            return Path.home() / "TabColdStore"
    
    def get_default_profile_dir(self) -> Path:
        system = platform.system()
        if system == "Windows":
            return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default"
        else:
            return Path.home() / ".config" / "google-chrome" / "Default"

CHROME_EPOCH = dt.datetime(1601, 1, 1)
TABLE_HEADERS = ("Date", "Title", "URL", "Domain", "Size", "PDF")

def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

def chrome_ts(microseconds: int) -> dt.datetime:
    return CHROME_EPOCH + dt.timedelta(microseconds=microseconds)

def safe_filename(text: str, max_length: int = 80) -> str:
    """Create a Windows-safe filename from text."""
    # Remove or replace ALL problematic characters for Windows
    safe = re.sub(r'[<>:"/\\|?*]', '_', text)
    safe = re.sub(r'[^\w\s.-]', '', safe)
    safe = re.sub(r'\s+', ' ', safe).strip()
    
    if len(safe) > max_length:
        safe = safe[:max_length].rsplit(' ', 1)[0]
    
    return safe or "untitled"

def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return "unknown"

def format_file_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

class TabArchiver:
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.verbose)
        self.html_index = config.pdf_root / "index.html"
        self.history_path = config.profile_dir / "History"
        
    def ensure_directories(self) -> None:
        self.config.pdf_root.mkdir(parents=True, exist_ok=True)
        
    def ensure_html_header(self) -> None:
        if self.html_index.exists():
            return
            
        self.ensure_directories()
        
        html_content = """<!doctype html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Tab Archive</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; }
        h1 { color: #333; }
        .stats { background: #f5f5f5; padding: 10px; border-radius: 5px; margin: 10px 0; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background: #f8f9fa; font-weight: 600; }
        tr:nth-child(even) { background: #f9f9f9; }
        a { color: #0066cc; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .url { color: #666; font-size: 0.9em; }
        .domain { background: #e3f2fd; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }
        .size { text-align: right; font-family: monospace; }
        .search-box { margin: 10px 0; padding: 8px; width: 300px; border: 1px solid #ddd; border-radius: 4px; }
    </style>
    <script>
        function searchTable() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const table = document.querySelector('table');
            const rows = table.getElementsByTagName('tr');
            
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            }
        }
    </script>
</head>
<body>
    <h1>📑 Archived Tabs</h1>
    <div class="stats" id="stats">Loading statistics...</div>
    <input type="text" id="searchInput" class="search-box" placeholder="Search archived tabs..." onkeyup="searchTable()">
    <table>
"""
        
        self.html_index.write_text(html_content, encoding="utf-8")
        
        hdr = "".join(f"<th>{h}</th>" for h in TABLE_HEADERS)
        with self.html_index.open("a", encoding="utf-8") as fp:
            fp.write(f"<tr>{hdr}</tr>\n")
    
    def store_locally(self, url: str, title: str, pdf_path: Path, logged_at: dt.datetime) -> None:
        self.ensure_html_header()
        
        file_size = pdf_path.stat().st_size if pdf_path.exists() else 0
        size_str = format_file_size(file_size)
        domain = get_domain(url)
        
        row = (
            f"<tr>"
            f"<td>{logged_at:%Y-%m-%d %H:%M}</td>"
            f"<td><strong>{title}</strong></td>"
            f"<td><a href='{url}' target='_blank' class='url'>{url[:100]}{'...' if len(url) > 100 else ''}</a></td>"
            f"<td><span class='domain'>{domain}</span></td>"
            f"<td class='size'>{size_str}</td>"
            f"<td><a href='{pdf_path.as_posix()}' target='_blank'>📄 {pdf_path.name}</a></td>"
            f"</tr>\n"
        )
        
        with self.html_index.open("a", encoding="utf-8") as fp:
            fp.write(row)
    
    async def get_open_tabs(self) -> List[Dict]:
        try:
            response = requests.get(
                f"http://localhost:{self.config.debug_port}/json",
                timeout=self.config.connection_timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Failed to connect to Chrome DevTools: {e}")
            return []
    
    def get_tab_history(self, url: str, tmp_history: Path) -> Optional[dt.datetime]:
        try:
            db = sqlite3.connect(tmp_history)
            cur = db.cursor()
            cur.execute("SELECT last_visit_time FROM urls WHERE url=? LIMIT 1", (url,))
            row = cur.fetchone()
            db.close()
            
            if row:
                return chrome_ts(row[0])
            return None
        except sqlite3.Error as e:
            self.logger.warning(f"Database error for {url}: {e}")
            return None
    
    async def snap_and_close_tab(self, tab: Dict, pdf_path: Path) -> bool:
        """Take PDF snapshot using a new browser instance."""
        tab_id = tab.get("id")
        tab_url = tab.get("url", "")
        
        if not tab_url:
            self.logger.warning(f"No URL for tab: {tab.get('title', 'Unknown')}")
            return False
        
        for attempt in range(self.config.max_retries):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    try:
                        self.logger.debug(f"Navigating to: {tab_url}")
                        
                        # Use relaxed loading for better success rate
                        try:
                            await page.goto(tab_url, wait_until='domcontentloaded', timeout=15000)
                            await page.wait_for_timeout(3000)
                        except Exception:
                            # Fallback to even more basic loading
                            await page.goto(tab_url, wait_until='load', timeout=10000)
                            await page.wait_for_timeout(2000)
                        
                        self.logger.debug(f"Generating PDF: {pdf_path}")
                        await page.pdf(
                            path=str(pdf_path),
                            print_background=True,
                            format='A4'
                        )
                        
                        await browser.close()
                        
                        # Close original tab if not dry run
                        if not self.config.dry_run and tab_id:
                            try:
                                close_url = f"http://localhost:{self.config.debug_port}/json/close/{tab_id}"
                                requests.post(close_url, timeout=self.config.connection_timeout)
                            except Exception as e:
                                self.logger.warning(f"Failed to close original tab: {e}")
                        
                        return True
                        
                    except Exception as e:
                        await browser.close()
                        raise e
                        
            except Exception as e:
                self.logger.warning(f"Attempt {attempt + 1} failed for {tab.get('title', 'Unknown')}: {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(1)
                else:
                    self.logger.error(f"Failed to archive after {self.config.max_retries} attempts")
        
        return False
    
    async def process_tabs(self) -> Tuple[int, int]:
        if not self.history_path.exists():
            self.logger.error(f"History database not found: {self.history_path}")
            return 0, 0
        
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        cutoff = now - dt.timedelta(days=self.config.days_idle)
        day_dir = self.config.pdf_root / now.strftime("%Y-%m-%d")
        
        if not self.config.dry_run:
            day_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Looking for tabs idle since {cutoff:%Y-%m-%d %H:%M}")
        
        tabs = await self.get_open_tabs()
        if not tabs:
            return 0, 0
        
        page_tabs = [tab for tab in tabs if tab.get("type") == "page"]
        self.logger.info(f"Found {len(page_tabs)} open tabs")
        
        tmp_history = Path(tempfile.gettempdir()) / f"history_tmp_{int(time.time())}"
        try:
            shutil.copy2(self.history_path, tmp_history)
        except Exception as e:
            self.logger.error(f"Failed to copy history database: {e}")
            return 0, len(page_tabs)
        
        processed = 0
        
        try:
            for tab in page_tabs:
                url = tab.get("url", "")
                title = tab.get("title", "untitled")
                
                if not url or url.startswith(("chrome://", "chrome-extension://", "edge://", "about:")):
                    continue
                
                last_visit = self.get_tab_history(url, tmp_history)
                if not last_visit:
                    self.logger.debug(f"No history found for: {title}")
                    continue
                
                if last_visit > cutoff:
                    self.logger.debug(f"Tab not idle long enough: {title}")
                    continue
                #cool
                
                # FIXED: Use the working safe_filename function
                safe_title = safe_filename(title, self.config.max_filename_length)
                pdf_path = day_dir / f"{safe_title}.pdf"
                
                # Handle filename conflicts
                counter = 1
                while pdf_path.exists():
                    stem = safe_filename(title, self.config.max_filename_length - 10)
                    pdf_path = day_dir / f"{stem}_{counter}.pdf"
                    counter += 1
                
                self.logger.info(f"{'[DRY RUN] ' if self.config.dry_run else ''}Archiving: {title}")
                self.logger.debug(f"  Safe filename: {safe_title}")
                self.logger.debug(f"  PDF: {pdf_path}")
                
                if self.config.dry_run:
                    processed += 1
                    continue
                
                success = await self.snap_and_close_tab(tab, pdf_path)
                if success:
                    self.store_locally(url, title, pdf_path, now)
                    processed += 1
                    self.logger.info(f"✓ Archived successfully")
                else:
                    self.logger.error(f"✗ Failed to archive")
        
        finally:
            tmp_history.unlink(missing_ok=True)
        
        return processed, len(page_tabs)

def parse_args():
    parser = argparse.ArgumentParser(description="Archive idle Chrome tabs to PDF")
    parser.add_argument("--days", "-d", type=int, default=14)
    parser.add_argument("--port", "-p", type=int, default=9222)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--dry-run", "-n", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser.parse_args()


async def main():
    args = parse_args()
    
    config = Config()
    config.days_idle = args.days
    config.debug_port = args.port
    config.dry_run = args.dry_run
    config.verbose = args.verbose
    
    if args.output:
        config.pdf_root = args.output
    if args.profile:
        config.profile_dir = args.profile
    
    archiver = TabArchiver(config)
    
    archiver.logger.info("🚀 Starting tab archiver")
    archiver.logger.info(f"Configuration:")
    archiver.logger.info(f"  Days idle: {config.days_idle}")
    archiver.logger.info(f"  Debug port: {config.debug_port}")
    archiver.logger.info(f"  Output directory: {config.pdf_root}")
    archiver.logger.info(f"  Profile directory: {config.profile_dir}")
    archiver.logger.info(f"  Dry run: {config.dry_run}")
    
    try:
        processed, total = await archiver.process_tabs()
        
        if config.dry_run:
            archiver.logger.info(f"🔍 Dry run complete: {processed} of {total} tabs would be archived")
        else:
            archiver.logger.info(f"✅ Complete: {processed} of {total} tabs archived")
            if processed > 0:
                archiver.logger.info(f"📄 Index available at: file://{archiver.html_index.absolute()}")
    
    except KeyboardInterrupt:
        archiver.logger.info("🛑 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        archiver.logger.error(f"💥 Unexpected error: {e}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())