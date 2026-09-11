from abc import ABC, abstractmethod
from typing import Any


class BaseUseCase(ABC):
    @abstractmethod
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the use case. Must be implemented by subclasses."""
        ...
