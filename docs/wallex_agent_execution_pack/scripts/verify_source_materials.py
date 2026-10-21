#!/usr/bin/env python3
"""Verify bundled Wallex source copies and the derived inactive-market list; performs no network calls."""
from __future__ import annotations
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORIG = ROOT / "source_materials" / "originals"
DERIVED = ROOT / "source_materials" / "derived"
FILES = ["assets.md", "intro-text.md", "task.md", "هکاتون استارکوچ _ والکس.pdf"]

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main() -> int:
    errors: list[str] = []
    expected_hashes: dict[str, str] = {}
    lines = (DERIVED / "SOURCE_SHA256.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        if line and not line.startswith("#"):
            digest, rel = line.split("  ", 1)
            expected_hashes[Path(rel).name] = digest
    for name in FILES:
        p = ORIG / name
        if not p.exists():
            errors.append(f"Missing source: {p.relative_to(ROOT)}")
        elif expected_hashes.get(name) != sha256(p):
            errors.append(f"SHA-256 mismatch: {p.relative_to(ROOT)}")
    assets = (ORIG / "assets.md").read_text(encoding="utf-8-sig")
    raw_markets = [line.strip() for line in assets.splitlines() if re.fullmatch(r"[A-Z0-9]+/(?:TMN|USDT)", line.strip())]
    data = json.loads((DERIVED / "inactive_markets.json").read_text(encoding="utf-8"))
    if raw_markets != data.get("inactive_markets"):
        errors.append("Derived inactive market list differs from source order/content")
    if len(raw_markets) != data.get("source_pair_line_count"):
        errors.append("Source pair line count mismatch")
    if len(set(raw_markets)) != data.get("unique_inactive_market_count"):
        errors.append("Unique pair count mismatch")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"OK: {len(FILES)} original sources verified; {len(raw_markets)} inactive pairs / {len(set(raw_markets))} unique pairs; no network calls made.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
