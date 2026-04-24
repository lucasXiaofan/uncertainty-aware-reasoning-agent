#!/usr/bin/env python3
"""Build an ICD-10-CM chapter coverage report for AgentClinic MIMIC-IV cases."""

from __future__ import annotations

import json
import re
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RUN_PATH = ROOT / "experiments/guideline_based_experience/mimic_cases/gpt5_nano_on_mimic_with_mimic_prompt/agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl"
ICD_CODES_PATH = ROOT / "experiments/train_test_creation/icd_coverage_check/data/Code Descriptions/icd10cm_codes_2026.txt"
REPORT_PATH = ROOT / "experiments/train_test_creation/icd_coverage_check/mimiciv_icd10cm_coverage_report.md"
MATCHES_PATH = ROOT / "experiments/train_test_creation/icd_coverage_check/mimiciv_icd10cm_matches.json"


CHAPTERS = [
    ("A00", "B99", "Certain infectious and parasitic diseases"),
    ("C00", "D49", "Neoplasms"),
    ("D50", "D89", "Diseases of the blood and immune mechanism"),
    ("E00", "E89", "Endocrine, nutritional and metabolic diseases"),
    ("F01", "F99", "Mental, behavioral and neurodevelopmental disorders"),
    ("G00", "G99", "Diseases of the nervous system"),
    ("H00", "H59", "Diseases of the eye and adnexa"),
    ("H60", "H95", "Diseases of the ear and mastoid process"),
    ("I00", "I99", "Diseases of the circulatory system"),
    ("J00", "J99", "Diseases of the respiratory system"),
    ("K00", "K95", "Diseases of the digestive system"),
    ("L00", "L99", "Diseases of the skin and subcutaneous tissue"),
    ("M00", "M99", "Diseases of the musculoskeletal system and connective tissue"),
    ("N00", "N99", "Diseases of the genitourinary system"),
    ("O00", "O9A", "Pregnancy, childbirth and the puerperium"),
    ("P00", "P96", "Certain conditions originating in the perinatal period"),
    ("Q00", "Q99", "Congenital malformations, deformations and chromosomal abnormalities"),
    ("R00", "R99", "Symptoms, signs and abnormal clinical and laboratory findings"),
    ("S00", "T88", "Injury, poisoning and certain other consequences of external causes"),
    ("U00", "U85", "Codes for special purposes"),
    ("V00", "Y99", "External causes of morbidity"),
    ("Z00", "Z99", "Factors influencing health status and contact with health services"),
]

COMMON_MISSING_CHAPTER_EXAMPLES = {
    "Diseases of the blood and immune mechanism": [
        "Iron deficiency anemia",
        "Vitamin B12 deficiency anemia",
        "Sickle-cell disease",
        "Thrombocytopenia",
        "Neutropenia",
    ],
    "Diseases of the eye and adnexa": [
        "Conjunctivitis",
        "Cataract",
        "Glaucoma",
        "Retinal detachment",
        "Diabetic retinopathy",
    ],
    "Certain conditions originating in the perinatal period": [
        "Neonatal jaundice",
        "Respiratory distress of newborn",
        "Birth asphyxia",
        "Neonatal sepsis",
        "Prematurity/low birth weight",
    ],
    "Codes for special purposes": [
        "Emergency-use code U07.1 COVID-19",
        "Post COVID-19 condition",
        "Other provisional special-purpose codes",
    ],
    "External causes of morbidity": [
        "Motor vehicle traffic accident",
        "Fall from stairs or steps",
        "Accidental poisoning exposure",
        "Assault-related injury mechanism",
        "Burn/fire exposure mechanism",
    ],
    "Factors influencing health status and contact with health services": [
        "Routine health examination",
        "Personal history of malignant neoplasm",
        "Long-term drug therapy",
        "Encounter for immunization",
        "Social determinants such as housing or food insecurity",
    ],
}

STOPWORDS = {
    "a",
    "and",
    "chronic",
    "condition",
    "due",
    "elsewhere",
    "except",
    "left",
    "mention",
    "not",
    "of",
    "or",
    "other",
    "right",
    "the",
    "to",
    "type",
    "uncontrolled",
    "unspecified",
    "with",
    "without",
}


