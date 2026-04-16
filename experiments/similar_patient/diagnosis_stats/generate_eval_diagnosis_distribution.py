from __future__ import annotations

import json
import math
from collections import Counter
from html import escape
from pathlib import Path


ROOT = Path(
    "/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent"
)
PREDICTIONS_PATH = ROOT / (
    "experiments/guideline_based_experience/mimic_cases/"
    "gpt5_nano_on_mimic_with_mimic_prompt/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl"
)
REFERENCE_STATS_PATH = ROOT / (
    "experiments/similar_patient/diagnosis_stats/"
    "mimiciv_single_diagnosis_nonoverlap_patients_stats.json"
)
OUTPUT_DIR = ROOT / "experiments/similar_patient/diagnosis_stats"
OUTPUT_JSON = OUTPUT_DIR / "gpt5_nano_mimic_diagnosis_distribution_comparison.json"

TOP_N_FOR_CHART = 15


def load_predictions(path: Path) -> list[dict]:
    with path.open() as f:
        return [json.loads(line) for line in f]


def load_reference_stats(path: Path) -> tuple[dict, dict[str, dict]]:
    data = json.loads(path.read_text())
    diagnosis_index = {
        item["diagnosis"]: item for item in data["diagnoses_by_repeat"]
    }
    return data, diagnosis_index


def build_bucket(
    rows: list[dict],
    reference_index: dict[str, dict],
    reference_total_subjects: int,
    bucket_name: str,
) -> dict:
    counter = Counter(row["correct_diagnosis"] for row in rows)
    total_cases = sum(counter.values())

    case_distribution = []
    reference_matches = []
    missing_in_reference = []

    for diagnosis, count in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
        case_pct = (count / total_cases * 100) if total_cases else 0.0
        entry = {
            "diagnosis": diagnosis,
            "case_count": count,
            "case_percentage": round(case_pct, 4),
        }
        case_distribution.append(entry)

        ref = reference_index.get(diagnosis)
        if ref is None:
            missing_in_reference.append(diagnosis)
            continue

        reference_matches.append(
            {
                "diagnosis": diagnosis,
                "reference_count": ref["repeat_count"],
                "reference_percentage_full_cohort": round(ref["percentage"], 4),
                "reference_percentage_from_count": round(
                    ref["repeat_count"] / reference_total_subjects * 100, 4
                ),
            }
        )

    matched_reference_total = sum(item["reference_count"] for item in reference_matches)
    for item in reference_matches:
        subset_pct = (
            item["reference_count"] / matched_reference_total * 100
            if matched_reference_total
            else 0.0
        )
        item["reference_percentage_within_matched_subset"] = round(subset_pct, 4)

    return {
        "bucket_name": bucket_name,
        "total_cases": total_cases,
        "unique_diagnoses": len(case_distribution),
        "matched_reference_diagnoses": len(reference_matches),
        "missing_reference_diagnoses": missing_in_reference,
        "case_distribution": case_distribution,
        "reference_distribution_for_same_diagnoses": reference_matches,
        "reference_matched_total_subjects": matched_reference_total,
    }


def build_overlap_analysis(
    correct_rows: list[dict],
    wrong_rows: list[dict],
) -> dict:
    correct_by_diagnosis: dict[str, list[int]] = {}
    wrong_by_diagnosis: dict[str, list[int]] = {}

    for row in correct_rows:
        correct_by_diagnosis.setdefault(row["correct_diagnosis"], []).append(
            row["scenario_id"]
        )
    for row in wrong_rows:
        wrong_by_diagnosis.setdefault(row["correct_diagnosis"], []).append(
            row["scenario_id"]
        )

    overlap_diagnoses = sorted(
        set(correct_by_diagnosis).intersection(wrong_by_diagnosis),
        key=lambda diagnosis: (
            -(len(correct_by_diagnosis[diagnosis]) + len(wrong_by_diagnosis[diagnosis])),
            diagnosis,
        ),
    )

    overlap_items = []
    for diagnosis in overlap_diagnoses:
        overlap_items.append(
            {
                "diagnosis": diagnosis,
                "correct_count": len(correct_by_diagnosis[diagnosis]),
                "wrong_count": len(wrong_by_diagnosis[diagnosis]),
                "total_count": len(correct_by_diagnosis[diagnosis])
                + len(wrong_by_diagnosis[diagnosis]),
                "correct_scenario_ids": sorted(correct_by_diagnosis[diagnosis]),
                "wrong_scenario_ids": sorted(wrong_by_diagnosis[diagnosis]),
            }
        )

    return {
        "summary": {
            "diagnoses_in_both_correct_and_wrong": len(overlap_items),
            "correct_unique_diagnoses": len(correct_by_diagnosis),
            "wrong_unique_diagnoses": len(wrong_by_diagnosis),
        },
        "overlap_diagnoses": overlap_items,
    }


