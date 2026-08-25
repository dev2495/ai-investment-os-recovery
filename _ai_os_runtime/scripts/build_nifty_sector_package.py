#!/usr/bin/env python3
"""Build an evidence-backed sector package from operator-downloaded Nifty CSV files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


INDEXES = (
    ("nifty-auto", "Nifty Auto", "ind_niftyautolist.csv", "nifty-auto"),
    ("nifty-bank", "Nifty Bank", "ind_niftybanklist.csv", "nifty-bank"),
    ("nifty-financial-services", "Nifty Financial Services", "ind_niftyfinancelist.csv", "nifty-financial-services"),
    ("nifty-fmcg", "Nifty FMCG", "ind_niftyfmcglist.csv", "nifty-fmcg"),
    ("nifty-it", "Nifty IT", "ind_niftyitlist.csv", "nifty-it"),
    ("nifty-media", "Nifty Media", "ind_niftymedialist.csv", "nifty-media"),
    ("nifty-metal", "Nifty Metal", "ind_niftymetallist.csv", "nifty-metal"),
    ("nifty-pharma", "Nifty Pharma", "ind_niftypharmalist.csv", "nifty-pharma"),
    ("nifty-private-bank", "Nifty Private Bank", "ind_nifty_privatebanklist.csv", "nifty-private-bank"),
    ("nifty-psu-bank", "Nifty PSU Bank", "ind_niftypsubanklist.csv", "nifty-psu-bank"),
    ("nifty-realty", "Nifty Realty", "ind_niftyrealtylist.csv", "nifty-realty"),
)
EXPECTED_COLUMNS = ("Company Name", "Industry", "Symbol", "Series", "ISIN Code")


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def build_package(input_dir: Path, as_of_date: str, observed_at: str) -> dict[str, Any]:
    datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    manifest: list[dict[str, Any]] = []
    taxonomy: list[dict[str, Any]] = []
    memberships: list[dict[str, Any]] = []

    for index_key, index_name, file_name, page_slug in INDEXES:
        path = input_dir / file_name
        if not path.is_file():
            raise ValueError(f"missing official constituent file: {file_name}")
        file_hash = sha256_file(path)
        page_url = f"https://www.niftyindices.com/indices/equity/sectoral-indices/{page_slug}"
        download_url = f"https://www.niftyindices.com/IndexConstituent/{file_name}"
        sector_key = f"nse-index:{index_key}"
        taxonomy.append({
            "taxonomy_key": sector_key,
            "node_code": index_key.upper().replace("-", "_"),
            "node_name": index_name,
            "node_level": "sector",
            "valid_from": as_of_date,
            "description": "Point-in-time official Nifty sectoral-index basket; not inferred historical industry membership.",
            "source_reference": f"sha256://{file_hash}",
            "methodology": {
                "classification_scope": "official_index_basket",
                "membership_as_of": as_of_date,
                "historical_start_unknown": True,
                "authoritative_for": "observed_index_constituents",
                "not_authoritative_for": ["historical_membership_start", "company_primary_industry", "index_weights"],
                "page_url": page_url,
                "download_url": download_url,
            },
        })
        rows: list[dict[str, str]] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
                raise ValueError(f"unexpected columns in {file_name}: {reader.fieldnames}")
            seen: set[str] = set()
            for position, raw in enumerate(reader, start=2):
                row = {key: str(raw.get(key) or "").strip() for key in EXPECTED_COLUMNS}
                if not all(row.values()):
                    raise ValueError(f"incomplete row in {file_name}:{position}")
                if row["Series"] != "EQ":
                    raise ValueError(f"unsupported series in {file_name}:{position}: {row['Series']}")
                if row["Symbol"] in seen:
                    raise ValueError(f"duplicate symbol in {file_name}: {row['Symbol']}")
                seen.add(row["Symbol"])
                rows.append(row)

        industries = sorted({row["Industry"] for row in rows})
        for industry in industries:
            taxonomy.append({
                "taxonomy_key": f"{sector_key}:industry:{slug(industry)}",
                "node_code": f"{index_key.upper().replace('-', '_')}__{slug(industry).upper().replace('-', '_')}",
                "node_name": industry,
                "node_level": "industry",
                "parent_key": sector_key,
                "valid_from": as_of_date,
                "description": f"Industry label supplied in the official {index_name} constituent CSV.",
                "source_reference": f"sha256://{file_hash}",
                "methodology": {"classification_scope": "source_supplied_index_industry_label", "membership_as_of": as_of_date},
            })

        for row in rows:
            evidence = [{
                "source": "NSE Indices Limited",
                "page_url": page_url,
                "download_url": download_url,
                "artifact_sha256": file_hash,
                "observed_at": observed_at,
                "membership_as_of": as_of_date,
                "company_name": row["Company Name"],
                "industry": row["Industry"],
                "series": row["Series"],
                "isin": row["ISIN Code"],
            }]
            common = {
                "symbol": row["Symbol"],
                "exchange": "NSE",
                "instrument_type": "equity",
                "company_name": row["Company Name"],
                "currency": "INR",
                "valid_from": as_of_date,
                "is_primary": False,
                "source_reference": f"sha256://{file_hash}",
                "evidence": evidence,
            }
            memberships.append({**common, "taxonomy_key": sector_key, "membership_role": "official_index_constituent"})
            memberships.append({
                **common,
                "taxonomy_key": f"{sector_key}:industry:{slug(row['Industry'])}",
                "membership_role": "source_industry_label",
            })
        manifest.append({
            "index_key": index_key,
            "index_name": index_name,
            "file_name": file_name,
            "sha256": file_hash,
            "row_count": len(rows),
            "page_url": page_url,
            "download_url": download_url,
        })

    canonical_manifest = json.dumps({"as_of_date": as_of_date, "files": manifest}, sort_keys=True, separators=(",", ":"))
    package_hash = hashlib.sha256(canonical_manifest.encode()).hexdigest()
    return {
        "source": {
            "name": "NSE Indices official sector constituents",
            "source_type": "primary_exchange_index_download",
            "location": "https://www.niftyindices.com/indices/equity/sectoral-indices",
            "artifact_ref": f"sha256://{package_hash}",
            "observed_at": observed_at,
            "manifest": manifest,
        },
        "taxonomy": taxonomy,
        "memberships": memberships,
        "metrics": [],
        "indices": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--observed-at", default=datetime.now(timezone.utc).isoformat())
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    package = build_package(args.input_dir.expanduser().resolve(), args.as_of_date, args.observed_at)
    args.output.write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "taxonomy_rows": len(package["taxonomy"]),
        "membership_rows": len(package["memberships"]),
        "source_artifact_ref": package["source"]["artifact_ref"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
