"""
Alert delivery seam.

Part 1 ships only the abstract `Notifier` and a `ConsoleNotifier` that prints.
Part 2 will add a `TwilioNotifier` (SMS + WhatsApp) behind this same interface —
nothing about advice/alert generation changes when it lands.
"""

from abc import ABC, abstractmethod
from typing import List

from .alerts import Alert
from .render import render_alert


class Notifier(ABC):
    @abstractmethod
    def send(self, alerts: List[Alert]) -> int:
        """Deliver the alerts. Returns how many were sent."""
        ...


class ConsoleNotifier(Notifier):
    """Print alerts to stdout — the default until Part-2 delivery is wired.

    Args:
        min_severity: only emit alerts at/above this severity
            ("urgent" > "alert" > "watch" > "info").
    """

    _ORDER = {"info": 0, "watch": 1, "alert": 2, "urgent": 3}

    def __init__(self, min_severity: str = "info"):
        self.min_rank = self._ORDER.get(min_severity, 0)

    def send(self, alerts: List[Alert]) -> int:
        sent = 0
        for a in alerts:
            if self._ORDER.get(a.severity, 0) < self.min_rank:
                continue
            print(render_alert(a))
            print("-" * 40)
            sent += 1
        if sent == 0:
            print("[advisory] no alerts to deliver")
        return sent
