"""Build results/replication_package.zip and results/ssrn_submission_bundle.zip.

The replication package is what a reader needs to rerun the study: source, specs,
guide, seeds and manifests. The submission bundle is what a reader needs to
*evaluate* it without rerunning: the manuscript, the guide, the key tables and
the figures.

Both are built from files on disk, and every included path is listed in a
MANIFEST.txt inside the archive with its size and SHA-256, so a reader can
verify they received what was intended.
"""

from __future__ import annotations

import hashlib
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.config import RESULTS_DIR  # noqa: E402

# --- what goes in the full replication package -----------------------------
CODE_DIRS = ["analytics", "backtest", "pine_parser", "signals", "utils", "tests", "tools"]
CODE_FILES = [
    "main.py", "requirements.txt", "requirements-ci.txt", "environment.yml",
    "Dockerfile", "docker-entrypoint.sh", "run_full_pipeline.sh",
    "run_fast_validation.sh", "README.md", "CHANGES.md", "LICENSE",
]
DOC_GLOBS = ["docs/*.md", "docs/specs/*.yaml", ".github/workflows/*.yml"]
DATA_FILES = ["data/raw/sp500_constituents.csv"]

# --- what goes in the SSRN submission bundle -------------------------------
BUNDLE_DOCS = [
    "docs/manuscript.md", "docs/manuscript.pdf",
    "docs/replication_guide.md", "CHANGES.md",
]
BUNDLE_RESULT_GLOBS = [
    "statistics_master.csv", "master_summary.md", "validation_report.md",
    "reviewer_report.md", "concept_rankings.csv",
    "concept_rankings_all_horizons.csv", "combination_rankings.csv",
    "stock_rankings.csv", "sector_analysis.csv", "regime_analysis.csv",
    "walkforward_summary.csv", "walkforward_detail.csv",
    "breakeven_costs.csv", "net_of_cost_rankings.csv",
    "cost_sensitivity_grid.csv", "monte_carlo.csv",
    "sensitivity_grid.csv", "sensitivity_stability.csv",
    "data_quality_report.csv", "run_manifest.json", "seed.txt",
]


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _add(zf: zipfile.ZipFile, src: Path, arc: str, manifest: list[str]) -> None:
    if not src.exists() or not src.is_file():
        return
    zf.write(src, arc)
    manifest.append(f"{_sha256(src)}  {src.stat().st_size:>12,}  {arc}")


def _write_manifest(zf: zipfile.ZipFile, manifest: list[str], title: str) -> None:
    header = [
        title, "=" * len(title), "",
        f"Built {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        f"{len(manifest)} files", "",
        "SHA-256                                                           "
        "        bytes  path",
        "-" * 100,
    ]
    zf.writestr("MANIFEST.txt", "\n".join(header + sorted(manifest, key=lambda s: s.split("  ")[-1])) + "\n")


def build_replication_package(out: Path | None = None) -> Path:
    out = out or (RESULTS_DIR / "replication_package.zip")
    manifest: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for d in CODE_DIRS:
            for p in sorted((ROOT / d).rglob("*.py")):
                if "__pycache__" in p.parts:
                    continue
                _add(zf, p, str(p.relative_to(ROOT)).replace("\\", "/"), manifest)
        for f in CODE_FILES:
            _add(zf, ROOT / f, f, manifest)
        for g in DOC_GLOBS:
            for p in sorted(ROOT.glob(g)):
                _add(zf, p, str(p.relative_to(ROOT)).replace("\\", "/"), manifest)
        for f in DATA_FILES:
            _add(zf, ROOT / f, f, manifest)
        # The committed sample cache makes the fast path work offline.
        for p in sorted((ROOT / "data" / "bundle" / "prices").glob("*.parquet"))[:50]:
            _add(zf, p, str(p.relative_to(ROOT)).replace("\\", "/"), manifest)
        for name in BUNDLE_RESULT_GLOBS:
            _add(zf, RESULTS_DIR / name, f"results/{name}", manifest)
        _write_manifest(zf, manifest, "SMC/ICT Replication Package")
    print(f"Wrote {out}  ({out.stat().st_size / 1e6:.2f} MB, {len(manifest)} files)")
    return out


def build_submission_bundle(out: Path | None = None) -> Path:
    out = out or (RESULTS_DIR / "ssrn_submission_bundle.zip")
    manifest: list[str] = []
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in BUNDLE_DOCS:
            _add(zf, ROOT / f, f, manifest)
        for name in BUNDLE_RESULT_GLOBS:
            _add(zf, RESULTS_DIR / name, f"results/{name}", manifest)
        for p in sorted((RESULTS_DIR / "figures").glob("*")):
            _add(zf, p, f"results/figures/{p.name}", manifest)
        for p in sorted((ROOT / "docs" / "specs").glob("*.yaml")):
            _add(zf, p, f"docs/specs/{p.name}", manifest)
        rp = RESULTS_DIR / "replication_package.zip"
        _add(zf, rp, "replication_package.zip", manifest)
        _write_manifest(zf, manifest, "SMC/ICT SSRN Submission Bundle")
    print(f"Wrote {out}  ({out.stat().st_size / 1e6:.2f} MB, {len(manifest)} files)")
    return out


def main() -> int:
    build_replication_package()
    build_submission_bundle()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