# Explicit mappings are used where labels are ICD-9-CM legacy wording, narrative
# labels, or where a broad MIMIC label should roll up to a representative ICD-10-CM
# diagnosis for chapter coverage. The report marks these as manual mappings.
OVERRIDES = {
    "Acute appendicitis without mention of peritonitis": "K3580",
    "Acute infective polyneuritis": "G610",
    "Acute Pharyngitis": "J029",
    "Anaphylactic reaction due to unspecified food": "T7800XA",
    "Anomalies of other endocrine glands": "Q891",
    "Anxiety state, unspecified": "F419",
    "Alcohol abuse, unspecified": "F1010",
    "Backache, unspecified": "M549",
    "Bacterial Vaginosis": "N760",
    "Bacterial Pharyngitis": "J020",
    "Calculus of bile duct without mention of cholecystitis, without mention of obstruction": "K8050",
    "Calculus of gallbladder and bile duct with other cholecystitis, without mention of obstruction": "K8070",
    "Calculus of gallbladder with acute and chronic cholecystitis without obstruction": "K8012",
    "Calculus of gallbladder with acute cholecystitis, without mention of obstruction": "K8000",
    "Calculus of gallbladder with other cholecystitis, without mention of obstruction": "K8010",
    "Cellulitis and abscess of face": "L03211",
    "Cellulitis and abscess of finger, unspecified": "L03019",
    "Cellulitis and abscess of foot, except toes": "L03119",
    "Cellulitis and abscess of leg, except foot": "L03119",
    "Cellulitis and abscess of upper arm and forearm": "L03119",
    "Cerebral artery occlusion, unspecified with cerebral infarction": "I6320",
    "Depressive disorder, not elsewhere classified": "F329",
    "Diabetes Mellitus with possible Diabetic Neuropathy": "E1140",
    "Diabetes mellitus without mention of complication, type II or unspecified type, not stated as uncontrolled": "E119",
    "Displacement of cervical intervertebral disc without myelopathy": "M5020",
    "Displacement of lumbar intervertebral disc without myelopathy": "M5126",
    "Diverticulitis of colon (without mention of hemorrhage)": "K5732",
    "Epigastric abdominal pain likely due to Gallstones/Cholelithiasis": "K8020",
    "Interstitial Emphysema": "J982",
    "Lumbago": "M5450",
    "Malignant neoplasm of kidney, except pelvis": "C649",
    "Malignant neoplasm of left kidney, except renal pelvis": "C642",
    "Mononucleosis (Infectious mononucleosis caused by Epstein-Barr virus)": "B2700",
    "Occipital neuralgia": "M5481",
    "Occlusion and stenosis of carotid artery without mention of cerebral infarction": "I6529",
    "Onychia and paronychia of finger": "L03019",
    "Opioid abuse, continuous": "F1120",
    "Other and unspecified noninfectious gastroenteritis and colitis": "K529",
    "Other causes of myelitis": "G0491",
    "Other pulmonary embolism and infarction": "I2699",
    "Other respiratory abnormalities": "R0689",
    "Pathologic fracture of vertebrae": "M8448XA",
    "Peptic Ulcer Disease": "K279",
    "Pyelonephritis, unspecified": "N12",
    "Renal colic": "N23",
    "Streptococcal sore throat": "J020",
    "The findings do not strongly indicate a specific acute pathology and may be consistent with a non-specific viral illness or early presentation of a more specific illness. The normal range of most test results suggests that there is no immediate acute disease. Given the generalized symptoms and lack of specific findings, a conservative approach with symptomatic treatment and watchful waiting is recommended with instructions to return or seek further care if symptoms worsen or if more specific symptoms develop.": "B349",
    "Threatened premature labor, antepartum condition or complication": "O479",
    "Toxic diffuse goiter without mention of thyrotoxic crisis or storm": "E0500",
    "Type 2 Diabetes Mellitus with signs of hypertension and microalbuminuria": "E1129",
    "Ulcerative (chronic) enterocolitis": "K5190",
    "Unspecified intestinal obstruction": "K56609",
    "Unspecified psychosis possibly compounded by substance use (noting the positive opiate screen). However, thorough examination and history are required to exclude other organic causes.": "F29",
    "Unspecified sinusitis (chronic)": "J328",
}


@dataclass(frozen=True)
class IcdCode:
    code: str
    description: str
    norm: str


def normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("non-specific", "nonspecific")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = text.replace("without mention of", "without")
    text = text.replace("not elsewhere classified", "unspecified")
    text = text.replace("type ii or unspecified type, not stated as uncontrolled", "type 2")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def code_key(code: str) -> tuple[str, int]:
    match = re.match(r"([A-Z])(\d{2})", code)
    if not match:
        return code[:1], -1
    return match.group(1), int(match.group(2))


def code_in_range(code: str, start: str, end: str) -> bool:
    return code_key(start) <= code_key(code) <= code_key(end)


