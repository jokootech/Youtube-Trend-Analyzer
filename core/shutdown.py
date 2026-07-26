"""Cross-platform graceful shutdown coordinator for asyncio loops."""

from __future__ import annotations

import asyncio
import signal
from loguru import logger


class ShutdownCoordinator:
    """Handles SIGINT/SIGTERM signals and provides a thread-safe shutdown event."""

    def __init__(self) -> None:
        self._shutdown_event = asyncio.Event()

    def _signal_handler(self, sig: signal.Signals) -> None:
        logger.warning("Received termination signal {name} — initiating shutdown", name=sig.name)
        self._shutdown_event.set()

    def install(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register signal handlers safely across Linux/macOS/Windows environments."""
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._signal_handler, sig)
            except NotImplementedError:
                # Windows event loop fallback
                signal.signal(sig, lambda *_: self._signal_handler(sig))

    @property
    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()

    async def wait(self) -> None:
        """Await until a shutdown signal is raised."""
        await self._shutdown_event.wait()