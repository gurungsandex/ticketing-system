from PySide6.QtCore import QObject, QThread, QTimer, Signal

import api_client


class NotifierWorker(QObject):
    ticket_resolved    = Signal(str)   # ticket_id
    ticket_in_progress = Signal(str)   # ticket_id
    queue_size_changed = Signal(int)

    def __init__(self, client_id: str, poll_interval_ms: int, queue_retry_ms: int):
        super().__init__()
        self._client_id = client_id
        self._poll_interval_ms = poll_interval_ms
        self._queue_retry_ms = queue_retry_ms
        self._last_known: dict = {}   # ticket_id -> status string
        self._poll_timer: QTimer = None
        self._queue_timer: QTimer = None

    def start_timers(self):
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(self._poll_interval_ms)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()

        self._queue_timer = QTimer()
        self._queue_timer.setInterval(self._queue_retry_ms)
        self._queue_timer.timeout.connect(self._flush_queue)
        self._queue_timer.start()

        # Run once immediately on startup
        self._poll()
        self._flush_queue()

    def _poll(self):
        notifications = api_client.get_notifications(self._client_id)
        for item in notifications:
            ticket_id  = item.get("id")
            new_status = item.get("status")
            old_status = self._last_known.get(ticket_id)

            if old_status is not None and old_status != new_status:
                # Notify when ticket moves TO in_progress
                if new_status == "in_progress":
                    self.ticket_in_progress.emit(ticket_id)
                # Notify when ticket moves TO resolved
                elif new_status == "resolved":
                    self.ticket_resolved.emit(ticket_id)

            self._last_known[ticket_id] = new_status

    def _flush_queue(self):
        api_client.flush_offline_queue()
        self.queue_size_changed.emit(api_client.get_queue_size())


class Notifier:
    def __init__(self, client_id: str, poll_interval_ms: int, queue_retry_ms: int):
        self._thread = QThread()
        self._worker = NotifierWorker(client_id, poll_interval_ms, queue_retry_ms)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start_timers)

    @property
    def ticket_resolved(self):
        return self._worker.ticket_resolved

    @property
    def ticket_in_progress(self):
        return self._worker.ticket_in_progress

    @property
    def queue_size_changed(self):
        return self._worker.queue_size_changed

    def start(self):
        self._thread.start()

    def stop(self):
        self._thread.quit()
        self._thread.wait()
