"""Worker entry-point — runs all background loops side-by-side."""

from __future__ import annotations

import asyncio
import signal
import sys
from typing import Coroutine

from awaaz_api.observability import configure_logging, get_logger, setup_telemetry
from awaaz_api.workers.analytics_rollup import run as analytics_loop
from awaaz_api.workers.billing_rollup import run as billing_loop
from awaaz_api.workers.gdpr_worker import run as gdpr_loop
from awaaz_api.workers.retry_worker import run as retry_loop
from awaaz_api.workers.wa_event_worker import run as wa_event_loop


async def _run() -> None:
    log = get_logger("awaaz.worker")
    log.info("worker.startup")

    stop = asyncio.Event()

    def _request_stop(*_args: object) -> None:
        log.info("worker.shutdown.signal")
        stop.set()

    loop = asyncio.get_event_loop()
    if sys.platform != "win32":  # SIGTERM unsupported on Windows event loop
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _request_stop)

    coros: list[Coroutine[object, object, object]] = [
        wa_event_loop(stop),
        retry_loop(stop),
        gdpr_loop(stop),
        analytics_loop(stop),
        billing_loop(stop),
    ]
    tasks = [asyncio.create_task(c) for c in coros]
    await stop.wait()
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    log.info("worker.shutdown.done")


def main() -> None:
    configure_logging()
    setup_telemetry()
    asyncio.run(_run())


if __name__ == "__main__":  # pragma: no cover
    main()
