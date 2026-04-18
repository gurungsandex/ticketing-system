import sys
import os
from typing import Optional

from PySide6.QtCore import Qt, QRect, QPoint, QSize, QMimeData
from PySide6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont, QIcon, QPixmap,
    QDragEnterEvent, QDropEvent,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QScrollArea,
    QGridLayout, QSizePolicy, QFrame, QSystemTrayIcon, QMenu,
    QLayout, QFileDialog,
)

import api_client
from config import APP_NAME

SUBCATEGORIES = {
    "Other": ["Configuration Issue", "General Request", "Other"],
    "Computer / Workstation": [
        "Won't Turn On","Slow Performance","Blue Screen",
        "Freezing / Crashing","Keyboard / Mouse Issue","Other"],
    "Network / Internet / WiFi": [
        "No Internet","Slow Connection","WiFi Dropping",
        "Cannot Access Network Drive","VPN Not Connecting","Other"],
    "Printer": ["Paper Jam","Not Printing","Offline","Driver Issue","Print Quality","Other"],
    "Scanner": ["Not Scanning","Driver Issue","Poor Scan Quality","Cannot Connect","Other"],
    "Phone / VoIP": [
        "No Dial Tone","Poor Call Quality","Cannot Make Calls",
        "Voicemail Issue","Phone Not Registered","Other"],
    "Browser": [
        "Cannot Load Pages","Slow Browser","Extension Issue",
        "Clearing Cache Needed","Homepage Changed","Other"],
    "Software / Application": [
        "App Won't Open","App Crashing","Installation Needed",
        "License Issue","Error Message","Other"],
    "Email": [
        "Cannot Send / Receive","Outlook Not Opening","Spam / Phishing",
        "Email Signature Issue","Account Locked","Other"],
    "VPN / Remote Access": [
        "Cannot Connect to VPN","Slow VPN","2FA Issue",
        "Remote Desktop Not Working","Other"],
    "Hardware": [
        "Monitor Issue","USB Not Working","Battery Issue",
        "Docking Station","Webcam Not Working","Other"],
    "File Access / Permissions": [
        "Cannot Access Folder","Permission Denied",
        "File Not Found","Shared Drive Issue","Other"],
    "Performance Issues": [
        "Computer Running Slow","High CPU Usage","Disk Full Warning",
        "App Running Slow","Overheating","Other"],
}

CATEGORIES_ORDER = [
    "Other","Computer / Workstation","Network / Internet / WiFi",
    "Printer","Scanner","Phone / VoIP","Browser",
    "Software / Application","Email","VPN / Remote Access",
    "Hardware","File Access / Permissions","Performance Issues",
]

MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".png",".jpg",".jpeg",".gif",".webp",".bmp",".pdf"}


class FlowLayout(QLayout):
    def __init__(self, parent=None, h_spacing=6, v_spacing=6):
        super().__init__(parent)
        self._h = h_spacing; self._v = v_spacing; self._items = []

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._layout(QRect(0, 0, w, 0), True)
    def setGeometry(self, rect): super().setGeometry(rect); self._layout(rect, False)

    def sizeHint(self):
        w = self.geometry().width()
        if w > 0:
            return QSize(w, self.heightForWidth(w))
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for i in self._items: s = s.expandedTo(i.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left()+m.right(), m.top()+m.bottom())

    def _layout(self, rect, test):
        m = self.contentsMargins()
        er = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, lh = er.x(), er.y(), 0
        for item in self._items:
            nx = x + item.sizeHint().width() + self._h
            if nx - self._h > er.right() and lh > 0:
                x = er.x(); y += lh + self._v
                nx = x + item.sizeHint().width() + self._h; lh = 0
            if not test: item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            x = nx; lh = max(lh, item.sizeHint().height())
        return y + lh - rect.y() + m.bottom()


class FlowWidget(QWidget):
    """QWidget that auto-updates its minimum height to match the FlowLayout's wrapped height."""
    def resizeEvent(self, event):
        super().resizeEvent(event)
        lay = self.layout()
        if lay and lay.hasHeightForWidth():
            h = lay.heightForWidth(event.size().width())
            self.setMinimumHeight(h)


