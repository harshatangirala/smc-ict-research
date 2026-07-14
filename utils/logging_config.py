"""Shared logging configuration for the research pipeline."""

from __future__ import annotations

import logging
import sys

from utils.config import LOGS_DIR

_CONFIGURED = False


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a module-level logger with a console + rotating-file handler.

    Configuration is applied once per process (idempotent across repeated
    calls) so importing this in many modules does not create duplicate
    handlers / duplicated log lines.
    """
    global _CONFIGURED
    root = logging.getLogger("smc_ict")
    if not _CONFIGURED:
        root.setLevel(level)
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        root.addHandler(console)

        file_handler = logging.FileHandler(LOGS_DIR / "pipeline.log", encoding="utf-8")
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)

        root.propagate = False
        _CONFIGURED = True

    return logging.getLogger(f"smc_ict.{name}")
