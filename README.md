# Chrome Tab Closer

A smart Chrome tab management tool that automatically closes idle tabs based on your browsing history, helping you maintain a clean browser while preserving access to closed content through a searchable HTML index.

## 🚀 Features

- **Smart Tab Detection**: Identifies tabs that haven't been visited for a specified number of days
- **Safe Closing**: Only closes tabs with actual browsing history (skips new/blank tabs)
- **HTML Index**: Creates a searchable log of all closed tabs with clickable links
- **Dry Run Mode**: Preview what would be closed before actually doing it
- **Flexible Configuration**: Customize idle thresholds, output directories, and more
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Multiple Chrome Instances**: Can work with different Chrome profiles and debug ports

## 📋 Requirements

- **Python 3.8+**
- **Google Chrome** (or Chromium-based browser)
- **Python packages**: `requests` (install with `pip install requests`)

## 🛠️ Installation

1. **Clone or download** this repository
2. **Install dependencies**:
   ```bash
   pip install requests
   ```
3. **Make Chrome accessible** by starting it with debug mode (see Setup section)

## ⚙️ Setup

### Option 1: Quick Setup (Recommended)

1. **Save the Chrome Debug Launcher** as `Chrome_Debug.bat`:
   ```batch
   @echo off
   echo Closing all Chrome processes...
   taskkill /f /im chrome.exe >nul 2>&1
   echo Waiting for Chrome to close completely...
   timeout /t 2 /nobreak >nul
   echo Starting Chrome with debug mode...
   start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   echo Chrome started with debug mode on port 9222
   pause
   ```

2. **Save the Quick Runner** as `Close_Tabs.bat`:
   ```batch
   @echo off
   cd /d "C:\path\to\your\script\directory"
   echo Choose an option:
   echo 1. Close tabs older than 7 days (recommended)
   echo 2. Close tabs older than 14 days  
   echo 3. Close tabs older than 30 days
   echo 4. Dry run - see what would be closed (7 days)
   set /p choice="Enter your choice (1-4): "
   
   if "%choice%"=="1" python tab_closer.py --days 7 --verbose
   if "%choice%"=="2" python tab_closer.py --days 14 --verbose
   if "%choice%"=="3" python tab_closer.py --days 30 --verbose
   if "%choice%"=="4" python tab_closer.py --days 7 --dry-run --verbose
   pause
   ```

### Option 2: Manual Setup

1. **Close all Chrome windows completely**
2. **Start Chrome with debug mode**:
   ```bash
   # Windows
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
   
   # macOS
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
   
   # Linux
   google-chrome --remote-debugging-port=9222
   ```

## 🎯 Usage

### Basic Commands

```bash
# Close tabs idle for 7 days (recommended)
python tab_closer.py --days 7

# Preview what would be closed (dry run)
python tab_closer.py --days 7 --dry-run

# Close tabs idle for 14 days with verbose output
python tab_closer.py --days 14 --verbose

# Close ALL tabs (use with caution!)
python tab_closer.py --days 0
```

### Advanced Options

```bash
# Custom Chrome profile
python tab_closer.py --days 7 --profile "C:\Users\Username\ChromeCustom\Default"

# Custom debug port
python tab_closer.py --days 7 --port 9223

# Custom log directory
python tab_closer.py --days 7 --log-dir "C:\MyLogs\TabCloser"

# Combine options
python tab_closer.py --days 7 --verbose --dry-run --port 9222
```

### Command Line Arguments

| Argument | Short | Default | Description |
|----------|-------|---------|-------------|
| `--days` | `-d` | `7` | Close tabs idle for this many days |
| `--port` | `-p` | `9222` | Chrome debug port |
| `--profile` | | Auto-detected | Chrome profile directory |
| `--log-dir` | `-l` | `~/Documents/TabCloser` | Directory for log files |
| `--dry-run` | `-n` | `False` | Preview mode - don't actually close tabs |
| `--verbose` | `-v` | `False` | Enable detailed logging |

## 📊 Output

### HTML Index File

The script creates `closed_tabs_index.html` in your log directory with:
- **Searchable table** of all closed tabs
- **Clickable URLs** to revisit closed pages
- **Domain grouping** and idle day information
- **Responsive design** that works on all devices

**Example location**: `C:\Users\Username\Documents\TabCloser\closed_tabs_index.html`

### Console Output

```
🚀 Starting tab closer
Configuration:
  Days idle: 7
  Debug port: 9222
  Log directory: C:\Users\Username\Documents\TabCloser
  Profile directory: C:\Users\Username\AppData\Local\Google\Chrome\User Data\Default
  Dry run: False

Looking for tabs idle since 2025-05-15 19:30
Found 15 open tabs
Closing: Old Article - Example.com
  URL: https://example.com/article
  Domain: example.com
  Last visit: 2025-05-10 14:22
  Idle for: 12 days
✓ Closed successfully

✅ Complete: 5 of 15 tabs closed
📄 Index available at: file://C:\Users\Username\Documents\TabCloser\closed_tabs_index.html
```

