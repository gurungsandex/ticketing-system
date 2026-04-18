"""
PM2 entry point — runs uvicorn programmatically.

This file exists so PM2 can launch the server with a plain
`python start_server.py` call, which works identically on
Windows, macOS, and Linux without any interpreter or PATH tricks.

PM2 runs this via ecosystem.config.js (cwd = ./backend).
Do NOT edit the host or port here — change them in ecosystem.config.js
via the HOST / PORT environment variables instead.
"""
import os
import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        workers=1,
        log_level="warning",
    )
