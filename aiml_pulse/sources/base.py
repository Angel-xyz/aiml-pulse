"""Base class shared by every source adapter."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from aiml_pulse.models import Item, SourceName


class BaseSource(ABC):
    name: SourceName

    @abstractmethod
    def fetch(self, since: date | datetime) -> list[Item]:
        """Return items published on or after 'since'. May be empty."""
        raise NotImplementedError


__all__ = ["BaseSource"]