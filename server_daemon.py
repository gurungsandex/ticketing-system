"""
IT Ticketing System — background server daemon.

Launched by setup.bat via pythonw.exe on Windows (no console window). Restarts
uvicorn automatically if it crashes.

The no-console creation flag only exists on Windows; passing it on macOS/Linux
raises ValueError, so it is applied conditionally and this module stays usable
for manual supervised runs on any platform.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT    = Path(__file__).parent
BACKEND = ROOT / "backend"
LOG     = ROOT / "logs" / "server.log"
LOG.parent.mkdir(exist_ok=True)

HOST = os.environ.get("HOST", "0.0.0.0")  # nosec B104 - LAN server binds all interfaces by design
PORT = os.environ.get("PORT", "8000")

# CREATE_NO_WINDOW is a Windows-only process creation flag.
_popen_kwargs = {}
if sys.platform == "win32":
    _popen_kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

while True:
    with open(LOG, "a", encoding="utf-8") as lf:
        p = subprocess.Popen(  # nosec B603 - fixed argv, no shell, no user input
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", HOST, "--port", str(PORT)],
            cwd=str(BACKEND),
            stdout=lf,
            stderr=lf,
            env=env,
            **_popen_kwargs,
        )
        p.wait()
    time.sleep(3)
