"""Extract directory rows and report unresolved SEC/LSGD crosswalks (no fuzzy auto-matches)."""

import difflib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "location-sources"


def rows(path):
    content = path.read_text(encoding="utf-8")
    result = []
    for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", content, re.S | re.I):
        cells = [
            html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
        ]
        result.append([" ".join(cell.split()) for cell in cells])
    return result


def normal(name):
    name = re.sub(r" (Grama|Block) Panchayat$", "", name, flags=re.I)
    return re.sub("[^a-z]", "", name.lower())


def main():
    sec, lsg = [], {}
    for district in range(1, 15):
        for kind in ["G", "B"]:
            for row in rows(ROOT / f"sec-{district:02d}-{kind}.html"):
                if len(row) >= 3 and re.fullmatch(kind + r"\d{5}", row[1]):
                    sec.append({"district": district, "code": row[1], "name": row[2], "kind": kind})
        for file in ROOT.glob(f"lsg-{district:02d}-*.html"):
            for row in rows(file):
                if len(row) >= 3 and re.fullmatch(r"[GB]\d{6}", row[2]):
                    lsg[row[2]] = {
                        "district": district,
                        "code": row[2],
                        "name": re.sub(r" (Grama|Block) Panchayat$", "", row[1], flags=re.I),
                        "kind": row[2][0],
                    }
    (ROOT / "parsed.json").write_text(
        json.dumps({"sec": sec, "lsg": list(lsg.values())}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    unmatched = []
    for row in sec:
        candidates = [
            x for x in lsg.values() if x["district"] == row["district"] and x["kind"] == row["kind"]
        ]
        exact = [x for x in candidates if normal(x["name"]) == normal(row["name"])]
        if len(exact) != 1:
            best = sorted(
                candidates,
                key=lambda x: difflib.SequenceMatcher(
                    None, normal(row["name"]), normal(x["name"])
                ).ratio(),
                reverse=True,
            )[:2]
            unmatched.append({"sec": row, "suggestions": best})
    (ROOT / "unmatched.json").write_text(
        json.dumps(unmatched, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SEC", len(sec), "LSGD", len(lsg), "unmatched", len(unmatched))
    for row in unmatched:
        print(
            row["sec"]["code"],
            row["sec"]["name"],
            "=>",
            " | ".join(x["code"] + " " + x["name"] for x in row["suggestions"]),
        )


if __name__ == "__main__":
    main()
