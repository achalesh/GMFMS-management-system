import csv
import hashlib
import json
import re
from pathlib import Path

from parse_location_sources import normal

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "kerala"
SOURCE = ROOT / "artifacts" / "location-sources"
DISTRICTS = [
    ("TVM", "Thiruvananthapuram", "തിരുവനന്തപുരം"),
    ("KLM", "Kollam", "കൊല്ലം"),
    ("PTA", "Pathanamthitta", "പത്തനംതിട്ട"),
    ("ALP", "Alappuzha", "ആലപ്പുഴ"),
    ("KTM", "Kottayam", "കോട്ടയം"),
    ("IDK", "Idukki", "ഇടുക്കി"),
    ("EKM", "Ernakulam", "എറണാകുളം"),
    ("TSR", "Thrissur", "തൃശ്ശൂർ"),
    ("PKD", "Palakkad", "പാലക്കാട്"),
    ("MLP", "Malappuram", "മലപ്പുറം"),
    ("KKD", "Kozhikode", "കോഴിക്കോട്"),
    ("WYD", "Wayanad", "വയനാട്"),
    ("KNR", "Kannur", "കണ്ണൂർ"),
    ("KSD", "Kasaragod", "കാസർഗോഡ്"),
]


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    parsed = json.loads((SOURCE / "parsed.json").read_text(encoding="utf-8"))
    aliases = json.loads((DATA / "sec_lsg_crosswalk.json").read_text(encoding="utf-8"))
    lsg = {row["code"]: row for row in parsed["lsg"]}
    spelling = json.loads((DATA / "hierarchy_spelling_aliases.json").read_text())
    matched = {}
    for row in parsed["sec"]:
        code = aliases.get(row["code"])
        if not code:
            candidates = [
                x
                for x in lsg.values()
                if x["district"] == row["district"]
                and x["kind"] == row["kind"]
                and normal(x["name"]) == normal(row["name"])
            ]
            assert len(candidates) == 1, row
            code = candidates[0]["code"]
        assert code not in matched, (code, row)
        assert lsg[code]["district"] == row["district"]
        matched[code] = row
    assert len(matched) == 1093

    # Explicit hierarchy reference: parse the printed columns, not name similarity.
    hierarchy = {}
    pending = None
    for line in (SOURCE / "hierarchy.txt").read_text(encoding="utf-8").splitlines():
        cells = re.split(r"\s{2,}", line.strip())
        if len(cells) == 2 and cells[0].isdigit():
            pending = cells
            continue
        if len(cells) == 4 and cells[1] == "Grama Panchayat" and pending:
            cells = [pending[0], pending[1] + " " + cells[0], *cells[1:]]
            pending = None
        if len(cells) == 5 and cells[0].isdigit() and cells[2] == "Grama Panchayat":
            key = (normal(cells[4]), normal(cells[1]))
            hierarchy[key] = cells[3]
    assert len(hierarchy) == 941, len(hierarchy)
    (SOURCE / "hierarchy-parsed.json").write_text(
        json.dumps([[*key, value] for key, value in hierarchy.items()], indent=2), encoding="utf-8"
    )
    unresolved = []
    records = []
    for lsg_code, sec in sorted(matched.items()):
        district_code, district_name, district_ml = DISTRICTS[sec["district"] - 1]
        if sec["kind"] == "B":
            continue
        block_lsg = "B" + lsg_code[1:5] + "00"
        assert block_lsg in matched, block_lsg
        block = matched[block_lsg]
        old_district = "Kozhikkode" if district_code == "KKD" else district_name
        parent = hierarchy.get(
            (
                normal(old_district),
                spelling["panchayat"].get(lsg_code, normal(lsg[lsg_code]["name"])),
            )
        )
        if parent is None or spelling["block"].get(normal(parent), normal(parent)) != normal(
            lsg[block_lsg]["name"]
        ):
            unresolved.append(
                {
                    "panchayat": lsg[lsg_code]["name"],
                    "district": district_name,
                    "pdf_parent": parent,
                    "directory_parent": lsg[block_lsg]["name"],
                    "lsg_code": lsg_code,
                }
            )
        records.append(
            {
                "state_code": "KL",
                "state_name_en": "Kerala",
                "state_name_ml": "കേരളം",
                "district_code": district_code,
                "district_name_en": district_name,
                "district_name_ml": district_ml,
                "district_order": sec["district"],
                "block_code": block["code"],
                "block_name_en": block["name"].title(),
                "block_name_ml": "",
                "block_lsg_code": block_lsg,
                "sec_local_body_code": sec["code"],
                "panchayat_name_en": sec["name"].title(),
                "panchayat_name_ml": "",
                "panchayat_lsg_code": lsg_code,
                "official_email": "",
                "office_phone": "",
                "active": "true",
            }
        )
    (SOURCE / "hierarchy-discrepancies.json").write_text(
        json.dumps(unresolved, indent=2), encoding="utf-8"
    )
    print("Hierarchy cross-check discrepancies:", len(unresolved))
    for row in unresolved:
        print(row)
    assert not unresolved, "Resolve all hierarchy discrepancies before writing the seed dataset."
    with (DATA / "locations.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(
        "Prepared",
        len(records),
        "Panchayat rows; unique blocks",
        len({r["block_code"] for r in records}),
    )
    manifest = {
        "retrieved_on": "2026-09-28",
        "counts": {"districts": 14, "blocks": 152, "panchayats": 941},
        "sources": json.loads((SOURCE / "manifest.json").read_text()),
        "hierarchy_reference": {
            "url": "https://lsgkerala.gov.in/htm/PDF/Election2015/Lcalbodies_2015.pdf",
            "sha256": hashlib.sha256((SOURCE / "lsg-hierarchy.pdf").read_bytes()).hexdigest(),
            "year": 2015,
        },
        "csv_sha256": hashlib.sha256((DATA / "locations.csv").read_bytes()).hexdigest(),
    }
    (DATA / "sources.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