def chapter_for(code: str) -> str:
    letter, number = code_key(code)
    if letter in {"A", "B"}:
        return "Certain infectious and parasitic diseases"
    if letter == "C" or (letter == "D" and number <= 49):
        return "Neoplasms"
    if letter == "D" and number >= 50:
        return "Diseases of the blood and immune mechanism"
    if letter == "E":
        return "Endocrine, nutritional and metabolic diseases"
    if letter == "F":
        return "Mental, behavioral and neurodevelopmental disorders"
    if letter == "G":
        return "Diseases of the nervous system"
    if letter == "H" and number <= 59:
        return "Diseases of the eye and adnexa"
    if letter == "H" and number >= 60:
        return "Diseases of the ear and mastoid process"
    if letter == "I":
        return "Diseases of the circulatory system"
    if letter == "J":
        return "Diseases of the respiratory system"
    if letter == "K":
        return "Diseases of the digestive system"
    if letter == "L":
        return "Diseases of the skin and subcutaneous tissue"
    if letter == "M":
        return "Diseases of the musculoskeletal system and connective tissue"
    if letter == "N":
        return "Diseases of the genitourinary system"
    if letter == "O":
        return "Pregnancy, childbirth and the puerperium"
    if letter == "P":
        return "Certain conditions originating in the perinatal period"
    if letter == "Q":
        return "Congenital malformations, deformations and chromosomal abnormalities"
    if letter == "R":
        return "Symptoms, signs and abnormal clinical and laboratory findings"
    if letter in {"S", "T"}:
        return "Injury, poisoning and certain other consequences of external causes"
    if letter == "U":
        return "Codes for special purposes"
    if letter in {"V", "W", "X", "Y"}:
        return "External causes of morbidity"
    if letter == "Z":
        return "Factors influencing health status and contact with health services"
    return "Unmapped ICD-10-CM chapter"


def read_icd_codes() -> dict[str, IcdCode]:
    codes: dict[str, IcdCode] = {}
    for line in ICD_CODES_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        code, description = line[:8].strip(), line[8:].strip()
        codes[code] = IcdCode(code=code, description=description, norm=normalize(description))
    return codes


