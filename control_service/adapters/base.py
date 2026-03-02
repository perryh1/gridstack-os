"""Abstract base classes for hardware adapters."""

from abc import ABC, abstractmethod
from ..models import MinerStatus, BESSStatus


class MinerAdapter(ABC):
    """Interface for controlling Bitcoin mining hardware."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection. Returns True if successful."""
        ...

    @abstractmethod
    async def get_status(self) -> MinerStatus:
        """Read current miner fleet status."""
        ...

    @abstractmethod
    async def set_power_mode(self, mode: str) -> bool:
        """Set miner power mode ('high', 'low', 'sleep'). Returns True if acknowledged."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Returns True if the adapter can reach the hardware."""
        ...


class BESSAdapter(ABC):
    """Interface for controlling battery energy storage."""

    @abstractmethod
    async def connect(self) -> bool:
        ...

    @abstractmethod
    async def get_status(self) -> BESSStatus:
        ...

    @abstractmethod
    async def set_charge(self, power_mw: float) -> bool:
        """Command BESS to charge at given rate (MW). 0 = stop."""
        ...

    @abstractmethod
    async def set_discharge(self, power_mw: float) -> bool:
        """Command BESS to discharge at given rate (MW). 0 = stop."""
        ...

    @abstractmethod
    async def set_idle(self) -> bool:
        """Stop all charge/discharge."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        ...