def collapse_for_chart(items: list[dict], value_key: str) -> list[dict]:
    items = sorted(items, key=lambda x: (-x[value_key], x["diagnosis"]))
    if len(items) <= TOP_N_FOR_CHART:
        return items

    head = items[:TOP_N_FOR_CHART]
    tail = items[TOP_N_FOR_CHART:]
    other_value = sum(item[value_key] for item in tail)
    other_item = {
        "diagnosis": f"Other ({len(tail)} diagnoses)",
        value_key: other_value,
    }

    percentage_keys = {
        key
        for item in tail
        for key, value in item.items()
        if key.endswith("percentage") and isinstance(value, (int, float))
    }
    for key in percentage_keys:
        other_item[key] = round(sum(item.get(key, 0.0) for item in tail), 4)

    head.append(other_item)
    return head


def make_pie_chart(
    items: list[dict],
    value_key: str,
    legend_builder,
    title: str,
    output_path: Path,
) -> None:
    chart_items = collapse_for_chart(items, value_key)
    labels = [item["diagnosis"] for item in chart_items]
    sizes = [item[value_key] for item in chart_items]

    colors = [
        "#4E79A7",
        "#F28E2B",
        "#E15759",
        "#76B7B2",
        "#59A14F",
        "#EDC948",
        "#B07AA1",
        "#FF9DA7",
        "#9C755F",
        "#BAB0AC",
        "#86BCB6",
        "#D37295",
        "#FABFD2",
        "#8CD17D",
        "#B6992D",
        "#499894",
    ][: len(chart_items)]

    width = 1800
    height = max(1000, 200 + len(chart_items) * 44)
    cx, cy, r = 360, height // 2, 240
    legend_x = 700
    legend_y = 150

    total = sum(sizes) or 1
    start_angle = -90.0
    paths = []
    legend_lines = []

    for i, (item, size) in enumerate(zip(chart_items, sizes)):
        sweep = size / total * 360.0
        end_angle = start_angle + sweep
        large_arc = 1 if sweep > 180 else 0

        x1 = cx + r * math.cos(math.radians(start_angle))
        y1 = cy + r * math.sin(math.radians(start_angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))

        if sweep >= 359.999:
            path_d = (
                f"M {cx},{cy-r} "
                f"A {r},{r} 0 1,1 {cx-0.01},{cy-r} "
                f"A {r},{r} 0 1,1 {cx},{cy-r} Z"
            )
        else:
            path_d = (
                f"M {cx},{cy} "
                f"L {x1:.3f},{y1:.3f} "
                f"A {r},{r} 0 {large_arc},1 {x2:.3f},{y2:.3f} Z"
            )

        color = colors[i]
        paths.append(
            f'<path d="{path_d}" fill="{color}" stroke="#ffffff" stroke-width="1.5" />'
        )
        legend_label = escape(legend_builder(item))
        y = legend_y + i * 44
        legend_lines.append(
            f'<rect x="{legend_x}" y="{y-14}" width="18" height="18" fill="{color}" />'
        )
        legend_lines.append(
            f'<text x="{legend_x + 30}" y="{y}" font-size="18" '
            f'font-family="Arial, sans-serif">{legend_label}</text>'
        )
        start_angle = end_angle

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="60" y="60" font-size="30" font-weight="bold" font-family="Arial, sans-serif">{escape(title)}</text>
  <text x="60" y="95" font-size="18" fill="#444444" font-family="Arial, sans-serif">Pie chart uses top {TOP_N_FOR_CHART} diagnoses plus Other for readability.</text>
  {''.join(paths)}
  <text x="{legend_x}" y="100" font-size="24" font-weight="bold" font-family="Arial, sans-serif">Diagnosis Legend</text>
  {''.join(legend_lines)}
