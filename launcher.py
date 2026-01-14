#!/usr/bin/env python3
"""
Weather Trader Application Launcher

This is the main entry point for the macOS application bundle.
It starts the FastAPI server and opens the browser to the dashboard.
"""
import os
import sys
import webbrowser
import subprocess
import threading
import time
from pathlib import Path


def get_app_dir() -> Path:
    """Get the application directory."""
    if getattr(sys, 'frozen', False):
        # Running in py2app bundle
        return Path(sys.executable).parent.parent / "Resources"
    else:
        # Running from source
        return Path(__file__).parent


def start_server():
    """Start the FastAPI server."""
    app_dir = get_app_dir()

    # Add app directory to Python path
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    # Import and run uvicorn
    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8741,
        log_level="info",
    )


def open_browser():
    """Open the browser to the dashboard after a delay."""
    time.sleep(2)  # Wait for server to start
    webbrowser.open("http://localhost:8741")


def main():
    """Main entry point."""
    # Check if we should use menu bar mode
    use_menubar = os.environ.get("WEATHER_TRADER_MENUBAR", "true").lower() == "true"

    if use_menubar:
        # Try to run menu bar app
        try:
            from macos.menubar import main as menubar_main
            menubar_main()
        except ImportError:
            # Fall back to direct server mode
            pass
    else:
        # Direct server mode
        # Start browser opener in background thread
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()

        # Start server (blocking)
        start_server()


if __name__ == "__main__":
    main()