def build_tray_icon() -> QIcon:
    px = QPixmap(32, 32)
    px.fill(Qt.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor("#2563EB")))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(0, 0, 32, 32, 6, 6)
    p.setPen(QPen(QColor("white")))
    p.setFont(QFont("Arial", 14, QFont.Weight.Bold))
    p.drawText(QRect(0, 0, 32, 32), Qt.AlignCenter, "IT")
    p.end()
    return QIcon(px)


class MainWindow(QMainWindow):
    def __init__(self, client_id: str, hostname: str, ip_address: str, sys_username: str):
        super().__init__()
        self._client_id    = client_id
        self._hostname     = hostname
        self._ip_address   = ip_address
        self._sys_username = sys_username

        self._selected_category:    Optional[str] = None
        self._selected_subcategory: Optional[str] = None
        self._category_buttons: dict = {}
        self._subcat_buttons:   dict = {}
        self._attachment_path:  Optional[str] = None
        self._close_hint_shown = False

        self._setup_window()
        self._setup_tray()
        self._build_ui()

    def _setup_window(self):
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(480, 580)
        self.resize(540, 720)
        # Allow all window buttons: min, max, close
        self.setWindowFlags(
            Qt.Window |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowMaximizeButtonHint |
            Qt.WindowCloseButtonHint
        )
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width()-540)//2, (screen.height()-720)//2)

    def _setup_tray(self):
        self._tray = QSystemTrayIcon(build_tray_icon(), self)
        self._tray.setToolTip(APP_NAME)
        self._tray_menu = QMenu()
        self._tray.setContextMenu(self._tray_menu)
        self._rebuild_tray_menu()
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _rebuild_tray_menu(self):
        self._tray_menu.clear()
        self._tray_menu.addAction("Open Helpdesk", self._show_window)
        self._tray_menu.addAction("Submit a Ticket", self._show_window)
        self._tray_menu.addSeparator()
        self._enable_act  = self._tray_menu.addAction("Enable auto-start",         self._enable_autostart)
        self._disable_act = self._tray_menu.addAction("Disable auto-start",        self._disable_autostart)
        self._tray_menu.addSeparator()
        self._tray_menu.addAction("Exit (Stop Notifications)", self._quit_app)
        self._update_autostart_menu()

    def _update_autostart_menu(self):
        enabled = self._is_autostart_enabled()
        self._enable_act.setVisible(not enabled)
        self._disable_act.setVisible(enabled)

    def _is_autostart_enabled(self) -> bool:
        import sys as _sys
        if _sys.platform == "darwin":
            from pathlib import Path
            return (Path.home() / "Library" / "LaunchAgents" / "com.mom.helpdesk.client.plist").exists()
        else:
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try: winreg.QueryValueEx(k, "MOMHelpdeskClient"); winreg.CloseKey(k); return True
                except FileNotFoundError: winreg.CloseKey(k); return False
            except Exception: return False

    def _enable_autostart(self):
        import sys as _sys
        if _sys.platform == "darwin":
            try:
                from pathlib import Path
                exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                (plist_dir / "com.mom.helpdesk.client.plist").write_text(
                    f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.mom.helpdesk.client</string>
    <key>ProgramArguments</key>
    <array><string>{exe}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>""", encoding="utf-8")
            except Exception: pass
        else:
            try:
                import winreg
                exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                winreg.SetValueEx(k, "MOMHelpdeskClient", 0, winreg.REG_SZ, exe)
                winreg.CloseKey(k)
            except Exception: pass
        self._update_autostart_menu()

    def _disable_autostart(self):
        import sys as _sys
        if _sys.platform == "darwin":
            try:
                from pathlib import Path
                plist = Path.home() / "Library" / "LaunchAgents" / "com.mom.helpdesk.client.plist"
                if plist.exists(): plist.unlink()
            except Exception: pass
        else:
            try:
                import winreg
                k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
                try: winreg.DeleteValue(k, "MOMHelpdeskClient")
                except FileNotFoundError: pass
                winreg.CloseKey(k)
            except Exception: pass
        self._update_autostart_menu()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self):
        self.showNormal(); self.raise_(); self.activateWindow()

    def _quit_app(self):
        QApplication.instance().quit()

    # ── Build UI ───────────────────────────────────────
    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget(); content.setObjectName("scrollContent")
        root = QVBoxLayout(content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        body = QWidget(); body.setObjectName("bodyWidget")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 18, 20, 14)
        bl.setSpacing(14)

        bl.addWidget(self._build_name_section())
        bl.addWidget(self._build_category_section())
        bl.addWidget(self._build_description_section())
        bl.addWidget(self._build_attachment_section())

        self._val_label = QLabel("Please select a category.")
        self._val_label.setObjectName("validationError")
        self._val_label.setVisible(False)
        bl.addWidget(self._val_label)

        self._submit_btn = QPushButton("Submit Ticket")
        self._submit_btn.setObjectName("submitBtn")
        self._submit_btn.setFixedHeight(44)
        self._submit_btn.clicked.connect(self._on_submit)
        bl.addWidget(self._submit_btn)

        self._confirm_widget = self._build_confirmation_widget()
        self._confirm_widget.setVisible(False)
        bl.addWidget(self._confirm_widget)

        bl.addStretch()
        bl.addWidget(self._build_footer())

        root.addWidget(body)
        scroll.setWidget(content)
        self.setCentralWidget(scroll)

    def _build_header(self):
        h = QWidget(); h.setObjectName("headerBar"); h.setFixedHeight(60)
        lay = QHBoxLayout(h); lay.setContentsMargins(18, 0, 18, 0)
        icon = QLabel("🎫"); icon.setObjectName("headerIcon")
        tw = QWidget()
        tl = QVBoxLayout(tw); tl.setContentsMargins(8,0,0,0); tl.setSpacing(0)
        l1 = QLabel("Medical Offices of Manhattan"); l1.setObjectName("headerLine1")
        l2 = QLabel("Tech Support"); l2.setObjectName("headerLine2")
        tl.addWidget(l1); tl.addWidget(l2)
        lay.addWidget(icon); lay.addWidget(tw); lay.addStretch()
        return h

    def _build_name_section(self):
        s = QWidget(); s.setObjectName("card")
        l = QVBoxLayout(s); l.setContentsMargins(14,12,14,12); l.setSpacing(6)
        l.addWidget(self._lbl("Your Name", "sectionLabel"))
        self._name_input = QLineEdit()
        self._name_input.setObjectName("textInput")
        self._name_input.setPlaceholderText("Enter your name (optional)")
        self._name_input.setFixedHeight(34)
        l.addWidget(self._name_input)
        return s

    def _lbl(self, text, obj): lb = QLabel(text); lb.setObjectName(obj); return lb

    def _build_category_section(self):
        s = QWidget(); s.setObjectName("card")
        l = QVBoxLayout(s); l.setContentsMargins(14,12,14,12); l.setSpacing(8)

        hr = QHBoxLayout()
        hr.addWidget(self._lbl("Select Category", "sectionLabel"))
        star = QLabel(" *"); star.setObjectName("requiredStar")
        hr.addWidget(star); hr.addStretch()
        l.addLayout(hr)

        grid = QGridLayout(); grid.setSpacing(7)
        other_btn = self._make_cat_btn("Other")
        grid.addWidget(other_btn, 0, 0, 1, 3)
        self._category_buttons["Other"] = other_btn

        rest = [c for c in CATEGORIES_ORDER if c != "Other"]
        for i, cat in enumerate(rest):
            btn = self._make_cat_btn(cat)
            grid.addWidget(btn, (i//3)+1, i%3)
            self._category_buttons[cat] = btn
        l.addLayout(grid)

        self._subcat_container = QWidget()
        sl = QVBoxLayout(self._subcat_container); sl.setContentsMargins(0,4,0,0); sl.setSpacing(5)
        div = QFrame(); div.setFrameShape(QFrame.Shape.HLine); div.setObjectName("divider")
        sl.addWidget(div)
        schr = QHBoxLayout()
        schr.addWidget(self._lbl("Sub-category", "subcatLabel"))
        schr.addWidget(self._lbl("(optional)", "optionalLabel"))
        schr.addStretch()
        sl.addLayout(schr)
        self._subcat_flow_widget = FlowWidget()
        self._subcat_flow_layout = FlowLayout(self._subcat_flow_widget, 6, 5)
        self._subcat_flow_widget.setLayout(self._subcat_flow_layout)
        sl.addWidget(self._subcat_flow_widget)
        self._subcat_container.setVisible(False)
        l.addWidget(self._subcat_container)
        return s

    def _make_cat_btn(self, text):
        btn = QPushButton(text)
        btn.setObjectName("categoryBtn")
        btn.setMinimumSize(90, 52)
        btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        btn.clicked.connect(lambda checked=False, t=text: self._on_category_selected(t))
        return btn

    def _on_category_selected(self, category: str):
        self._selected_category    = category
        self._selected_subcategory = None
        self._val_label.setVisible(False)
        for cat, btn in self._category_buttons.items():
            btn.setProperty("selected", cat == category)
            btn.style().unpolish(btn); btn.style().polish(btn)
        self._rebuild_subcats(category)
        self._subcat_container.setVisible(True)

    def _rebuild_subcats(self, category: str):
        for btn in list(self._subcat_buttons.values()):
            self._subcat_flow_layout.removeWidget(btn); btn.deleteLater()
        self._subcat_buttons.clear()
        for subcat in SUBCATEGORIES.get(category, []):
            btn = QPushButton(subcat)
            btn.setObjectName("subcatBtn")
            btn.setMinimumHeight(28)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked=False, s=subcat: self._on_subcat_selected(s))
            self._subcat_flow_layout.addWidget(btn)
            self._subcat_buttons[subcat] = btn
        self._subcat_flow_widget.updateGeometry()
        self._subcat_flow_widget.update()

    def _on_subcat_selected(self, subcat: str):
        self._selected_subcategory = subcat
        for s, btn in self._subcat_buttons.items():
            btn.setProperty("selected", s == subcat)
            btn.style().unpolish(btn); btn.style().polish(btn)

    def _build_description_section(self):
        s = QWidget(); s.setObjectName("card")
        l = QVBoxLayout(s); l.setContentsMargins(14,12,14,12); l.setSpacing(6)
        hr = QHBoxLayout()
        hr.addWidget(self._lbl("Description", "sectionLabel"))
        hr.addWidget(self._lbl("(optional)", "optionalLabel"))
        hr.addStretch()
        l.addLayout(hr)
        self._desc_input = QTextEdit()
        self._desc_input.setObjectName("descInput")
        self._desc_input.setFixedHeight(78)
        self._desc_input.setPlaceholderText("Briefly describe your issue…")
        l.addWidget(self._desc_input)
        return s

    def _build_attachment_section(self):
        s = QWidget(); s.setObjectName("card")
        l = QVBoxLayout(s); l.setContentsMargins(14,12,14,12); l.setSpacing(6)

        hr = QHBoxLayout()
        hr.addWidget(self._lbl("Attach Screenshot", "sectionLabel"))
        hr.addWidget(self._lbl("(optional, max 10 MB)", "optionalLabel"))
        hr.addStretch()
        l.addLayout(hr)

        row = QHBoxLayout(); row.setSpacing(8)
        self._attach_btn = QPushButton("📎  Choose File…")
        self._attach_btn.setObjectName("attachBtn")
        self._attach_btn.setFixedHeight(32)
        self._attach_btn.clicked.connect(self._choose_attachment)
        row.addWidget(self._attach_btn)

        self._clear_attach_btn = QPushButton("✕")
        self._clear_attach_btn.setObjectName("clearAttachBtn")
        self._clear_attach_btn.setFixedSize(32, 32)
        self._clear_attach_btn.setVisible(False)
        self._clear_attach_btn.clicked.connect(self._clear_attachment)
        row.addWidget(self._clear_attach_btn)
        row.addStretch()
        l.addLayout(row)

        self._attach_label = QLabel("No file selected")
        self._attach_label.setObjectName("attachLabel")
        l.addWidget(self._attach_label)

        if sys.platform == "darwin":
            hint_text = "💡 Tip: Press Cmd+Shift+4 to take a screenshot, then attach the file here."
        else:
            hint_text = "💡 Tip: Use Snipping Tool (Win+Shift+S) to take a screenshot, then save and attach it here."
        snip_hint = QLabel(hint_text)
        snip_hint.setObjectName("snipHint")
        snip_hint.setWordWrap(True)
        l.addWidget(snip_hint)
        return s

    def _choose_attachment(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Screenshot or File",
            os.path.expanduser("~"),
            "Images & PDF (*.png *.jpg *.jpeg *.gif *.webp *.bmp *.pdf)",
        )
        if not path:
            return
        size = os.path.getsize(path)
        if size > MAX_ATTACHMENT_SIZE:
            self._attach_label.setText("⚠ File too large (max 10 MB)")
            self._attach_label.setStyleSheet("color:#EF4444")
            return
        self._attachment_path = path
        filename = os.path.basename(path)
        self._attach_label.setText(f"📎 {filename}")
        self._attach_label.setStyleSheet("color:#065F46;font-weight:600")
        self._clear_attach_btn.setVisible(True)

    def _clear_attachment(self):
        self._attachment_path = None
        self._attach_label.setText("No file selected")
        self._attach_label.setStyleSheet("")
        self._clear_attach_btn.setVisible(False)

    def _build_confirmation_widget(self):
        w = QWidget(); w.setObjectName("confirmationCard")
        l = QVBoxLayout(w); l.setContentsMargins(14,14,14,14); l.setSpacing(7)
        self._confirm_check = QLabel("✓  Ticket submitted successfully!")
        self._confirm_check.setObjectName("confirmCheck")
        l.addWidget(self._confirm_check)
        self._confirm_id = QLabel("")
        self._confirm_id.setObjectName("confirmTicketId")
        l.addWidget(self._confirm_id)
        self._confirm_msg = QLabel("")
        self._confirm_msg.setObjectName("confirmMessage")
        self._confirm_msg.setWordWrap(True)
        l.addWidget(self._confirm_msg)
        another = QPushButton("Submit Another Ticket")
        another.setObjectName("anotherBtn")
        another.setFixedHeight(38)
        another.clicked.connect(self._reset_form)
        l.addWidget(another)
        return w

    def _build_footer(self):
        f = QWidget(); f.setObjectName("footer")
        l = QVBoxLayout(f); l.setContentsMargins(0,8,0,0); l.setSpacing(2)

        top_row = QHBoxLayout()
        self._pending_label = QLabel()
        self._pending_label.setObjectName("pendingLabel")
        self._pending_label.setVisible(False)
        top_row.addWidget(self._pending_label)
        top_row.addStretch()
        short = self._client_id[:8] + "…"
        cid = QLabel(f"Client ID: {short}")
        cid.setObjectName("clientIdLabel")
        top_row.addWidget(cid)
        l.addLayout(top_row)

        dev = QLabel("Developer: Sandesh Gurung")
        dev.setObjectName("devCredit")
        dev.setAlignment(Qt.AlignCenter)
        l.addWidget(dev)
        return f

    # ── Form logic ──────────────────────────────────────
    def _on_submit(self):
        if not self._selected_category:
            self._val_label.setVisible(True)
            return

        self._val_label.setVisible(False)
        self._submit_btn.setEnabled(False)
        self._submit_btn.setText("Submitting…")

        name = self._name_input.text().strip()
        payload = {
            "client_id":    self._client_id,
            "username":     name if name else self._sys_username,
            "ip_address":   self._ip_address,
            "hostname":     self._hostname,
            "category":     self._selected_category,
            "sub_category": self._selected_subcategory or "",
            "description":  self._desc_input.toPlainText().strip(),
        }

        result = api_client.submit_ticket(payload)

        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Submit Ticket")

        if result:
            tid = result.get("id", "Unknown")
            # Upload attachment if present
            if self._attachment_path:
                self._submit_btn.setText("Uploading…")
                self._submit_btn.setEnabled(False)
                upload_ok = api_client.upload_attachment(tid, self._attachment_path)
                self._submit_btn.setEnabled(True)
                self._submit_btn.setText("Submit Ticket")
                attach_note = " Screenshot attached." if upload_ok else " (Attachment upload failed.)"
            else:
                attach_note = ""

            self._confirm_check.setText("✓  Ticket submitted successfully!")
            self._confirm_check.setObjectName("confirmCheck")
            self._confirm_id.setText(f"Your Ticket ID: {tid}")
            self._confirm_msg.setText(
                f"We'll notify you when IT updates your ticket status.{attach_note}")
        else:
            self._confirm_check.setText("⚠  Ticket saved — will send when online")
            self._confirm_check.setObjectName("confirmCheckWarn")
            self._confirm_id.setText("")
            self._confirm_msg.setText(
                "No connection. Your ticket is saved locally and will be "
                "submitted automatically when the server is reachable.")
            self._update_pending_label(api_client.get_queue_size())

        self._submit_btn.setVisible(False)
        self._confirm_widget.setVisible(True)

    def _reset_form(self):
        self._name_input.clear()
        self._desc_input.clear()
        self._selected_category    = None
        self._selected_subcategory = None
        self._val_label.setVisible(False)
        self._clear_attachment()

        for btn in self._category_buttons.values():
            btn.setProperty("selected", False)
            btn.style().unpolish(btn); btn.style().polish(btn)

        for btn in list(self._subcat_buttons.values()):
            self._subcat_flow_layout.removeWidget(btn); btn.deleteLater()
        self._subcat_buttons.clear()
        self._subcat_container.setVisible(False)

        self._confirm_widget.setVisible(False)
        self._submit_btn.setVisible(True)
        self._submit_btn.setEnabled(True)
        self._submit_btn.setText("Submit Ticket")

    def _update_pending_label(self, count: int):
        if count > 0:
            self._pending_label.setText(f"⚠ {count} ticket(s) pending sync")
            self._pending_label.setVisible(True)
        else:
            self._pending_label.setVisible(False)

    # ── Notifications ────────────────────────────────────
    def show_tray_notification(self, ticket_id: str):
        self._tray.showMessage(
            "Ticket Resolved ✓",
            f"Your ticket {ticket_id} has been resolved by IT.",
            QSystemTrayIcon.MessageIcon.Information, 6000,
        )

    def show_inprogress_notification(self, ticket_id: str):
        self._tray.showMessage(
            "Ticket In Progress",
            f"IT Support is working on your ticket {ticket_id}.",
            QSystemTrayIcon.MessageIcon.Information, 6000,
        )

    def update_queue_display(self, count: int):
        self._update_pending_label(count)

    # ── Close: hide to tray, keep running ────────────────
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if not self._close_hint_shown:
            self._close_hint_shown = True
            if sys.platform == "darwin":
                tip = "Running in background. You'll be notified when your ticket status changes. Click the menu bar icon to reopen."
            else:
                tip = "Running in background. You'll be notified when your ticket status changes. Right-click the tray icon to reopen."
            self._tray.showMessage(APP_NAME, tip, QSystemTrayIcon.MessageIcon.Information, 4000)


# ── Global stylesheet ───────────────────────────────────
APP_STYLESHEET = """
QWidget {
    font-family: -apple-system, "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1E293B;
}
QWidget#scrollContent, QWidget#bodyWidget { background-color: #F8FAFC; }
QWidget#headerBar { background-color: #059669; }  /* Green for client app */
QLabel#headerLine1 { color:white; font-size:14px; font-weight:bold; }
QLabel#headerLine2 { color:rgba(255,255,255,.82); font-size:12px; }
QLabel#headerIcon  { font-size:22px; color:white; }

QWidget#card {
    background-color:#FFFFFF;
    border:1px solid #E2E8F0;
    border-radius:8px;
}
QLabel#sectionLabel  { font-weight:bold; font-size:13px; }
QLabel#requiredStar  { color:#EF4444; font-weight:bold; }
QLabel#optionalLabel { color:#94A3B8; font-size:12px; }
QLabel#subcatLabel   { font-weight:600; font-size:12px; color:#475569; }
QLabel#attachLabel   { font-size:12px; color:#64748B; }
QLabel#snipHint      { font-size:11px; color:#94A3B8; font-style:italic; margin-top:2px; }