</svg>
"""
    output_path.write_text(svg)


def make_overlap_chart(overlap_items: list[dict], output_path: Path) -> None:
    top_items = overlap_items[:20]
    width = 1800
    row_height = 34
    top_margin = 110
    left_label_width = 620
    chart_width = 760
    right_margin = 120
    height = max(420, top_margin + len(top_items) * row_height + 120)
    max_count = max((item["total_count"] for item in top_items), default=1)
    bar_area_x = left_label_width
    center_x = bar_area_x + chart_width // 2
    scale = (chart_width / 2 - 30) / max_count

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '  <rect width="100%" height="100%" fill="#ffffff" />',
        '  <text x="60" y="55" font-size="30" font-weight="bold" font-family="Arial, sans-serif">Diagnoses Appearing in Both Correct and Wrong Predictions</text>',
        '  <text x="60" y="88" font-size="18" fill="#444444" font-family="Arial, sans-serif">Blue bars show correct counts; red bars show wrong counts. Top 20 overlap diagnoses are shown.</text>',
        f'  <line x1="{center_x}" y1="{top_margin - 20}" x2="{center_x}" y2="{height - 60}" stroke="#666666" stroke-width="1.5" />',
        '  <rect x="60" y="104" width="18" height="18" fill="#4E79A7" />',
        '  <text x="88" y="119" font-size="18" font-family="Arial, sans-serif">Correct</text>',
        '  <rect x="190" y="104" width="18" height="18" fill="#E15759" />',
        '  <text x="218" y="119" font-size="18" font-family="Arial, sans-serif">Wrong</text>',
    ]

    for i, item in enumerate(top_items):
        y = top_margin + i * row_height
        correct_width = item["correct_count"] * scale
        wrong_width = item["wrong_count"] * scale
        diagnosis = escape(item["diagnosis"])

        lines.append(
            f'  <text x="{left_label_width - 12}" y="{y + 14}" text-anchor="end" font-size="15" font-family="Arial, sans-serif">{diagnosis}</text>'
        )
        lines.append(
            f'  <rect x="{center_x - correct_width:.2f}" y="{y}" width="{correct_width:.2f}" height="16" fill="#4E79A7" />'
        )
        lines.append(
            f'  <rect x="{center_x:.2f}" y="{y}" width="{wrong_width:.2f}" height="16" fill="#E15759" />'
        )
        lines.append(
            f'  <text x="{center_x - correct_width - 8:.2f}" y="{y + 14}" text-anchor="end" font-size="14" font-family="Arial, sans-serif">{item["correct_count"]}</text>'
        )
        lines.append(
            f'  <text x="{center_x + wrong_width + 8:.2f}" y="{y + 14}" font-size="14" font-family="Arial, sans-serif">{item["wrong_count"]}</text>'
        )

    tick_counts = range(1, max_count + 1)
    for tick in tick_counts:
        offset = tick * scale
        lines.append(
            f'  <line x1="{center_x - offset:.2f}" y1="{top_margin - 25}" x2="{center_x - offset:.2f}" y2="{height - 60}" stroke="#eeeeee" stroke-width="1" />'
        )
        lines.append(
            f'  <line x1="{center_x + offset:.2f}" y1="{top_margin - 25}" x2="{center_x + offset:.2f}" y2="{height - 60}" stroke="#eeeeee" stroke-width="1" />'
        )
        lines.append(
            f'  <text x="{center_x - offset:.2f}" y="{height - 30}" text-anchor="middle" font-size="12" fill="#666666" font-family="Arial, sans-serif">{tick}</text>'
        )
        lines.append(
            f'  <text x="{center_x + offset:.2f}" y="{height - 30}" text-anchor="middle" font-size="12" fill="#666666" font-family="Arial, sans-serif">{tick}</text>'
        )

    lines.append("</svg>")
    output_path.write_text("\n".join(lines))


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    predictions = load_predictions(PREDICTIONS_PATH)
    reference_stats, reference_index = load_reference_stats(REFERENCE_STATS_PATH)
    reference_total_subjects = reference_stats["summary"]["total_subject_ids"]

    correct_rows = [row for row in predictions if row.get("correct") is True]
    wrong_rows = [row for row in predictions if row.get("correct") is False]
    overlap_analysis = build_overlap_analysis(correct_rows, wrong_rows)

    correct_bucket = build_bucket(
        correct_rows,
        reference_index,
        reference_total_subjects,
        "correct_predictions",
    )
    wrong_bucket = build_bucket(
        wrong_rows,
        reference_index,
        reference_total_subjects,
        "wrong_predictions",
    )

    output = {
        "source_predictions_jsonl": str(PREDICTIONS_PATH),
        "source_reference_stats_json": str(REFERENCE_STATS_PATH),
        "generated_outputs_dir": str(OUTPUT_DIR),
        "notes": [
            "Case-side distributions are computed from `correct_diagnosis` within each bucket (`correct == true` and `correct == false`).",
            "Reference-side distributions are joined by exact diagnosis string match against the full single-diagnosis MIMIC-IV stats file.",
            "Reference JSON values include both the original full-cohort percentage and the subset-normalized percentage among only the matched diagnoses.",
            "Pie charts use top 15 diagnoses plus an aggregated `Other` slice for readability; the JSON preserves all diagnoses.",
        ],
        "prediction_summary": {
            "total_cases": len(predictions),
            "correct_cases": len(correct_rows),
            "wrong_cases": len(wrong_rows),
        },
        "reference_summary": reference_stats["summary"],
        "overall_predictions": build_bucket(
            predictions,
            reference_index,
            reference_total_subjects,
            "overall_predictions",
        ),
        "correct_wrong_overlap_json": str(
            OUTPUT_DIR / "gpt5_nano_correct_wrong_overlap_analysis.json"
        ),
        "correct_predictions": correct_bucket,
        "wrong_predictions": wrong_bucket,
        "generated_chart_files": {
            "correct_wrong_overlap": str(
                OUTPUT_DIR / "gpt5_nano_correct_wrong_overlap_bar.svg"
            ),
            "overall_case_distribution": str(
                OUTPUT_DIR / "gpt5_nano_overall_case_diagnosis_distribution_pie.svg"
            ),
            "overall_reference_distribution": str(
                OUTPUT_DIR / "gpt5_nano_overall_reference_diagnosis_distribution_pie.svg"
            ),
            "correct_case_distribution": str(
                OUTPUT_DIR / "gpt5_nano_correct_case_diagnosis_distribution_pie.svg"
            ),
            "correct_reference_distribution": str(
                OUTPUT_DIR / "gpt5_nano_correct_reference_diagnosis_distribution_pie.svg"
            ),
            "wrong_case_distribution": str(
                OUTPUT_DIR / "gpt5_nano_wrong_case_diagnosis_distribution_pie.svg"
            ),
            "wrong_reference_distribution": str(
                OUTPUT_DIR / "gpt5_nano_wrong_reference_diagnosis_distribution_pie.svg"
            ),
        },
    }

    OUTPUT_JSON.write_text(json.dumps(output, indent=2))
    (
        OUTPUT_DIR / "gpt5_nano_correct_wrong_overlap_analysis.json"
    ).write_text(json.dumps(overlap_analysis, indent=2))

    make_overlap_chart(
        overlap_analysis["overlap_diagnoses"],
        OUTPUT_DIR / "gpt5_nano_correct_wrong_overlap_bar.svg",
    )

    make_pie_chart(
        output["overall_predictions"]["case_distribution"],
        "case_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["case_count"]} cases | '
            f'{item.get("case_percentage", 0):.2f}% of all 200 cases'
        ),
        "Overall 200 AgentClinic Cases: Diagnosis Distribution (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_overall_case_diagnosis_distribution_pie.svg",
    )
    make_pie_chart(
        output["overall_predictions"]["reference_distribution_for_same_diagnoses"],
        "reference_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["reference_count"]} patients | '
            f'{item.get("reference_percentage_full_cohort", 0):.2f}% of full 5,513-patient cohort | '
            f'{item.get("reference_percentage_within_matched_subset", 0):.2f}% of matched subset'
        ),
        "Overall 200 AgentClinic Cases: Same Diagnoses in Single-Diagnosis Cohort (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_overall_reference_diagnosis_distribution_pie.svg",
    )
    make_pie_chart(
        correct_bucket["case_distribution"],
        "case_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["case_count"]} cases | '
            f'{item.get("case_percentage", 0):.2f}% of correct bucket'
        ),
        "Correct Predictions: Diagnosis Distribution (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_correct_case_diagnosis_distribution_pie.svg",
    )
    make_pie_chart(
        correct_bucket["reference_distribution_for_same_diagnoses"],
        "reference_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["reference_count"]} patients | '
            f'{item.get("reference_percentage_full_cohort", 0):.2f}% of full cohort | '
            f'{item.get("reference_percentage_within_matched_subset", 0):.2f}% of matched subset'
        ),
        "Correct Predictions: Same Diagnoses in Single-Diagnosis Cohort (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_correct_reference_diagnosis_distribution_pie.svg",
    )
    make_pie_chart(
        wrong_bucket["case_distribution"],
        "case_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["case_count"]} cases | '
            f'{item.get("case_percentage", 0):.2f}% of wrong bucket'
        ),
        "Wrong Predictions: Diagnosis Distribution (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_wrong_case_diagnosis_distribution_pie.svg",
    )
    make_pie_chart(
        wrong_bucket["reference_distribution_for_same_diagnoses"],
        "reference_count",
        lambda item: (
            f'{item["diagnosis"]} | {item["reference_count"]} patients | '
            f'{item.get("reference_percentage_full_cohort", 0):.2f}% of full cohort | '
            f'{item.get("reference_percentage_within_matched_subset", 0):.2f}% of matched subset'
        ),
        "Wrong Predictions: Same Diagnoses in Single-Diagnosis Cohort (Top 15 + Other)",
        OUTPUT_DIR / "gpt5_nano_wrong_reference_diagnosis_distribution_pie.svg",
    )


if __name__ == "__main__":
    main()
