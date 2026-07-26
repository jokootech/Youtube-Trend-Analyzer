"""YouTube Trend Analyzer — Async entry point with graceful shutdown & resource cleanup."""

from __future__ import annotations

import asyncio
import gc
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# Ensure project root is on sys.path for direct python execution
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config.settings import RunMode, get_settings
from core.cli import parse_cli_args
from core.logger import setup_logging
from core.shutdown import ShutdownCoordinator
from processors.trend_analyst import TrendAnalyst


async def _run_scheduled(analyst: TrendAnalyst, coordinator: ShutdownCoordinator) -> None:
    """Run the pipeline on a fixed interval loop until a shutdown signal is caught."""
    settings = get_settings()
    interval_seconds = settings.poll_interval_minutes * 60

    while not coordinator.is_shutting_down:
        try:
            results = await analyst.run_once()
            if results:
                logger.info("Scheduled pipeline produced {n} analysis results", n=len(results))
            else:
                logger.info("Scheduled pipeline completed with zero new results")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Unhandled error during pipeline iteration: {error!r}", error=exc)

        # Wait for the next polling interval or shut down immediately on signal
        try:
            await asyncio.wait_for(coordinator.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass  # Normal timeout — loop to execute next cycle


async def _run_once(analyst: TrendAnalyst) -> None:
    """Execute a single pipeline run."""
    try:
        results = await analyst.run_once()
        logger.info("Single run execution finished processed={n}", n=len(results))
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error("Single run failed with exception: {error!r}", error=exc)
        raise


async def async_main() -> None:
    """Top-level async orchestrator."""
    args = parse_cli_args()
    settings = get_settings()

    if args.mode:
        settings.run_mode = RunMode(args.mode)

    setup_logging(log_level=settings.log_level.value)

    logger.info(
        "YouTube Trend Analyzer initializing mode={mode} provider={llm} model={model}",
        mode=settings.run_mode.value,
        llm=settings.llm_provider.value,
        model=settings.active_llm_model,
    )

    loop = asyncio.get_running_loop()
    coordinator = ShutdownCoordinator()

    # In Windows, signal handlers can throw NotImplementedError; wrapped safely
    try:
        coordinator.install(loop)
    except (NotImplementedError, AttributeError):
        pass

    analyst = TrendAnalyst(settings)
    await analyst.startup()

    # استفاده مستقیم از ناتیفایر داخلی analyst برای جلوگیری از ساخت نمونه جدید و Session اضافه
    try:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        await analyst._notifier.send_text(
            f"✅ <b>Trend Analyzer Bot Online</b>\n"
            f"Mode: <code>{settings.run_mode.value}</code>\n"
            f"LLM: <code>{settings.llm_provider.value}/{settings.active_llm_model}</code>\n"
            f"Started: <code>{ts}</code>"
        )
    except Exception as exc:
        logger.warning("Failed to dispatch startup notification: {error!r}", error=exc)

    try:
        if settings.run_mode == RunMode.ONCE:
            await _run_once(analyst)
        else:
            await _run_scheduled(analyst, coordinator)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.warning("Keyboard interrupt received — triggering immediate task cleanup...")
    finally:
        logger.info("Shutting down TrendAnalyst resources safely...")
        await analyst.shutdown()
        
        # وقفه کوتاه‌مدت برای پاک‌سازی کانکشن‌های زیرین شبکه توسط asyncio
        await asyncio.sleep(0.25)


def main() -> None:
    """Synchronous entry point with OS-level hard kill on KeyboardInterrupt."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Program execution stopped immediately by user (KeyboardInterrupt)")
        os._exit(0)
    except Exception as exc:
        logger.critical("Fatal application launch error: {error!r}", error=exc)
        sys.exit(1)
    finally:
        # پاک‌سازی حافظه برای جمع‌آوری ارجاعات مانده‌ی HTTP Client
        gc.collect()


if __name__ == "__main__":
    main()