QLineEdit#textInput {
    border:1px solid #E2E8F0; border-radius:8px;
    padding:4px 10px; background:#FFFFFF;
}
QLineEdit#textInput:focus { border-color:#2563EB; }

QTextEdit#descInput {
    border:1px solid #E2E8F0; border-radius:8px;
    padding:6px 10px; background:#FFFFFF;
}
QTextEdit#descInput:focus { border-color:#2563EB; }

QPushButton#categoryBtn {
    min-width:90px; min-height:52px; font-size:11px;
    border:1px solid #E2E8F0; border-radius:8px;
    background:#FFFFFF; padding:4px;
}
QPushButton#categoryBtn:hover { border-color:#2563EB; background:#F0F7FF; }
QPushButton#categoryBtn[selected="true"] {
    border:2px solid #2563EB; background:#EFF6FF;
    color:#1D4ED8; font-weight:bold;
}

QPushButton#subcatBtn {
    min-height:28px; font-size:11px;
    border:1px solid #E2E8F0; border-radius:14px;
    background:#FFFFFF; color:#475569; padding:3px 10px;
}
QPushButton#subcatBtn:hover { border-color:#F59E0B; background:#FFFDF0; }
QPushButton#subcatBtn[selected="true"] {
    border:2px solid #F59E0B; background:#FFFBEB;
    color:#92400E; font-weight:bold;
}

