"""
MOM IT Helpdesk — Windows background server daemon.
Launched by setup.bat via pythonw.exe (no console window).
Restarts uvicorn automatically if it crashes.
"""
import subprocess
import sys
import os
import time
from pathlib import Path

ROOT    = Path(__file__).parent
BACKEND = ROOT / "backend"
LOG     = ROOT / "logs" / "server.log"
LOG.parent.mkdir(exist_ok=True)

CREATE_NO_WINDOW = 0x08000000

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

while True:
    with open(LOG, "a", encoding="utf-8") as lf:
        p = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app",
             "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(BACKEND),
            stdout=lf,
            stderr=lf,
            env=env,
            creationflags=CREATE_NO_WINDOW,
        )
        p.wait()
    time.sleep(3)
