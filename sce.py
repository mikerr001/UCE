#!/usr/bin/env python3
"""
NexForge UCE — main entry point.
Launches the web landing page on Replit / headless environments,
or the Tkinter desktop GUI when a real display is available.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)


def _has_real_display() -> bool:
    if sys.platform == 'win32':
        return True
    display = os.environ.get('DISPLAY', '')
    if not display:
        return False
    import subprocess
    try:
        result = subprocess.run(
            ['xdpyinfo', '-display', display],
            capture_output=True, timeout=2
        )
        return result.returncode == 0
    except Exception:
        return False


def main():
    if _has_real_display():
        from ui.app import launch
        launch()
    else:
        from web.server import app
        port = int(os.environ.get('PORT', 5000))
        print(f'NexForge UCE — web interface starting on port {port}')
        app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()
