"""Download public SEC and LSGD directory snapshots for reviewed dataset preparation."""

import concurrent.futures
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "location-sources"
ROOT.mkdir(parents=True, exist_ok=True)


def fetch(url, filename):
    path = ROOT / filename
    if not path.exists():
        for attempt in range(3):
            try:
                with urlopen(
                    Request(url, headers={"User-Agent": "GMFMS location-master preparation"}),
                    timeout=40,
                ) as response:
                    data = response.read()
                path.write_bytes(data)
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2)
    data = path.read_bytes()
    return {"url": url, "file": filename, "sha256": hashlib.sha256(data).hexdigest()}


def main():
    index = fetch("https://sec.kerala.gov.in/public/cnstncy", "sec-index.html")
    html = (ROOT / index["file"]).read_text(encoding="utf-8")
    links = list(dict.fromkeys(re.findall(r'href="(/public/cnstncy/lb/[^"]+/[GB])"', html)))
    assert len(links) == 28, len(links)
    tasks = [
        (urljoin(index["url"], link), f"sec-{i // 2 + 1:02d}-{link[-1]}.html")
        for i, link in enumerate(links)
    ]
    # Read the official directory's own district filter and pagination links.
    tasks += [
        (f"https://lsgkerala.gov.in/en/website/input/{district}/0", f"lsg-{district:02d}-0.html")
        for district in range(1, 15)
    ]
    manifest = [index]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for entry in pool.map(lambda item: fetch(*item), tasks):
            manifest.append(entry)
            print(entry["file"], flush=True)
    tasks = []
    for district in range(1, 15):
        html = (ROOT / f"lsg-{district:02d}-0.html").read_text(encoding="utf-8")
        pages = set(re.findall(r'href="(\?page=[^"]+)"', html))
        for page in sorted(pages):
            if page.endswith("0"):
                continue
            number = re.search(r"(\d+)$", page).group(1)
            tasks.append(
                (
                    f"https://lsgkerala.gov.in/en/website/input/{district}/0{page}",
                    f"lsg-{district:02d}-{number}.html",
                )
            )
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for entry in pool.map(lambda item: fetch(*item), tasks):
            manifest.append(entry)
            print(entry["file"], flush=True)
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Downloaded {len(manifest)} public source pages.")


if __name__ == "__main__":
    main()