## 🛡️ Safety Features

### What Gets Closed
- ✅ Regular web pages (http/https)
- ✅ Tabs with browsing history
- ✅ Tabs older than specified threshold

### What Gets Skipped
- ❌ Chrome internal pages (`chrome://`, `chrome-extension://`)
- ❌ About pages (`about:blank`)
- ❌ Tabs without browsing history
- ❌ Tabs newer than the idle threshold

### Dry Run Mode
Always test with `--dry-run` first to see what would be closed:
```bash
python tab_closer.py --days 7 --dry-run --verbose
```

## 🔧 Troubleshooting

### "Failed to connect to Chrome DevTools"
- **Cause**: Chrome not running with debug mode
- **Solution**: Start Chrome with `--remote-debugging-port=9222`
- **Check**: Visit `http://localhost:9222` in browser - should show JSON

### "History database not found"
- **Cause**: Incorrect Chrome profile path
- **Solution**: Use `--profile` flag with correct path
- **Windows default**: `%LOCALAPPDATA%\Google\Chrome\User Data\Default`
- **macOS default**: `~/Library/Application Support/Google/Chrome/Default`
- **Linux default**: `~/.config/google-chrome/Default`

### "No tabs found" or tabs not closing
- **Check**: Make sure you have actual web pages open (not just new tab pages)
- **Verify**: Tabs have been visited (appear in browser history)
- **Test**: Use `--verbose` flag to see detailed processing info

### Permission errors
- **Windows**: Run as Administrator if needed
- **macOS/Linux**: Check file permissions on log directory

## 🏗️ Advanced Configuration

### Multiple Chrome Instances

You can run multiple Chrome instances with different profiles:

```bash
# Work Chrome (port 9222)
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\ChromeWork"

# Personal Chrome (port 9223)  
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9223 --user-data-dir="%USERPROFILE%\ChromePersonal"
```

Then run the script against each:
```bash
# Close work tabs
python tab_closer.py --days 7 --port 9222 --profile "%USERPROFILE%\ChromeWork\Default"

# Close personal tabs
python tab_closer.py --days 14 --port 9223 --profile "%USERPROFILE%\ChromePersonal\Default"
```

### Automation

#### Windows Task Scheduler
1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (e.g., daily at 6 PM)
4. Set action: Start Program
   - **Program**: `python`
   - **Arguments**: `tab_closer.py --days 7`
   - **Start in**: `C:\path\to\script\directory`

#### Cron (macOS/Linux)
```bash
# Edit crontab
crontab -e

# Add line for daily execution at 6 PM
0 18 * * * cd /path/to/script && python tab_closer.py --days 7
```

## 🚦 Best Practices

### Recommended Thresholds
- **Conservative**: 14+ days for most users
- **Moderate**: 7 days for active browsers
- **Aggressive**: 3-5 days for heavy tab users
- **Testing**: Always start with `--dry-run`

### Daily Workflow
1. **Morning**: Start Chrome with debug mode (`Chrome_Debug.bat`)
2. **Browse normally** throughout the day
3. **Evening**: Run tab closer (`Close_Tabs.bat` → Option 1)
4. **Weekly**: Review HTML index for any important closed tabs

### Backup Strategy
- **Bookmarks**: Important pages should be bookmarked first
- **Read Later**: Use browser's reading list for articles
- **HTML Index**: Regular check of closed tabs index

## 📝 File Structure

```
your-project-directory/
├── tab_closer.py              # Main script
├── Chrome_Debug.bat           # Chrome launcher (Windows)
├── Close_Tabs.bat            # Quick runner (Windows)
├── README.md                 # This file
└── logs/                     # Created automatically
    └── closed_tabs_index.html # HTML index of closed tabs
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is released under the MIT License. See LICENSE file for details.

## ⚠️ Disclaimer

This tool closes browser tabs based on browsing history. While it includes safety measures, always:
- **Test with dry run first**
- **Bookmark important pages**
- **Review the HTML index regularly**
- **Understand that closed tabs cannot be "undone"**

Use at your own risk. The authors are not responsible for any lost tabs or data.

## 🆘 Support

### Common Issues
- Check the Troubleshooting section above
- Ensure Chrome is running with debug mode
- Verify correct profile path
- Test with `--dry-run` first

### Getting Help
- Create an issue with detailed error messages
- Include your command line and output
- Specify your OS and Chrome version
- Include relevant log snippets

---

**Happy tab managing! 🎉**
