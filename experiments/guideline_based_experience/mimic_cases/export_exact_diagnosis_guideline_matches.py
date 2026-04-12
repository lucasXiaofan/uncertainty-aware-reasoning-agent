from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


REPO = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent")
REPORT_PATH = REPO / (
    "experiments/guideline_based_experience/mimic_cases/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804_unique_diagnosis_guideline_report.json"
)
MAYO_PATH = REPO / "experiments/guideline_based_experience/mayoclinical.json"
UTD_DIR = REPO / "experiments/guideline_based_experience/结果"
OUTPUT_CSV = REPO / (
    "experiments/guideline_based_experience/mimic_cases/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804_false_cases_exact_diagnosis_guideline_matches.csv"
)

STOPWORDS = {
    "of",
    "and",
    "the",
    "with",
    "without",
    "mention",
    "other",
    "unspecified",
    "acute",
    "chronic",
    "except",
    "not",
    "elsewhere",
    "classified",
    "condition",
    "complication",
    "episode",
    "single",
    "recurrent",
    "continuous",
    "state",
    "possible",
    "signs",
    "symptoms",
    "antepartum",
    "or",
    "in",
    "on",
    "due",
    "to",
    "left",
    "right",
    "upper",
    "lower",
    "non",
    "type",
    "adult",
    "adults",
    "child",
    "children",
    "likely",
    "probable",
    "status",
    "generalized",
    "organism",
    "before",
    "after",
    "caused",
    "causing",
    "nontraumatic",
    "initial",
    "management",
    "evaluation",
    "approach",
    "overview",
}

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


