#!/usr/bin/env python3
"""
Analyze disease/condition coverage across two medical guideline sources:
1. mayoclinical.json (Mayo Clinic)
2. 结果/ directory (UpToDate)

Outputs a CSV with each unique disease/topic and which source(s) cover it.
"""

import json
import os
import csv
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
MAYO_FILE = SCRIPT_DIR / "mayoclinical.json"
UPTODATE_DIR = SCRIPT_DIR / "结果"
OUTPUT_CSV = SCRIPT_DIR / "disease_coverage.csv"


def extract_mayo_diseases(filepath: Path) -> dict[str, str]:
    """
    Extract disease names from mayoclinical.json.
    Each entry's text starts with the disease name (first non-URL, non-empty line).
    Returns {normalized_name: original_name}.
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    diseases = {}
    for entry in data:
        text = entry.get("text", "")
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines:
            # Skip URL lines and boilerplate
            if line.startswith("http") or line.startswith("©") or line in (
                "Overview", "Terms & Conditions", "Notice of Nondiscrimination",
                "Privacy Policy", "Advertising & Sponsorship Policy",
                "Notice of Privacy Practices", "Accessibility Statement",
                "Manage Cookies", "Site Map", "By Mayo Clinic Staff",
            ):
                continue
            # First valid line is the disease name
            name = line
            normalized = name.lower().strip()
            diseases[normalized] = name
            break

    return diseases


def extract_uptodate_topics(directory: Path) -> dict[str, str]:
    """
    Extract topic names from UpToDate txt files.
    First line of each file is the topic title.
    For 'Patient education: X (The Basics/Beyond the Basics)' → extracts X.
    Returns {normalized_name: original_name}.
    """
    topics = {}

    for txt_file in directory.glob("*.txt"):
        try:
            with open(txt_file, encoding="utf-8") as f:
                first_line = f.readline().strip()
        except Exception:
            continue

        if not first_line:
            continue

        # Normalize the topic name
        name = first_line

        # Extract disease name from "Patient education: X (The Basics/Beyond the Basics)"
        if name.startswith("Patient education:"):
            name = name[len("Patient education:"):].strip()
            # Remove trailing qualifiers like "(The Basics)" or "(Beyond the Basics)"
            for suffix in (" (The Basics)", " (Beyond the Basics)"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)].strip()

        normalized = name.lower().strip()
        if normalized:
            topics[normalized] = name

    return topics


def main():
    print("Extracting Mayo Clinic diseases...")
    mayo_diseases = extract_mayo_diseases(MAYO_FILE)
    print(f"  Found {len(mayo_diseases)} unique Mayo Clinic diseases")

    print("Extracting UpToDate topics...")
    uptodate_topics = extract_uptodate_topics(UPTODATE_DIR)
    print(f"  Found {len(uptodate_topics)} unique UpToDate topics")

    # Build union of all names
    all_normalized = set(mayo_diseases.keys()) | set(uptodate_topics.keys())
    print(f"\nTotal unique diseases/topics: {len(all_normalized)}")

    # Count overlap
    both = set(mayo_diseases.keys()) & set(uptodate_topics.keys())
    mayo_only = set(mayo_diseases.keys()) - set(uptodate_topics.keys())
    uptodate_only = set(uptodate_topics.keys()) - set(mayo_diseases.keys())
    print(f"  In both sources:      {len(both)}")
    print(f"  Mayo Clinic only:     {len(mayo_only)}")
    print(f"  UpToDate only:        {len(uptodate_only)}")

    # Write CSV
    rows = []
    for norm in sorted(all_normalized):
        in_mayo = norm in mayo_diseases
        in_uptodate = norm in uptodate_topics

        # Use the display name from whichever source has it (prefer mayo if both)
        display_name = mayo_diseases.get(norm) or uptodate_topics.get(norm)

        if in_mayo and in_uptodate:
            source = "both"
        elif in_mayo:
            source = "mayoclinic_only"
        else:
            source = "uptodate_only"

        rows.append({
            "disease_name": display_name,
            "has_mayoclinic": "yes" if in_mayo else "no",
            "has_uptodate": "yes" if in_uptodate else "no",
            "source": source,
        })

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["disease_name", "has_mayoclinic", "has_uptodate", "source"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nCSV written to: {OUTPUT_CSV}")
    print(f"Total rows: {len(rows)}")


if __name__ == "__main__":
    main()
