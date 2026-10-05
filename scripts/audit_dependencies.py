"""Read public PyPI vulnerability metadata for the installed locked versions."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def check(line):
    name, version = line.split("==", 1)
    try:
        with urlopen(f"https://pypi.org/pypi/{quote(name)}/{quote(version)}/json", timeout=15) as r:
            payload = json.load(r)
        issues = [
            {
                "id": v["id"],
                "aliases": v.get("aliases", []),
                "fixed_in": v.get("fixed_in", []),
                "link": v.get("link", ""),
            }
            for v in payload.get("vulnerabilities", [])
            if not v.get("withdrawn")
        ]
        return {"package": name, "version": version, "vulnerabilities": issues}
    except Exception as exc:
        return {"package": name, "version": version, "error": type(exc).__name__}


if __name__ == "__main__":
    lines = [
        line.strip()
        for line in (ROOT / "requirements/lock.txt").read_text(encoding="utf-8").splitlines()
        if "==" in line
    ]
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(check, lines))
    (ROOT / "artifacts/dependency-audit.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    affected = [r for r in results if r.get("vulnerabilities")]
    failed = [r for r in results if r.get("error")]
    print(json.dumps({"checked": len(results), "affected": affected, "unavailable": failed}))
    sys.exit(1 if affected or failed else 0)
