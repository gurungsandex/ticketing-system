/**
 * PM2 Ecosystem — MOM IT Helpdesk v4.0
 * Works on Windows and macOS.
 *
 * QUICK START:
 *   npm install -g pm2
 *   pm2 start ecosystem.config.js
 *   pm2 save
 *
 * COMMANDS:
 *   pm2 start ecosystem.config.js   → start (or restart if already running)
 *   pm2 stop helpdesk               → stop the server
 *   pm2 restart helpdesk            → restart
 *   pm2 delete helpdesk             → remove from PM2 process list
 *   pm2 status                      → show running processes
 *   pm2 logs helpdesk               → live log tail
 *   pm2 logs helpdesk --lines 100   → last 100 log lines
 *
 * AUTO-START ON BOOT:
 *   Windows : pm2-startup install   (then follow the printed instruction)
 *   macOS   : pm2 startup           (then run the printed sudo command)
 *   Both    : pm2 save              (run after startup command)
 *
 * UNINSTALL:
 *   pm2 delete helpdesk
 *   pm2 save
 *   Windows : pm2-startup uninstall
 *   macOS   : pm2 unstartup launchd
 */

module.exports = {
  apps: [
    {
      name: "helpdesk",

      // start_server.py calls uvicorn.run() directly — no PATH lookups needed.
      // PM2 will use whichever `python` / `python3` is on your system PATH.
      script: "start_server.py",
      interpreter: process.platform === "win32" ? "python" : "python3",

      // Run from the backend folder so relative imports resolve correctly
      cwd: "./backend",

      // Crash recovery
      autorestart: true,
      restart_delay: 3000,
      max_restarts: 10,

      // Restart if memory exceeds 512 MB
      max_memory_restart: "512M",

      // Do not watch for file changes in production
      watch: false,

      // Environment — override host/port here if needed
      env: {
        HOST: "0.0.0.0",
        PORT: "8000",
      },

      // Logs — written to ./logs/ relative to the project root
      out_file:         "../logs/out.log",
      error_file:       "../logs/err.log",
      log_date_format:  "YYYY-MM-DD HH:mm:ss",
      merge_logs:       true,
    },
  ],
};
