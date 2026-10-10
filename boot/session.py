from datetime import datetime


class SessionManager:
    def __init__(self):
        self.state = "stopped"
        self.started_at: datetime | None = None
        self.sleep_count = 0
        self.resume_count = 0

    def start(self) -> None:
        self.state = "running"
        self.started_at = datetime.now()

    def begin_sleep(self) -> None:
        self.state = "sleeping"
        self.sleep_count += 1

    def resume(self) -> None:
        self.state = "running"
        self.resume_count += 1

    def sleep_failed(self) -> None:
        if self.state == "sleeping":
            self.state = "running"

    def begin_shutdown(self) -> None:
        self.state = "shutting down"


SESSION_MANAGER = SessionManager()