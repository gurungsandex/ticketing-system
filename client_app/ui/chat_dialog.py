"""
End-user live chat window.

Uses REST polling (consistent with the rest of the client) so it works through
the same firewall/proxy path as ticket submission — no separate WebSocket port
to open. Messages are scoped to this client's session id + client_id.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

import api_client


class ChatDialog(QDialog):
    def __init__(self, client_id: str, display_name: str, hostname: str, parent=None,
                 agents_available: bool = True):
        super().__init__(parent)
        self._client_id = client_id
        self._display_name = display_name
        self._hostname = hostname
        self._session_id = None
        self._last_id = 0
        self._agents_available = agents_available

        self.setWindowTitle("Live Chat with IT Support")
        self.setMinimumSize(420, 520)
        self._build_ui()

        self._start()

        self._timer = QTimer(self)
        self._timer.setInterval(2500)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget(); header.setObjectName("chatHeader"); header.setFixedHeight(48)
        hl = QHBoxLayout(header); hl.setContentsMargins(14, 0, 14, 0)
        title = QLabel("💬  IT Support")
        title.setStyleSheet("color:white;font-weight:bold;font-size:14px")
        hl.addWidget(title); hl.addStretch()
        self._status = QLabel("Connecting…")
        self._status.setStyleSheet("color:rgba(255,255,255,.85);font-size:11px")
        hl.addWidget(self._status)
        root.addWidget(header)

        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background:#F8FAFC;border:none")
        self._msg_container = QWidget()
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(12, 12, 12, 12)
        self._msg_layout.setSpacing(8)
        self._msg_layout.addStretch()
        self._scroll.setWidget(self._msg_container)
        root.addWidget(self._scroll, 1)

        input_row = QWidget(); input_row.setObjectName("chatInputRow")
        il = QHBoxLayout(input_row); il.setContentsMargins(10, 8, 10, 10); il.setSpacing(6)
        self._input = QLineEdit(); self._input.setPlaceholderText("Type your message…")
        self._input.setFixedHeight(36)
        self._input.returnPressed.connect(self._send)
        il.addWidget(self._input)
        send = QPushButton("Send"); send.setObjectName("chatSend"); send.setFixedHeight(36)
        send.clicked.connect(self._send)
        il.addWidget(send)
        root.addWidget(input_row)

        self.setStyleSheet("""
            QWidget#chatHeader { background:#059669; }
            QWidget#chatInputRow { background:#FFFFFF; border-top:1px solid #E2E8F0; }
            QLineEdit { border:1px solid #E2E8F0; border-radius:8px; padding:4px 10px; }
            QLineEdit:focus { border-color:#059669; }
            QPushButton#chatSend { background:#059669; color:white; border:none;
                border-radius:8px; font-weight:bold; padding:0 16px; }
            QPushButton#chatSend:hover { background:#047857; }
        """)

    def _add_bubble(self, sender_role: str, name: str, content: str):
        row = QHBoxLayout()
        bubble = QLabel(content)
        bubble.setWordWrap(True)
        bubble.setMaximumWidth(300)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if sender_role == "user":
            bubble.setStyleSheet(
                "background:#059669;color:white;border-radius:10px;padding:8px 11px;")
            row.addStretch(); row.addWidget(bubble)
        elif sender_role == "system":
            bubble.setStyleSheet(
                "background:transparent;color:#94A3B8;font-size:11px;font-style:italic;")
            row.addStretch(); row.addWidget(bubble); row.addStretch()
        else:
            bubble.setStyleSheet(
                "background:white;color:#1E293B;border:1px solid #E2E8F0;"
                "border-radius:10px;padding:8px 11px;")
            wrap = QVBoxLayout(); wrap.setSpacing(2)
            who = QLabel(name or "IT Support")
            who.setStyleSheet("color:#64748B;font-size:10px;font-weight:600")
            wrap.addWidget(who); wrap.addWidget(bubble)
            row.addLayout(wrap); row.addStretch()
        # Insert before the trailing stretch.
        self._msg_layout.insertLayout(self._msg_layout.count() - 1, row)
        QTimer.singleShot(50, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _start(self):
        session = api_client.start_chat(
            self._client_id, self._display_name, self._hostname)
        if not session:
            self._status.setText("Could not connect")
            self._add_bubble("system", "", "Unable to reach the server. Please try again later.")
            self._input.setEnabled(False)
            return
        self._session_id = session["id"]
        if session.get("status") == "waiting":
            if self._agents_available:
                self._status.setText("Waiting for an agent…")
                self._add_bubble("system", "", "You're in the queue. An agent will be with you shortly.")
            else:
                self._status.setText("No agents online")
                self._add_bubble(
                    "system", "",
                    "Our team is offline right now — go ahead and leave a message. "
                    "We'll reply as soon as someone's back online.",
                )
        else:
            self._status.setText("Connected")
        self._poll()

    def _poll(self):
        if not self._session_id:
            return
        data = api_client.poll_chat(self._session_id, self._client_id, self._last_id)
        if not data:
            return
        status = data.get("status")
        if status == "active":
            self._status.setText("Connected with " + (data.get("agent_username") or "IT"))
        elif status == "closed":
            self._status.setText("Chat ended")
            self._input.setEnabled(False)
            self._timer.stop()
        for m in data.get("messages", []):
            self._add_bubble(m["sender_role"], m.get("sender_name", ""), m["content"])
            self._last_id = max(self._last_id, m["id"])

    def _send(self):
        text = self._input.text().strip()
        if not text or not self._session_id:
            return
        self._input.clear()
        ok = api_client.send_chat_message(self._session_id, self._client_id, text)
        if not ok:
            self._add_bubble("system", "", "Message failed to send. Check your connection.")
        else:
            self._poll()

    def closeEvent(self, event):
        try:
            self._timer.stop()
            if self._session_id:
                api_client.close_chat(self._session_id, self._client_id)
        except Exception:
            pass
        super().closeEvent(event)
