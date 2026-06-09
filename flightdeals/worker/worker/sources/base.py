"""Source adapter interface.

RULE (handover §5): never scrape consumer flight sites from this box.
Adapters call flight DATA APIs server-to-server only.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import FareSnapshot


class FareSource(ABC):
    name: str = "base"

    @abstractmethod
    def sweep(self, origin: str, destination: str) -> list[FareSnapshot]:
        """Return cheapest cached fares for a route over the sweep horizon."""
        raise NotImplementedError