def read_rows() -> list[dict]:
    return [json.loads(line) for line in RUN_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_match(query_norm: str, icd: IcdCode) -> float:
    q_tokens = set(query_norm.split())
    i_tokens = set(icd.norm.split())
    if not q_tokens or not i_tokens:
        return 0.0
    overlap = len(q_tokens & i_tokens) / len(q_tokens | i_tokens)
    containment = len(q_tokens & i_tokens) / len(q_tokens)
    ratio = SequenceMatcher(None, query_norm, icd.norm).ratio()
    return 0.50 * containment + 0.30 * overlap + 0.20 * ratio


def content_tokens(norm_text: str) -> set[str]:
    return {token for token in norm_text.split() if len(token) > 2 and token not in STOPWORDS}


def match_diagnosis(diagnosis: str, codes: dict[str, IcdCode]) -> dict:
    if diagnosis in OVERRIDES:
        icd = codes[OVERRIDES[diagnosis]]
        return {
            "diagnosis": diagnosis,
            "code": icd.code,
            "icd10cm_description": icd.description,
            "chapter": chapter_for(icd.code),
            "match_method": "manual_legacy_or_narrative_mapping",
            "match_score": None,
        }

    query_norm = normalize(diagnosis)
    exact = [icd for icd in codes.values() if icd.norm == query_norm]
    if exact:
        icd = sorted(exact, key=lambda item: len(item.code))[0]
        return {
            "diagnosis": diagnosis,
            "code": icd.code,
            "icd10cm_description": icd.description,
            "chapter": chapter_for(icd.code),
            "match_method": "exact_normalized_description",
            "match_score": 1.0,
        }

    q_tokens = content_tokens(query_norm)
    candidates = [
        icd
        for icd in codes.values()
        if q_tokens and q_tokens & content_tokens(icd.norm)
    ]
    if not candidates:
        candidates = list(codes.values())
    # Keep SequenceMatcher work bounded by doing a cheap token-containment pass first.
    candidates = sorted(
        candidates,
        key=lambda item: len(q_tokens & content_tokens(item.norm)) / max(len(q_tokens), 1),
        reverse=True,
    )[:250]
    best = max(candidates, key=lambda item: score_match(query_norm, item))
    score = score_match(query_norm, best)
    return {
        "diagnosis": diagnosis,
        "code": best.code,
        "icd10cm_description": best.description,
        "chapter": chapter_for(best.code),
        "match_method": "fuzzy_description_match",
        "match_score": round(score, 3),
    }


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(out)


def scenario_link_list(items: list[dict]) -> str:
    return ", ".join(str(item["scenario_id"]) for item in sorted(items, key=lambda row: row["scenario_id"]))


def render_report(rows: list[dict], matches: dict[str, dict]) -> str:
    total = len(rows)
    false_rows = [row for row in rows if row.get("correct") is False]
    unique_dx = sorted({row["correct_diagnosis"] for row in rows}, key=str.lower)

    enriched = []
    for row in rows:
        match = matches[row["correct_diagnosis"]]
        enriched.append({**row, **match})

    by_chapter = defaultdict(list)
    by_false_chapter = defaultdict(list)
    for item in enriched:
        by_chapter[item["chapter"]].append(item)
        if item.get("correct") is False:
            by_false_chapter[item["chapter"]].append(item)

    chapter_rows = []
    false_count = Counter(item["chapter"] for item in enriched if item.get("correct") is False)
    for chapter, items in sorted(by_chapter.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        chapter_rows.append([
            chapter,
            len(items),
            f"{len(items) / total:.1%}",
            false_count[chapter],
            f"{false_count[chapter] / len(items):.1%}",
            len({item["correct_diagnosis"] for item in items}),
        ])

    missing_chapters = [name for _, _, name in CHAPTERS if name not in by_chapter]
    false_missing_chapters = [name for _, _, name in CHAPTERS if name not in by_false_chapter]

    missing_examples = [
        [
            chapter,
            ", ".join(COMMON_MISSING_CHAPTER_EXAMPLES.get(chapter, ["No examples listed"])),
        ]
        for chapter in missing_chapters
    ]

    lines = [
        "# MIMIC-IV ICD-10-CM Coverage Report",
        "",
        f"Input run: `{RUN_PATH.relative_to(ROOT)}`",
        "",
        "ICD source downloaded for matching: CMS/CDC `april-1-2026-code-descriptions-tabular-order.zip`, "
        "using `icd10cm_codes_2026.txt` from the extracted Code Descriptions directory. CMS lists this as the "
        "April 1, 2026 ICD-10-CM code description release for encounters from April 1, 2026 through September 30, 2026.",
        "",
        "Online references checked before download:",
        "",
        "- CMS ICD-10 files page: https://www.cms.gov/medicare/coding-billing/icd-10-codes",
        "- CDC ICD-10-CM files page: https://www.cdc.gov/nchs/icd/icd-10-cm/files.html",
        "- CDC ICD-10-CM overview/browser reference: https://www.cdc.gov/nchs/icd/icd-10-cm/index.html",
        "",
        "## Method",
        "",
        "- Treated the case `correct_diagnosis` label as the target diagnosis.",
        "- Matched each unique label to a billable ICD-10-CM diagnosis code from the downloaded CMS code description file.",
        "- Used exact normalized title matching where possible; used explicit manual mappings for ICD-9-CM legacy wording and narrative labels; used fuzzy description matching only for remaining labels.",
        "- Rolled the matched ICD-10-CM code up to ICD-10-CM chapter ranges.",
        "- Counts are case counts, not unique diagnosis counts, unless explicitly stated.",
        "",
        "## Summary",
        "",
        md_table(
            ["Metric", "Value"],
            [
                ["Total cases", total],
                ["Incorrect model cases (`correct: false`)", len(false_rows)],
                ["Correct model cases", total - len(false_rows)],
                ["Unique diagnosis labels", len(unique_dx)],
                ["ICD-10-CM chapters represented", f"{len(by_chapter)} / {len(CHAPTERS)}"],
                ["ICD-10-CM chapters represented among incorrect cases", f"{len(by_false_chapter)} / {len(CHAPTERS)}"],
            ],
        ),
        "",
        "## Top Missing ICD Chapter Coverage",
        "",
        "The 200-case set does not cover these ICD-10-CM chapters at all. The examples are common diagnosis or coding targets that could be added to improve chapter-level coverage.",
        "",
        md_table(["Uncovered ICD-10-CM chapter", "Common diagnosis/code examples to add"], missing_examples),
        "",
        "## Overall ICD-10-CM Chapter Distribution",
        "",
        md_table(
            ["ICD-10-CM chapter", "Cases", "% of 200", "Incorrect cases", "Incorrect rate in chapter", "Unique diagnoses"],
            chapter_rows,
        ),
        "",
        "## Incorrect-Case ICD-10-CM Chapter Distribution",
        "",
    ]

    false_rows_table = []
    for chapter, items in sorted(by_false_chapter.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        false_rows_table.append([
            chapter,
            len(items),
            f"{len(items) / len(false_rows):.1%}",
            scenario_link_list(items),
        ])
    lines += [md_table(["ICD-10-CM chapter", "Incorrect cases", "% of 117 incorrect", "Scenario ids"], false_rows_table), ""]

    lines += [
        "## Chapter Details",
        "",
        "Each row below shows the scenario ids, original MIMIC diagnosis labels, and matched ICD-10-CM diagnosis codes for the chapter.",
        "",
    ]
    for chapter, items in sorted(by_chapter.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        diagnosis_groups = defaultdict(list)
        for item in items:
            diagnosis_groups[(item["correct_diagnosis"], item["code"], item["icd10cm_description"])].append(item)
        detail_rows = []
        for (diagnosis, code, desc), group in sorted(diagnosis_groups.items(), key=lambda kv: (-len(kv[1]), kv[0][0].lower())):
            false_ids = [str(item["scenario_id"]) for item in sorted(group, key=lambda row: row["scenario_id"]) if item.get("correct") is False]
            detail_rows.append([
                len(group),
                scenario_link_list(group),
                ", ".join(false_ids) if false_ids else "-",
                diagnosis,
                f"{code} - {desc}",
            ])
        lines += [f"### {chapter}", "", md_table(["Cases", "Scenario ids", "Incorrect scenario ids", "MIMIC diagnosis", "Matched ICD-10-CM diagnosis"], detail_rows), ""]

    lines += [
        "## Coverage Gaps And Example Needs",
        "",
        "For full chapter-level coverage across the ICD-10-CM tree, add at least one example in each chapter with zero cases in the 200-case set:",
        "",
    ]
    if missing_chapters:
        lines.append("\n".join(f"- {chapter}" for chapter in missing_chapters))
    else:
        lines.append("- No chapter-level gaps in the full 200-case set.")
    lines += [
        "",
        "Note: `External causes of morbidity`, `Factors influencing health status and contact with health services`, and `Codes for special purposes` are useful for full ICD-tree stress testing, but they are often secondary/supporting codes rather than primary diagnosis targets.",
        "",
        "For failure-analysis coverage, add or surface incorrect examples in chapters that have no `correct: false` cases:",
        "",
    ]
    if false_missing_chapters:
        lines.append("\n".join(f"- {chapter}" for chapter in false_missing_chapters))
    else:
        lines.append("- No chapter-level gaps among incorrect cases.")

    low_volume = [
        (chapter, len(items))
        for chapter, items in by_chapter.items()
        if len(items) < 3
    ]
    low_volume = sorted(low_volume, key=lambda item: (item[1], item[0]))
    lines += [
        "",
        "Chapters represented by fewer than 3 examples are weakly covered and should receive more examples before treating the set as balanced:",
        "",
    ]
    lines.append("\n".join(f"- {chapter}: {count} case(s)" for chapter, count in low_volume) if low_volume else "- None.")

    high_error = [
        (chapter, len(items), false_count[chapter], false_count[chapter] / len(items))
        for chapter, items in by_chapter.items()
        if len(items) >= 3
    ]
    high_error = sorted(high_error, key=lambda item: (-item[3], -item[2], item[0]))
    lines += [
        "",
        "Among represented chapters with at least 3 cases, the categories most in need of additional training examples because of high error rates are:",
        "",
        md_table(
            ["ICD-10-CM chapter", "Cases", "Incorrect", "Incorrect rate"],
            [[chapter, cases, errors, f"{rate:.1%}"] for chapter, cases, errors, rate in high_error[:10]],
        ),
        "",
        "## Matching Audit",
        "",
        md_table(
            ["Method", "Unique diagnoses"],
            [[method, count] for method, count in Counter(match["match_method"] for match in matches.values()).most_common()],
        ),
        "",
        "Manual mappings are listed in `mimiciv_icd10cm_matches.json` for review. These are the main source of judgment because many source labels use legacy ICD-9 wording such as `without mention of`, `NEC`, or `except pelvis`.",
        "",
    ]

    return "\n".join(lines)


def main() -> None:
    rows = read_rows()
    codes = read_icd_codes()
    unique_dx = sorted({row["correct_diagnosis"] for row in rows}, key=str.lower)
    matches = {dx: match_diagnosis(dx, codes) for dx in unique_dx}
    MATCHES_PATH.write_text(json.dumps(matches, indent=2, sort_keys=True), encoding="utf-8")
    REPORT_PATH.write_text(render_report(rows, matches), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {MATCHES_PATH}")


if __name__ == "__main__":
    main()
