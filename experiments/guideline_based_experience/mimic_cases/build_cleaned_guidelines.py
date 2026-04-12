from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path


REPO = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent")
SOURCE_DIR = REPO / "experiments/guideline_based_experience/guidelines"
SOURCE_INDEX = SOURCE_DIR / "mimic_exact_match_guideline_index.csv"
CLEAN_DIR = REPO / "experiments/guideline_based_experience/cleaned_guidelines"
CLEAN_INDEX = CLEAN_DIR / "cleaned_guideline_index.csv"
EXCLUDED_INDEX = CLEAN_DIR / "excluded_vague_diagnoses.csv"


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def cleaned_diagnosis_name(diagnosis: str) -> str:
    cleaned = diagnosis
    replacements = [
        (r"\bunspecified\b", ""),
        (r"\bother\b", ""),
        (r"\bpossible\b", ""),
        (r"\blikely due to\b", "due to"),
        (r",\s*,", ", "),
        (r"\(\s*\)", ""),
        (r"\s+", " "),
    ]
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s*$", "", cleaned)
    cleaned = re.sub(r"^\s*,\s*", "", cleaned)
    cleaned = cleaned.strip()

    # Prefer canonical disease wording for labels that become awkward after removing vague modifiers.
    overrides = {
        "Unspecified acute appendicitis": "Acute appendicitis",
        "Unspecified appendicitis": "Appendicitis",
        "Unspecified intestinal obstruction": "Intestinal obstruction",
        "Unspecified psychosis": "Psychosis",
        "Unspecified schizophrenia, unspecified": "Schizophrenia",
        "Acute pericarditis, unspecified": "Acute pericarditis",
        "Acute pharyngitis, unspecified": "Acute pharyngitis",
        "Cellulitis and abscess of finger, unspecified": "Cellulitis and abscess of finger",
        "Cerebral artery occlusion, unspecified with cerebral infarction": "Cerebral artery occlusion with cerebral infarction",
        "Contact dermatitis and other eczema, unspecified cause": "Contact dermatitis and eczema",
        "Infective otitis externa, unspecified": "Infective otitis externa",
        "Otitis media, unspecified, left ear": "Otitis media, left ear",
        "Pneumonia, organism unspecified": "Pneumonia",
        "Schizoaffective disorder, unspecified": "Schizoaffective disorder",
        "Unspecified sinusitis (chronic)": "Chronic sinusitis",
    }
    return overrides.get(diagnosis, cleaned)


def vague_reason(diagnosis: str) -> str | None:
    normalized = diagnosis.lower()
    explicit_vague = {
        "abdominal pain": "symptom-level label rather than a disease diagnosis",
        "chest pain": "symptom-level label rather than a disease diagnosis",
        "epistaxis": "symptom-level label rather than a disease diagnosis",
        "renal colic": "symptom-level label rather than a disease diagnosis",
        "sore throat": "symptom-level label rather than a disease diagnosis",
    }
    for phrase, reason in explicit_vague.items():
        if phrase in normalized:
            return reason
    return None


def rewritten_text(original_text: str, cleaned_name: str) -> str:
    lines = original_text.splitlines()
    if lines and lines[0].startswith("Diagnosis: "):
        original_name = lines[0].removeprefix("Diagnosis: ")
        lines[0] = f"Diagnosis: {cleaned_name}"
        lines.insert(1, f"Original diagnosis label: {original_name}")
    return "\n".join(lines).rstrip() + "\n"


def unique_output_name(base_name: str, source: str, used: set[str]) -> str:
    base = f"{slugify(base_name)}_{source}"
    candidate = f"{base}.txt"
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix = 2
    while True:
        candidate = f"{base}_{suffix}.txt"
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def main() -> None:
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    with SOURCE_INDEX.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    clean_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []
    used_names: set[str] = set()

    for row in rows:
        diagnosis = row["diagnosis"]
        reason = vague_reason(diagnosis)
        if reason is not None:
            excluded_rows.append(
                {
                    "diagnosis": diagnosis,
                    "scenario_ids": row["scenario_ids"],
                    "reason": reason,
                    "original_guideline_txt_file": row["guideline_txt_file"],
                }
            )
            continue

        cleaned_name = cleaned_diagnosis_name(diagnosis)
        source = row["source"]
        output_name = unique_output_name(cleaned_name, source, used_names)
        output_path = CLEAN_DIR / output_name

        original_path = Path(row["guideline_txt_file"])
        original_text = original_path.read_text(encoding="utf-8")
        output_path.write_text(rewritten_text(original_text, cleaned_name), encoding="utf-8")

        clean_rows.append(
            {
                "cleaned_diagnosis": cleaned_name,
                "original_diagnosis": diagnosis,
                "scenario_ids": row["scenario_ids"],
                "count_in_file": row["count_in_file"],
                "source": source,
                "guideline_title": row["guideline_title"],
                "guideline_id": row["guideline_id"],
                "guideline_origin_path": row["guideline_origin_path"],
                "cleaned_guideline_txt_file": str(output_path),
                "strict_matched_alias": row["strict_matched_alias"],
                "strict_match_score": row["strict_match_score"],
            }
        )

    with CLEAN_INDEX.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "cleaned_diagnosis",
                "original_diagnosis",
                "scenario_ids",
                "count_in_file",
                "source",
                "guideline_title",
                "guideline_id",
                "guideline_origin_path",
                "cleaned_guideline_txt_file",
                "strict_matched_alias",
                "strict_match_score",
            ],
        )
        writer.writeheader()
        writer.writerows(clean_rows)

    with EXCLUDED_INDEX.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["diagnosis", "scenario_ids", "reason", "original_guideline_txt_file"],
        )
        writer.writeheader()
        writer.writerows(excluded_rows)

    print(CLEAN_INDEX)
    print(f"cleaned_guidelines={len(clean_rows)}")
    print(f"excluded_vague={len(excluded_rows)}")


if __name__ == "__main__":
    main()
