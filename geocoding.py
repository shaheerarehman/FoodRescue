from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class Coordinates:
    latitude: str
    longitude: str
    approximate: bool = False


class GeocodingUnavailable(Exception):
    """The lookup can be retried later."""


class GeocodingProvider(Protocol):
    def geocode(self, address: str) -> Optional[Coordinates]:
        """Return coordinates, or None if the address has no match."""
        ...
