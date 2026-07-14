from pathlib import Path

from utils.config import DATA_CACHE_DIR
from utils.data_loader import load_constituents

if __name__ == "__main__":
    c = load_constituents()
    have = {p.stem for p in Path(DATA_CACHE_DIR).glob("*.parquet")}
    want = set(c["YFSymbol"])
    print("missing:", sorted(want - have))
