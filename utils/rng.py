"""Deterministic, process-stable random number generation.

Why this module exists
----------------------
The original `backtest/baselines.random_entry` derived its per-ticker seed as::

    rng = np.random.default_rng(seed + abs(hash(tuple(df.index[:1].astype(str)))) % 10_000)

`hash()` on a `str` is salted per interpreter process (PEP 456 / PYTHONHASHSEED),
so this produced a *different* random baseline on every run. Because the
random-entry baseline is the comparator behind every `significant_vs_baseline`
flag in the published results, the headline significance counts could not be
reproduced -- rerunning the pipeline silently changed which concepts were
called significant.

`derive_seed` replaces it with BLAKE2b over the UTF-8 label, which is stable
across processes, machines, Python versions and platforms.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from utils.config import RANDOM_SEED, RESULTS_DIR

_SEED_SPACE = 2**32


def derive_seed(label: str, master_seed: int = RANDOM_SEED) -> int:
    """Return a stable child seed for `label`, derived from `master_seed`.

    Deterministic across processes -- unlike `hash()`, which is salted.

    >>> derive_seed("AAPL") == derive_seed("AAPL")
    True
    """
    payload = f"{master_seed}:{label}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") % _SEED_SPACE


def get_rng(label: str, master_seed: int = RANDOM_SEED) -> np.random.Generator:
    """A NumPy Generator seeded stably from `label`."""
    return np.random.default_rng(derive_seed(label, master_seed))


def write_seed_manifest(extra: dict | None = None, path: Path | None = None) -> Path:
    """Persist the master seed and the derived child seeds actually used, so a
    reader can verify a rerun reproduced the same draws."""
    path = path or (RESULTS_DIR / "seed.txt")
    manifest = {
        "master_seed": RANDOM_SEED,
        "derivation": "blake2b(f'{master_seed}:{label}', digest_size=8) % 2**32",
        "note": (
            "Stable across processes and platforms. Does NOT use Python's "
            "salted hash(); see utils/rng.py for the rationale."
        ),
    }
    if extra:
        manifest.update(extra)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return path
