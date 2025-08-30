"""
MW75 Testing Guide and Utilities

Provides testing guidance and utility functions for MW75 EEG streaming validation.
"""

import webbrowser
from pathlib import Path

from ..utils.logging import get_logger


class TestGuide:
    """Interactive testing guide for MW75 EEG streaming"""

    def __init__(self) -> None:
        self.logger = get_logger(__name__)

    def show_quick_start(self) -> None:
        """Display quick start testing instructions"""
        print("\n" + "=" * 70)
        print("MW75 EEG Streamer - Quick Test Guide")
        print("=" * 70)

        print("\nSTEP 1: Start Test Server")
        print("   Terminal 1:")
        print("   $ python -m mw75_streamer.testing")
        print("   or")
        print("   $ python -m mw75_streamer.testing --advanced")

        print("\nSTEP 2: Start EEG Streaming")
        print("   Terminal 2:")
        print("   $ python -m mw75_streamer -ws ws://localhost:8080")

        print("\nSTEP 3: Optional Browser Visualization")
        print("   Open eeg_test_client.html in your browser")
        print("   (Located in mw75_streamer/testing/)")

        print("\nEXPECTED RESULTS:")
        print("   • Test server receives JSON EEG packets")
        print("   • Packet counter increments correctly")
        print("   • Channel data shows realistic µV values")
        print("   • No dropped packets (or minimal drops)")
        print("   • Browser client displays real-time data")

        print("\n🔧 TROUBLESHOOTING:")
        print("   • Port 8080 in use? Try: --port 9000")
        print("   • Missing websockets? Run: pip install websockets")
        print("   • MW75 not paired? Check System Preferences > Bluetooth")
        print("   • No data? Ensure MW75 is on and electrodes make contact")

        print("=" * 70 + "\n")

    def open_browser_client(self, port: int = 8080) -> bool:
        """
        Open the browser test client

        Args:
            port: WebSocket server port for the browser client URL

        Returns:
            True if browser was opened successfully, False otherwise
        """
        try:
            # Find the HTML file
            html_file = Path(__file__).parent / "eeg_test_client.html"

            if not html_file.exists():
                self.logger.error(f"Browser test client not found: {html_file}")
                return False

            # Open in browser
            file_url = f"file://{html_file.absolute()}"
            webbrowser.open(file_url)

            self.logger.info(f"Browser test client opened: {file_url}")
            self.logger.info(f"Make sure to connect to: ws://localhost:{port}/browser")

            return True

        except Exception as e:
            self.logger.error(f"Error opening browser client: {e}")
            return False

    def validate_setup(self) -> dict:
        """
        Validate the testing setup

        Returns:
            Dictionary with validation results
        """
        results = {
            "websockets_available": False,
            "html_client_available": False,
            "port_8080_available": True,  # We'll assume it's available
        }

        # Check websockets library
        try:
            import websockets  # noqa: F401

            results["websockets_available"] = True
            self.logger.info("websockets library is available")
        except ImportError:
            self.logger.error("websockets library not found. Install with: pip install websockets")

        # Check HTML client file
        html_file = Path(__file__).parent / "eeg_test_client.html"
        if html_file.exists():
            results["html_client_available"] = True
            self.logger.info("Browser test client is available")
        else:
            self.logger.error("Browser test client not found")

        # Check port availability (basic check)
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", 8080))
            sock.close()

            if result == 0:
                results["port_8080_available"] = False
                self.logger.warning("Port 8080 appears to be in use")
            else:
                self.logger.info("Port 8080 appears to be available")

        except Exception as e:
            self.logger.warning(f"Could not check port 8080 availability: {e}")

        return results

    def show_test_checklist(self) -> None:
        """Display testing checklist for validation"""
        print("\n" + "=" * 70)
        print("MW75 EEG Streaming Test Checklist")
        print("=" * 70)

        checklist = [
            "[ ] Test server starts and listens on port 8080",
            "[ ] EEG streamer connects to WebSocket successfully",
            "[ ] JSON data is received and parsed correctly",
            "[ ] Packet counters increment sequentially",
            "[ ] Channel data shows realistic µV values (-200 to +200 range)",
            "[ ] REF and DRL values are present and reasonable",
            "[ ] No dropped packets (or minimal < 1%)",
            "[ ] Disconnected electrodes show sentinel values (8388607)",
            "[ ] Clean disconnection when streamer stops",
            "[ ] Browser client can connect and display data",
            "[ ] Real-time statistics update correctly",
            "[ ] All 12 EEG channels are present and updating",
        ]

        for item in checklist:
            print(f"   {item}")

        print("\nTips:")
        print("   • Good electrode contact is crucial for clean data")
        print("   • Streaming rate should be ~500 Hz (500 packets/second)")
        print("   • Checksum errors indicate communication issues")
        print("   • Counter jumps indicate dropped packets")

        print("=" * 70 + "\n")


def show_quick_start() -> None:
    """Convenience function to show quick start guide"""
    guide = TestGuide()
    guide.show_quick_start()


def open_browser_test() -> bool:
    """Convenience function to open browser test client"""
    guide = TestGuide()
    return guide.open_browser_client()


def validate_test_setup() -> dict:
    """Convenience function to validate testing setup"""
    guide = TestGuide()
    return guide.validate_setup()


if __name__ == "__main__":
    # If run directly, show the quick start guide
    show_quick_start()
