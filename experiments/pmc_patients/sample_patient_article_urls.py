#!/usr/bin/env python3
"""Sample PMC-Patients rows and add source article URLs.

PMC-Patients rows include both a PubMed PMID and a PubMed Central XML path.
The XML path contains the PMCID of the source article, which lets us construct
the stable full-text article URL without network calls.
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from pathlib import Path


DEFAULT_INPUT = Path("PMC-Patients.csv")
DEFAULT_OUTPUT = Path("experiments/pmc_patients/pmc_patients_sample_300_article_urls.csv")
PMCID_RE = re.compile(r"(PMC\d+)", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sample rows from PMC-Patients.csv and add source article URLs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input PMC-Patients CSV path. Default: {DEFAULT_INPUT}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=300,
        help="Number of patient rows to sample. Default: 300",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling. Default: 42",
    )
    parser.add_argument(
        "--include-patient-text",
        action="store_true",
        help="Include the full patient summary text in the output CSV.",
    )
    return parser.parse_args()


def extract_pmcid(file_path: str) -> str:
    matches = PMCID_RE.findall(file_path or "")
    if not matches:
        return ""
    return matches[-1].upper()


def article_urls(row: dict[str, str]) -> dict[str, str]:
    pmid = (row.get("PMID") or "").strip()
    pmcid = extract_pmcid(row.get("file_path", ""))

    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
    pmc_url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/" if pmcid else ""

    return {
        "pmc_id": pmcid,
        "pubmed_url": pubmed_url,
        "pmc_url": pmc_url,
        "original_article_url": pmc_url or pubmed_url,
    }


def reservoir_sample(
    input_path: Path, sample_size: int, seed: int
) -> tuple[list[str], list[dict[str, str]], int]:
    if sample_size <= 0:
        raise ValueError("--sample-size must be positive")

    rng = random.Random(seed)
    sample: list[dict[str, str]] = []
    total_rows = 0

    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{input_path} has no CSV header")
        fieldnames = list(reader.fieldnames)

        for row in reader:
            total_rows += 1
            if len(sample) < sample_size:
                sample.append(row)
                continue

            replacement_index = rng.randint(0, total_rows - 1)
            if replacement_index < sample_size:
                sample[replacement_index] = row

    return fieldnames, sample, total_rows


def output_fields(include_patient_text: bool) -> list[str]:
    fields = [
        "patient_id",
        "patient_uid",
        "PMID",
        "pmc_id",
        "title",
        "pubmed_url",
        "pmc_url",
        "original_article_url",
        "file_path",
        "age",
        "gender",
    ]
    if include_patient_text:
        fields.append("patient")
    return fields


def write_sample(
    rows: list[dict[str, str]], output_path: Path, include_patient_text: bool
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = output_fields(include_patient_text)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            enriched = {**row, **article_urls(row)}
            writer.writerow({field: enriched.get(field, "") for field in fields})


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    args = parse_args()

    _, rows, total_rows = reservoir_sample(args.input, args.sample_size, args.seed)
    write_sample(rows, args.output, args.include_patient_text)

    unique_articles = {
        article_urls(row)["original_article_url"]
        for row in rows
        if article_urls(row)["original_article_url"]
    }
    print(f"Read {total_rows:,} rows from {args.input}")
    print(f"Wrote {len(rows):,} sampled patients to {args.output}")
    print(f"Resolved {len(unique_articles):,} unique source article URLs")


if __name__ == "__main__":
    main()
