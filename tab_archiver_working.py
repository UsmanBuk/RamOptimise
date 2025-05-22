#!/usr/bin/env python3
"""
Enhanced Chrome tab closer - closes idle tabs without PDF generation
Simple, fast, and practical tab management
"""

import argparse
import asyncio
import datetime as dt
import logging
import platform
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

# ─── Configuration ──────────────────────────────────────────────────────────
class Config:
    def __init__(self):
        self.days_idle = 7
        self.debug_port = 9222
        self.log_root = self.get_default_log_root()
        self.profile_dir = self.get_default_profile_dir()
        self.connection_timeout = 10
        self.dry_run = False
        self.verbose = False
        
    def get_default_log_root(self) -> Path:
        if platform.system() == "Windows":
            return Path.home() / "Documents" / "TabCloser"
        else:
            return Path.home() / "TabCloser"
    
    def get_default_profile_dir(self) -> Path:
        system = platform.system()
        if system == "Windows":
            return Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default"
        else:
            return Path.home() / ".config" / "google-chrome" / "Default"

# ─── Global constants ────────────────────────────────────────────────────────
CHROME_EPOCH = dt.datetime(1601, 1, 1)
TABLE_HEADERS = ("Date", "Title", "URL", "Domain", "Idle Days")

# ─── Logging setup ──────────────────────────────────────────────────────────
def setup_logging(verbose: bool = False) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    return logging.getLogger(__name__)

# ─── Helper functions ────────────────────────────────────────────────────────
def chrome_ts(microseconds: int) -> dt.datetime:
    return CHROME_EPOCH + dt.timedelta(microseconds=microseconds)

def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return "unknown"