@dataclass(frozen=True)
class Entry:
    source: str
    entry_id: str
    title: str
    normalized_title: str
    path: str


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def clean_diagnosis(text: str) -> str:
    text = norm(text)
    if "appendicitis" in text and "peritonitis" in text:
        text = text.replace("peritonitis", " ")
    replacements = [
        ("without mention of", " "),
        ("not elsewhere classified", " "),
        ("without intrauterine pregnancy", "ectopic pregnancy"),
        ("without myelopathy", " "),
        ("without obstruction", " "),
        ("with obstruction", " "),
        ("with intoxication", " intoxication "),
        ("and abscess", " abscess "),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    tokens = [tok for tok in text.split() if tok not in STOPWORDS]
    return " ".join(tokens)


def content_tokens(text: str) -> list[str]:
    return [tok for tok in clean_diagnosis(text).split() if tok]


def extract_mayo_title(text: str) -> str:
    for line in (line.strip() for line in text.splitlines() if line.strip()):
        if line.startswith("http") or line in BOILERPLATE_MAYO:
            continue
        return line
    return ""


def local_entries() -> list[Entry]:
    entries: list[Entry] = []

    for item in json.loads(MAYO_PATH.read_text(encoding="utf-8")):
        title = extract_mayo_title(item.get("text", ""))
        if title:
            entries.append(
                Entry(
                    source="mayoclinic",
                    entry_id=str(item.get("id")),
                    title=title,
                    normalized_title=clean_diagnosis(title),
                    path=str(MAYO_PATH),
                )
            )

    for txt_file in sorted(UTD_DIR.glob("*.txt")):
        with txt_file.open(encoding="utf-8", errors="ignore") as handle:
            first_line = handle.readline().strip()
        if first_line:
            entries.append(
                Entry(
                    source="uptodate",
                    entry_id=txt_file.name,
                    title=first_line,
                    normalized_title=clean_diagnosis(first_line),
                    path=str(txt_file),
                )
            )

    return entries


def strict_aliases(diagnosis: str) -> list[str]:
    normalized = norm(diagnosis)
    cleaned = clean_diagnosis(diagnosis)
    tokens = content_tokens(diagnosis)
    aliases: list[str] = []

    if cleaned:
        aliases.append(cleaned)

    if len(tokens) == 1:
        aliases.extend(tokens)
    else:
        aliases.extend(" ".join(tokens[i:j]) for i in range(len(tokens)) for j in range(i + 2, len(tokens) + 1))

    # Conservative canonical synonyms only. No symptom-level expansions such as sore throat.
    if "acute infective polyneuritis" in normalized:
        aliases += ["guillain barre syndrome"]
    if "achalasia" in normalized or "cardiospasm" in normalized:
        aliases += ["achalasia"]
    if "pharyngitis" in normalized:
        aliases += ["acute pharyngitis", "pharyngitis", "streptococcal pharyngitis"]
    if "appendicitis" in normalized:
        aliases += ["acute appendicitis", "appendicitis"]
    if "pericarditis" in normalized:
        aliases += ["acute pericarditis", "pericarditis"]
    if "pyelonephritis" in normalized:
        aliases += ["pyelonephritis"]
    if "diverticulitis" in normalized:
        aliases += ["diverticulitis"]
    if "mononucleosis" in normalized:
        aliases += ["infectious mononucleosis"]
    if "lyme" in normalized:
        aliases += ["lyme disease"]
    if "paronychia" in normalized or "onychia" in normalized:
        aliases += ["paronychia"]
    if "sinusitis" in normalized:
        aliases += ["sinusitis"]
    if "epistaxis" in normalized:
        aliases += ["epistaxis"]
    if "otitis" in normalized:
        aliases += ["otitis externa", "otitis media"]
    if "cellulitis" in normalized:
        aliases += ["cellulitis"]
    if "pilonidal" in normalized and "abscess" in normalized:
        aliases += ["pilonidal cyst"]
    if "pulmonary embol" in normalized:
        aliases += ["pulmonary embolism"]
    if "vertebral artery dissection" in normalized:
        aliases += ["vertebral artery dissection"]
    if "transient cerebral ischemia" in normalized:
        aliases += ["transient ischemic attack"]
    if "cerebral artery occlusion" in normalized or "stroke" in normalized:
        aliases += ["stroke", "cerebral ischemia"]
    if "kidney" in normalized or "ureter" in normalized or "renal colic" in normalized or "hydronephrosis" in normalized:
        aliases += ["nephrolithiasis", "ureteral stone", "kidney stones"]
    if "gallbladder" in normalized or "cholecystitis" in normalized:
        aliases += ["cholecystitis"]
    if "hernia" in normalized:
        aliases += ["umbilical hernia", "hernia"]

    deduped: list[str] = []
    seen = set()
    for alias in aliases:
        alias = clean_diagnosis(alias)
        if alias and alias not in seen:
            seen.add(alias)
            deduped.append(alias)

    deduped.sort(key=lambda value: (-len(value.split()), -len(value)))
    return deduped


def score_strict_match(diagnosis: str, entry: Entry) -> dict | None:
    diagnosis_clean = clean_diagnosis(diagnosis)
    diagnosis_tokens = set(content_tokens(diagnosis))
    title_clean = entry.normalized_title
    title_tokens = set(title_clean.split())
    if not title_clean:
        return None

    matched_alias = None
    alias_score = -1.0
    for alias in strict_aliases(diagnosis):
        if alias == title_clean:
            score = 4.0
        elif alias and (alias in title_clean or title_clean in alias):
            score = 3.0 + min(0.5, 0.1 * max(len(alias.split()) - 1, 0))
        else:
            continue
        if score > alias_score:
            alias_score = score
            matched_alias = alias

    shared_tokens = sorted(diagnosis_tokens & title_tokens)
    overlap = len(shared_tokens) / len(diagnosis_tokens) if diagnosis_tokens else 0.0
    precision = len(shared_tokens) / len(title_tokens) if title_tokens else 0.0
    ratio = SequenceMatcher(None, diagnosis_clean, title_clean).ratio()

    if matched_alias is None and not (overlap >= 0.75 and ratio >= 0.55):
        return None

    final_score = alias_score if alias_score >= 0 else (1.2 * overlap + 0.6 * precision + 0.4 * ratio)
    return {
        "score": round(final_score, 4),
        "match_type": "exact" if matched_alias == title_clean else "very_close",
        "matched_alias": matched_alias or "",
        "shared_tokens": ", ".join(shared_tokens),
        "source": entry.source,
        "entry_id": entry.entry_id,
        "entry_title": entry.title,
        "entry_path": entry.path,
    }


def build_indexes(entries: list[Entry]) -> tuple[dict[str, list[Entry]], dict[str, list[Entry]]]:
    token_index: dict[str, list[Entry]] = defaultdict(list)
    title_index: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        title_index[entry.normalized_title].append(entry)
        for token in set(entry.normalized_title.split()):
            token_index[token].append(entry)
    return token_index, title_index


def candidate_entries(diagnosis: str, entries: list[Entry], token_index: dict[str, list[Entry]], title_index: dict[str, list[Entry]]) -> list[Entry]:
    candidates: dict[tuple[str, str], Entry] = {}

    for alias in strict_aliases(diagnosis):
        for entry in title_index.get(alias, []):
            candidates[(entry.source, entry.entry_id)] = entry

        for token in alias.split():
            if len(token) <= 2:
                continue
            for entry in token_index.get(token, []):
                candidates[(entry.source, entry.entry_id)] = entry

    for token in content_tokens(diagnosis):
        if len(token) <= 2:
            continue
        for entry in token_index.get(token, []):
            candidates[(entry.source, entry.entry_id)] = entry

    return list(candidates.values()) or entries


def best_strict_match(
    diagnosis: str,
    entries: list[Entry],
    token_index: dict[str, list[Entry]],
    title_index: dict[str, list[Entry]],
) -> dict | None:
    candidates = []
    for entry in candidate_entries(diagnosis, entries, token_index, title_index):
        match = score_strict_match(diagnosis, entry)
        if match is not None:
            candidates.append(match)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item["score"],
            len(item["matched_alias"].split()),
            len(item["shared_tokens"].split(", ")) if item["shared_tokens"] else 0,
            -len(item["entry_title"]),
        ),
        reverse=True,
    )
    return candidates[0]


def main() -> None:
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    entries = local_entries()
    token_index, title_index = build_indexes(entries)
    rows: list[dict] = []

    for item in report["diagnoses"]:
        if item["is_wrong_diagnosis"]:
            continue

        best = best_strict_match(item["diagnosis"], entries, token_index, title_index)
        if best is None:
            continue

        rows.append(
            {
                "diagnosis": item["diagnosis"],
                "count_in_file": item["count_in_file"],
                "scenario_ids": ",".join(str(sid) for sid in item["scenario_ids"]),
                "strict_match_type": best["match_type"],
                "strict_matched_alias": best["matched_alias"],
                "strict_match_score": best["score"],
                "guideline_source": best["source"],
                "guideline_title": best["entry_title"],
                "guideline_id": best["entry_id"],
                "guideline_path": best["entry_path"],
                "shared_tokens": best["shared_tokens"],
                "original_mayoclinic_title": (item.get("mayoclinic_match") or {}).get("title", ""),
                "original_uptodate_title": (item.get("uptodate_match") or {}).get("title", ""),
            }
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "diagnosis",
                "count_in_file",
                "scenario_ids",
                "strict_match_type",
                "strict_matched_alias",
                "strict_match_score",
                "guideline_source",
                "guideline_title",
                "guideline_id",
                "guideline_path",
                "shared_tokens",
                "original_mayoclinic_title",
                "original_uptodate_title",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(OUTPUT_CSV)
    print(f"rows={len(rows)}")


if __name__ == "__main__":
    main()
