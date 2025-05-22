#!/usr/bin/env python3
"""
Fixed minimal test script with proper Windows filename handling
"""
import asyncio
import requests
import re
from playwright.async_api import async_playwright
from pathlib import Path

def safe_filename(text: str, max_length: int = 30) -> str:
    """Create a safe filename from text for Windows."""
    # Remove or replace problematic characters
    safe = re.sub(r'[<>:"/\\|?*]', '_', text)
    safe = re.sub(r'[^\w\s.-]', '', safe)
    safe = re.sub(r'\s+', ' ', safe).strip()
    
    if len(safe) > max_length:
        safe = safe[:max_length].rsplit(' ', 1)[0]  # Break at word boundary
    
    return safe or "untitled"

async def test_pdf_generation():
    """Test PDF generation with proper filename handling."""
    
    # Get tabs from Chrome
    try:
        response = requests.get("http://localhost:9222/json", timeout=10)
        tabs = response.json()
        page_tabs = [tab for tab in tabs if tab.get("type") == "page"]
        
        print(f"Found {len(page_tabs)} page tabs")
        
        if not page_tabs:
            print("No page tabs found!")
            return
        
        # Test with first tab
        tab = page_tabs[0]
        title = tab.get("title", "test")
        url = tab.get("url", "")
        
        print(f"Testing with: {title}")
        print(f"URL: {url}")
        
        # Create output directory
        output_dir = Path("test_pdfs")
        output_dir.mkdir(exist_ok=True)
        
        # Use the safe filename function
        clean_title = safe_filename(title, 30)
        pdf_path = output_dir / f"{clean_title}.pdf"
        
        print(f"Safe filename: {clean_title}")
        print(f"PDF path: {pdf_path}")
        
        # Generate PDF
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            print(f"Navigating to {url}...")
            await page.goto(url, wait_until='domcontentloaded', timeout=15000)
            await page.wait_for_timeout(2000)
            
            print(f"Generating PDF...")
            await page.pdf(path=str(pdf_path), print_background=True, format='A4')
            
            await browser.close()
            
            print(f"✅ PDF saved to: {pdf_path}")
            print(f"File size: {pdf_path.stat().st_size} bytes")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_pdf_generation())