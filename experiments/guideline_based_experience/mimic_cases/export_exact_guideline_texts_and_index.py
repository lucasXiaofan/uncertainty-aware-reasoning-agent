from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path


REPO = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent")
CSV_PATH = REPO / (
    "experiments/guideline_based_experience/mimic_cases/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804_false_cases_exact_diagnosis_guideline_matches.csv"
)
JSONL_PATH = REPO / (
    "experiments/guideline_based_experience/mimic_cases/"
    "gpt5_nano_on_mimic_with_mimic_prompt/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl"
)
MAYO_PATH = REPO / "experiments/guideline_based_experience/mayoclinical.json"
GUIDELINES_DIR = REPO / "experiments/guideline_based_experience/guidelines"
INDEX_PATH = GUIDELINES_DIR / "mimic_exact_match_guideline_index.csv"

BOILERPLATE_MAYO = {
    "Overview",
    "Symptoms",
    "Causes",
    "Risk factors",
    "Complications",
    "Prevention",
    "When to see a doctor",
    "By Mayo Clinic Staff",
    "Terms & Conditions",
    "Notice of Nondiscrimination",
    "Privacy Policy",
    "Advertising & Sponsorship Policy",
    "Notice of Privacy Practices",
    "Accessibility Statement",
    "Manage Cookies",
    "Site Map",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def unique_filename(diagnosis: str, source: str, used_paths: set[str]) -> str:
    base = f"{slugify(diagnosis)}_{source}"
    filename = f"{base}.txt"
    if filename not in used_paths:
        used_paths.add(filename)
        return filename

    suffix = 2
    while True:
        filename = f"{base}_{suffix}.txt"
        if filename not in used_paths:
            used_paths.add(filename)
            return filename
        suffix += 1


def load_mayo_by_id() -> dict[str, str]:
    mayo_by_id: dict[str, str] = {}
    for item in json.loads(MAYO_PATH.read_text(encoding="utf-8")):
        entry_id = str(item.get("id"))
        text = item.get("text", "").strip()
        if text:
            mayo_by_id[entry_id] = text
    return mayo_by_id


def scenario_ids_by_diagnosis() -> dict[str, list[int]]:
    mapping: dict[str, list[int]] = defaultdict(list)
    with JSONL_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            diagnosis = row["correct_diagnosis"].strip()
            mapping[diagnosis].append(int(row["scenario_id"]))
    return {diagnosis: sorted(ids) for diagnosis, ids in mapping.items()}


def load_exact_rows() -> list[dict[str, str]]:
    with CSV_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row["strict_match_type"] == "exact"]


def source_label(row: dict[str, str]) -> str:
    return "uptodate" if row["guideline_source"] == "uptodate" else "mayoclinic"


def guideline_text(row: dict[str, str], mayo_by_id: dict[str, str]) -> str:
    if row["guideline_source"] == "uptodate":
        return Path(row["guideline_path"]).read_text(encoding="utf-8", errors="ignore").strip()
    return mayo_by_id[row["guideline_id"]].strip()


def render_guideline_file(row: dict[str, str], scenario_ids: list[int], text: str) -> str:
    lines = [
        f"Diagnosis: {row['diagnosis']}",
        f"Source: {source_label(row)}",
        f"Guideline title: {row['guideline_title']}",
        f"Guideline id: {row['guideline_id']}",
        f"Relevant scenario_ids: {', '.join(str(sid) for sid in scenario_ids)}",
        f"Matched alias: {row['strict_matched_alias']}",
        f"Original source path: {row['guideline_path']}",
        "",
        "Guideline content",
        "",
        text,
    ]
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    GUIDELINES_DIR.mkdir(parents=True, exist_ok=True)
    exact_rows = load_exact_rows()
    scenario_map = scenario_ids_by_diagnosis()
    mayo_by_id = load_mayo_by_id()
    used_paths: set[str] = set()

    index_rows: list[dict[str, str]] = []
    for row in exact_rows:
        diagnosis = row["diagnosis"]
        scenario_ids = scenario_map.get(diagnosis, [])
        source = source_label(row)
        filename = unique_filename(diagnosis, source, used_paths)
        output_path = GUIDELINES_DIR / filename

        text = guideline_text(row, mayo_by_id)
        output_path.write_text(render_guideline_file(row, scenario_ids, text), encoding="utf-8")

        index_rows.append(
            {
                "diagnosis": diagnosis,
                "scenario_ids": ",".join(str(sid) for sid in scenario_ids),
                "count_in_file": row["count_in_file"],
                "source": source,
                "guideline_title": row["guideline_title"],
                "guideline_id": row["guideline_id"],
                "guideline_origin_path": row["guideline_path"],
                "guideline_txt_file": str(output_path),
                "strict_matched_alias": row["strict_matched_alias"],
                "strict_match_score": row["strict_match_score"],
            }
        )

    with INDEX_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "diagnosis",
                "scenario_ids",
                "count_in_file",
                "source",
                "guideline_title",
                "guideline_id",
                "guideline_origin_path",
                "guideline_txt_file",
                "strict_matched_alias",
                "strict_match_score",
            ],
        )
        writer.writeheader()
        writer.writerows(index_rows)

    print(INDEX_PATH)
    print(f"guideline_files={len(index_rows)}")


if __name__ == "__main__":
    main()