QPushButton#submitBtn {
    background:#059669; color:white; border:none;
    border-radius:8px; font-size:14px; font-weight:bold;
}
QPushButton#submitBtn:hover    { background:#047857; }
QPushButton#submitBtn:disabled { background:#6EE7B7; }

QPushButton#attachBtn {
    background:#F8FAFC; border:1px solid #E2E8F0;
    border-radius:7px; font-size:12px; color:#475569; padding:0 10px;
}
QPushButton#attachBtn:hover { background:#EFF6FF; border-color:#2563EB; }

QPushButton#clearAttachBtn {
    background:#FEF2F2; border:1px solid #FECACA;
    border-radius:7px; font-size:13px; color:#B91C1C;
}
QPushButton#clearAttachBtn:hover { background:#FEE2E2; }

QLabel#validationError { color:#EF4444; font-size:12px; }

QWidget#confirmationCard {
    background:#F0FFF4; border:1px solid #10B981; border-radius:8px;
}
QLabel#confirmCheck     { color:#065F46; font-size:14px; font-weight:bold; }
QLabel#confirmCheckWarn { color:#92400E; font-size:13px; font-weight:bold; }
QLabel#confirmTicketId  { color:#1E293B; font-weight:600; }
QLabel#confirmMessage   { color:#374151; font-size:12px; }

QPushButton#anotherBtn {
    background:#FFFFFF; color:#2563EB;
    border:1px solid #2563EB; border-radius:8px; font-size:13px;
}
QPushButton#anotherBtn:hover { background:#EFF6FF; }

QFrame#divider { border:none; border-top:1px solid #E2E8F0; }
QLabel#pendingLabel  { color:#B45309; font-size:11px; }
QLabel#clientIdLabel { color:#CBD5E1; font-size:10px; }
QLabel#devCredit     { color:#CBD5E1; font-size:10px; }

QScrollArea { background:transparent; border:none; }
QScrollBar:vertical {
    border:none; background:#F1F5F9; width:7px; border-radius:4px;
}
QScrollBar::handle:vertical { background:#CBD5E1; border-radius:4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
"""
