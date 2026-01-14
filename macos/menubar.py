"""macOS menu bar controller using rumps."""
import webbrowser
import subprocess
import sys
import os
import signal
from pathlib import Path

try:
    import rumps
except ImportError:
    print("rumps not installed. Install with: pip install rumps")
    sys.exit(1)


class WeatherTraderMenuBar(rumps.App):
    """Menu bar application for Weather Trader."""

    def __init__(self):
        super().__init__(
            "Weather Trader",
            icon=self._get_icon_path(),
            quit_button=None,
        )

        # State
        self.server_process = None
        self.status = "stopped"
        self.bankroll = 0.0
        self.daily_pnl = 0.0
        self.open_positions = 0

        # Build menu
        self.menu = [
            rumps.MenuItem("Trading Status", callback=None),
            None,  # Separator
            rumps.MenuItem("Bankroll: $0.00", callback=None),
            rumps.MenuItem("Today's P&L: $0.00", callback=None),
            rumps.MenuItem("Open Positions: 0", callback=None),
            None,
            rumps.MenuItem("Open Dashboard", callback=self.open_dashboard, key="d"),
            rumps.MenuItem("Pause Trading", callback=self.toggle_pause, key="p"),
            rumps.MenuItem("Emergency Stop", callback=self.emergency_stop, key="e"),
            None,
            rumps.MenuItem("Quit Weather Trader", callback=self.quit_app, key="q"),
        ]

        # Start server on launch
        self.start_server()

    def _get_icon_path(self) -> str:
        """Get path to menu bar icon."""
        # Look for icon in resources
        possible_paths = [
            Path(__file__).parent / "resources" / "icon.png",
            Path(__file__).parent.parent / "macos" / "resources" / "icon.png",
            Path.home() / "Library" / "Application Support" / "WeatherTrader" / "icon.png",
        ]

        for path in possible_paths:
            if path.exists():
                return str(path)

        return None  # Use default

    def start_server(self):
        """Start the FastAPI server."""
        try:
            # Get the app directory
            app_dir = Path(__file__).parent.parent

            # Start uvicorn server
            self.server_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8741",
                ],
                cwd=str(app_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.status = "active"
            self._update_status_display()

            # Open browser after short delay
            rumps.Timer(self._open_browser_delayed, 2).start()

        except Exception as e:
            rumps.alert(
                title="Server Error",
                message=f"Failed to start server: {e}",
            )

    def _open_browser_delayed(self, _):
        """Open browser after delay (called by timer)."""
        webbrowser.open("http://localhost:8741")

    def stop_server(self):
        """Stop the FastAPI server."""
        if self.server_process:
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            self.server_process = None

        self.status = "stopped"
        self._update_status_display()

    def _update_status_display(self):
        """Update menu items with current status."""
        status_item = self.menu["Trading Status"]
        if status_item:
            if self.status == "active":
                status_item.title = "● Trading Active"
            elif self.status == "paused":
                status_item.title = "● Trading Paused"
            else:
                status_item.title = "○ Trading Stopped"

        # Update stats
        bankroll_item = self.menu.get("Bankroll: $0.00")
        if bankroll_item:
            bankroll_item.title = f"Bankroll: ${self.bankroll:.2f}"

        pnl_item = self.menu.get("Today's P&L: $0.00")
        if pnl_item:
            sign = "+" if self.daily_pnl >= 0 else ""
            pnl_item.title = f"Today's P&L: {sign}${self.daily_pnl:.2f}"

        positions_item = self.menu.get("Open Positions: 0")
        if positions_item:
            positions_item.title = f"Open Positions: {self.open_positions}"

    @rumps.clicked("Open Dashboard")
    def open_dashboard(self, _):
        """Open the dashboard in browser."""
        webbrowser.open("http://localhost:8741")

    @rumps.clicked("Pause Trading")
    def toggle_pause(self, sender):
        """Toggle trading pause state."""
        if self.status == "active":
            self.status = "paused"
            sender.title = "Resume Trading"
        else:
            self.status = "active"
            sender.title = "Pause Trading"

        self._update_status_display()

        # Send command to API
        try:
            import urllib.request
            endpoint = "pause" if self.status == "paused" else "start"
            req = urllib.request.Request(
                f"http://localhost:8741/api/v1/status/control/{endpoint}",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            print(f"Error toggling pause: {e}")

    @rumps.clicked("Emergency Stop")
    def emergency_stop(self, _):
        """Emergency stop trading."""
        response = rumps.alert(
            title="Emergency Stop",
            message="Stop all trading? Open positions will remain until resolution.",
            ok="Stop Trading",
            cancel="Cancel",
        )

        if response == 1:  # OK clicked
            try:
                import urllib.request
                req = urllib.request.Request(
                    "http://localhost:8741/api/v1/status/control/stop",
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)

                self.status = "stopped"
                self._update_status_display()

            except Exception as e:
                rumps.alert(
                    title="Error",
                    message=f"Failed to stop trading: {e}",
                )

    @rumps.clicked("Quit Weather Trader")
    def quit_app(self, _):
        """Quit the application."""
        response = rumps.alert(
            title="Quit Weather Trader",
            message="Stop trading and quit? Open positions will remain until resolution.",
            ok="Quit",
            cancel="Cancel",
        )

        if response == 1:  # OK clicked
            self.stop_server()
            rumps.quit_application()


def main():
    """Main entry point for menu bar app."""
    WeatherTraderMenuBar().run()


if __name__ == "__main__":
    main()
