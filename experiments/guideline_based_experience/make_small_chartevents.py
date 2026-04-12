#!/usr/bin/env python3
"""Create a smaller sampled version of MIMIC-IV ICU chartevents.csv.

This streams the input file line-by-line and writes an approximately
target-sized CSV by sampling rows with a fixed probability derived from
the source file size.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sample a large CSV into a much smaller CSV without loading "
            "the full file into memory."
        )
    )
    parser.add_argument(
        "--input",
        default="chartevents.csv",
        help="Path to the source CSV (default: chartevents.csv)",
    )
    parser.add_argument(
        "--output",
        default="chartevents_150mb.csv",
        help="Path to the output CSV (default: chartevents_150mb.csv)",
    )
    parser.add_argument(
        "--target-mb",
        type=float,
        default=150.0,
        help="Approximate output size in MB (decimal megabytes, default: 150)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        return 1

    source_size = input_path.stat().st_size
    target_bytes = int(args.target_mb * 1_000_000)

    if target_bytes <= 0:
        print("--target-mb must be positive", file=sys.stderr)
        return 1

    if source_size <= target_bytes:
        print(
            "Source file is already smaller than the requested target size.",
            file=sys.stderr,
        )
        return 1

    # Use a slight headroom discount because line lengths vary and the CSV
    # header is always retained.
    sample_probability = min(1.0, (target_bytes / source_size) * 0.98)
    random.seed(args.seed)

    written_bytes = 0
    input_rows = 0
    output_rows = 0

    with input_path.open("r", encoding="utf-8", newline="") as src:
        with output_path.open("w", encoding="utf-8", newline="") as dst:
            header = src.readline()
            if not header:
                print("Input file is empty.", file=sys.stderr)
                return 1

            dst.write(header)
            written_bytes += len(header.encode("utf-8"))

            for line in src:
                input_rows += 1
                if random.random() < sample_probability:
                    dst.write(line)
                    written_bytes += len(line.encode("utf-8"))
                    output_rows += 1

                    if written_bytes >= target_bytes:
                        break

    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Source size: {source_size / 1_000_000:.1f} MB")
    print(f"Target size: {target_bytes / 1_000_000:.1f} MB")
    print(f"Actual size: {written_bytes / 1_000_000:.1f} MB")
    print(f"Rows scanned: {input_rows:,}")
    print(f"Rows written: {output_rows:,}")
    print(f"Sampling probability: {sample_probability:.6f}")
    print(f"Seed: {args.seed}")

    if written_bytes < target_bytes * 0.85:
        print(
            "Warning: output is materially below target size. "
            "Increase --target-mb slightly and rerun if needed.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