class TabCloser:
    def __init__(self, config: Config):
        self.config = config
        self.logger = setup_logging(config.verbose)
        self.history_path = config.profile_dir / "History"
        self.html_index = config.log_root / "closed_tabs_index.html"
        
    def ensure_directories(self) -> None:
        self.config.log_root.mkdir(parents=True, exist_ok=True)
        
    def ensure_html_header(self) -> None:
        """Create or verify index.html with proper header."""
        if self.html_index.exists():
            return
            
        self.ensure_directories()
        
        html_content = """<!doctype html>
<html>
<head>
    <meta charset='utf-8'>
    <title>Closed Tabs Log</title>
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
        .idle-days { text-align: center; font-weight: bold; }
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
    <h1>📑 Closed Tabs Log</h1>
    <div class="stats" id="stats">Loading statistics...</div>
    <input type="text" id="searchInput" class="search-box" placeholder="Search closed tabs..." onkeyup="searchTable()">
    <table>
"""
        
        self.html_index.write_text(html_content, encoding="utf-8")
        
        hdr = "".join(f"<th>{h}</th>" for h in TABLE_HEADERS)
        with self.html_index.open("a", encoding="utf-8") as fp:
            fp.write(f"<tr>{hdr}</tr>\n")
    
    def log_closed_tab_html(self, title: str, url: str, last_visit: dt.datetime, closed_at: dt.datetime) -> None:
        """Log a closed tab to the HTML index."""
        self.ensure_html_header()
        
        domain = get_domain(url)
        idle_days = (closed_at - last_visit).days
        
        row = (
            f"<tr>"
            f"<td>{closed_at:%Y-%m-%d %H:%M}</td>"
            f"<td><strong>{title}</strong></td>"
            f"<td><a href='{url}' target='_blank' class='url'>{url[:100]}{'...' if len(url) > 100 else ''}</a></td>"
            f"<td><span class='domain'>{domain}</span></td>"
            f"<td class='idle-days'>{idle_days}</td>"
            f"</tr>\n"
        )
        
        with self.html_index.open("a", encoding="utf-8") as fp:
            fp.write(row)
    
    async def get_open_tabs(self) -> List[Dict]:
        """Retrieve list of open tabs from Chrome DevTools."""
        try:
            response = requests.get(
                f"http://localhost:{self.config.debug_port}/json",
                timeout=self.config.connection_timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            self.logger.error(f"Failed to connect to Chrome DevTools: {e}")
            self.logger.info(f"Make sure Chrome is running with --remote-debugging-port={self.config.debug_port}")
            return []
    
    def get_tab_history(self, url: str, tmp_history: Path) -> Optional[dt.datetime]:
        """Get last visit time for a URL from Chrome history."""
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
    
    async def close_tab(self, tab: Dict) -> bool:
        """Close a single tab."""
        tab_id = tab.get("id")
        if not tab_id:
            self.logger.warning(f"No tab ID for tab: {tab.get('title', 'Unknown')}")
            return False
        
        try:
            close_url = f"http://localhost:{self.config.debug_port}/json/close/{tab_id}"
            response = requests.post(close_url, timeout=self.config.connection_timeout)
            
            if response.status_code == 200:
                return True
            else:
                self.logger.warning(f"Failed to close tab, status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error closing tab: {e}")
            return False
    
    async def process_tabs(self) -> Tuple[int, int]:
        """Main processing logic. Returns (closed, total) counts."""
        if not self.history_path.exists():
            self.logger.error(f"History database not found: {self.history_path}")
            return 0, 0
        
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        cutoff = now - dt.timedelta(days=self.config.days_idle)
        
        self.logger.info(f"Looking for tabs idle since {cutoff:%Y-%m-%d %H:%M}")
        
        # Get open tabs
        tabs = await self.get_open_tabs()
        if not tabs:
            return 0, 0
        
        page_tabs = [tab for tab in tabs if tab.get("type") == "page"]
        self.logger.info(f"Found {len(page_tabs)} open tabs")
        
        # Copy history database
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
                
                # Skip browser internal pages
                if not url or url.startswith(("chrome://", "chrome-extension://", "edge://", "about:")):
                    self.logger.debug(f"Skipping internal page: {title}")
                    continue
                
                # Check last visit time
                last_visit = self.get_tab_history(url, tmp_history)
                if not last_visit:
                    self.logger.debug(f"No history found for: {title}")
                    continue
                
                if last_visit > cutoff:
                    idle_days = (now - last_visit).days
                    self.logger.debug(f"Tab not idle long enough: {title} (idle {idle_days} days, need {self.config.days_idle})")
                    continue
                
                idle_days = (now - last_visit).days
                domain = get_domain(url)
                
                self.logger.info(f"{'[DRY RUN] ' if self.config.dry_run else ''}Closing: {title}")
                self.logger.debug(f"  URL: {url}")
                self.logger.debug(f"  Domain: {domain}")
                self.logger.debug(f"  Last visit: {last_visit:%Y-%m-%d %H:%M}")
                self.logger.debug(f"  Idle for: {idle_days} days")
                
                if self.config.dry_run:
                    processed += 1
                    continue
                
                # Close the tab
                success = await self.close_tab(tab)
                if success:
                    if not self.config.dry_run:
                        self.log_closed_tab_html(title, url, last_visit, now)
                    processed += 1
                    self.logger.info(f"✓ Closed successfully")
                else:
                    self.logger.error(f"✗ Failed to close")
                
                # Small delay to avoid overwhelming Chrome
                await asyncio.sleep(0.1)
        
        finally:
            tmp_history.unlink(missing_ok=True)
        
        return processed, len(page_tabs)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Close idle Chrome tabs")
    parser.add_argument("--days", "-d", type=int, default=7,
                       help="Close tabs idle for this many days (default: 7)")
    parser.add_argument("--port", "-p", type=int, default=9222,
                       help="Chrome debug port (default: 9222)")
    parser.add_argument("--log-dir", "-l", type=Path,
                       help="Directory for log files")
    parser.add_argument("--profile", type=Path,
                       help="Chrome profile directory")
    parser.add_argument("--dry-run", "-n", action="store_true",
                       help="Show what would be closed without actually doing it")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    return parser.parse_args()

async def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup configuration
    config = Config()
    config.days_idle = args.days
    config.debug_port = args.port
    config.dry_run = args.dry_run
    config.verbose = args.verbose
    
    if args.log_dir:
        config.log_root = args.log_dir
    if args.profile:
        config.profile_dir = args.profile
    
    # Initialize closer
    closer = TabCloser(config)
    
    closer.logger.info("🚀 Starting tab closer")
    closer.logger.info(f"Configuration:")
    closer.logger.info(f"  Days idle: {config.days_idle}")
    closer.logger.info(f"  Debug port: {config.debug_port}")
    closer.logger.info(f"  Log directory: {config.log_root}")
    closer.logger.info(f"  Profile directory: {config.profile_dir}")
    closer.logger.info(f"  Dry run: {config.dry_run}")
    
    try:
        processed, total = await closer.process_tabs()
        
        if config.dry_run:
            closer.logger.info(f"🔍 Dry run complete: {processed} of {total} tabs would be closed")
        else:
            closer.logger.info(f"✅ Complete: {processed} of {total} tabs closed")
            if processed > 0:
                closer.logger.info(f"📄 Index available at: file://{closer.html_index.absolute()}")
    
    except KeyboardInterrupt:
        closer.logger.info("🛑 Interrupted by user")
        sys.exit(1)
    except Exception as e:
        closer.logger.error(f"💥 Unexpected error: {e}")
        if config.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())