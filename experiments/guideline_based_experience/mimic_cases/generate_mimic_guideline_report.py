from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path


REPO = Path("/Users/xiaofanlu/Documents/github_repos/uncertainty-aware-reasoning-agent")
INPUT_PATH = REPO / (
    "benchmarks/AgentClinic/experiment_highest_transfer_clusters/results/"
    "gpt5_nano_on_mimic_with_mimic_prompt/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804.jsonl"
)
OUTPUT_PATH = REPO / (
    "experiments/guideline_based_experience/mimic_cases/"
    "agentclinic_mimiciv_openai_gpt-5-nano_selected_20260329_133804_unique_diagnosis_guideline_report.json"
)
MAYO_PATH = REPO / "experiments/guideline_based_experience/mayoclinical.json"
UTD_DIR = REPO / "experiments/guideline_based_experience/结果"

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

WRONG_DIAGNOSIS_PREFIX = "The findings do not strongly indicate a specific acute pathology"
GENERIC_SINGLETON_ALIASES = {
    "pain",
    "disease",
    "disorder",
    "syndrome",
    "abuse",
    "intoxication",
    "fracture",
    "cellulitis",
    "abscess",
    "artery",
    "cancer",
    "neoplasm",
}


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def extract_mayo_title(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if line.startswith("http") or line in BOILERPLATE_MAYO:
            continue
        return line
    return ""


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


def diagnosis_aliases(diagnosis: str) -> list[str]:
    n = norm(diagnosis)
    cleaned = clean_diagnosis(diagnosis)
    toks = content_tokens(diagnosis)
    aliases: list[str] = []
    if cleaned:
        aliases.append(cleaned)
    aliases.extend(toks)
    aliases.extend(" ".join(toks[i : i + 2]) for i in range(len(toks) - 1))
    aliases.extend(" ".join(toks[i : i + 3]) for i in range(len(toks) - 2))

    if "chest pain" in n:
        aliases += ["chest pain"]
    if "appendicitis" in n:
        aliases += ["appendicitis"]
    if "cellulitis" in n and "abscess" in n:
        aliases += ["cellulitis and skin abscess", "cellulitis", "skin abscess"]
    elif "cellulitis" in n:
        aliases += ["cellulitis"]
    if "pharyngitis" in n or "sore throat" in n or "tonsillitis" in n:
        aliases += ["pharyngitis", "streptococcal pharyngitis", "sore throat", "tonsillitis"]
    if "alcohol abuse" in n or "alcohol" in n:
        aliases += [
            "alcohol use disorder",
            "alcohol intoxication",
            "ethanol intoxication",
            "alcohol withdrawal",
            "alcohol",
        ]
    if "depressive" in n or "major depressive" in n:
        aliases += ["depression", "major depressive disorder"]
    if "suicidal ideation" in n:
        aliases += ["suicidal ideation", "suicide risk"]
    if "anxiety" in n:
        aliases += ["anxiety disorder", "anxiety"]
    if "atrial fibrillation" in n:
        aliases += ["atrial fibrillation"]
    if "vertigo" in n or "dizziness" in n:
        aliases += ["vertigo", "dizziness"]
    if "migraine" in n or "hemicrania" in n or "occipital neuralgia" in n:
        aliases += ["headache", "migraine", "occipital neuralgia", "hemicrania"]
    if "epile" in n or "convuls" in n or "seizure" in n:
        aliases += ["seizure"]
    if "meningitis" in n:
        aliases += ["meningitis"]
    if "myelitis" in n or "polyneuritis" in n:
        aliases += ["myelitis", "guillain barre syndrome"]
    if "diabetes" in n:
        aliases += ["diabetes mellitus", "type 2 diabetes"]
    if "thyroid" in n or "goiter" in n:
        aliases += ["thyroid cancer", "thyroid disease", "hyperthyroidism"]
    if "kidney" in n or "ureter" in n or "renal colic" in n or "hydronephrosis" in n:
        aliases += ["kidney stones", "ureteral stone", "nephrolithiasis", "renal colic"]
    if "pyelonephritis" in n:
        aliases += ["pyelonephritis"]
    if (
        "pregnancy" in n
        or "tubal" in n
        or "premature labor" in n
        or "uterus" in n
        or "ovary" in n
        or "vaginosis" in n
    ):
        aliases += ["ectopic pregnancy", "preterm labor", "bacterial vaginosis", "uterine fibroids", "ovarian cyst"]
    if "gallbladder" in n or "bile duct" in n or "cholecystitis" in n:
        aliases += ["cholecystitis", "gallstones"]
    if "diverticulitis" in n:
        aliases += ["diverticulitis"]
    if "ulcerative" in n or "enterocolitis" in n or "gastroenteritis" in n or "colitis" in n:
        aliases += ["ulcerative colitis", "colitis", "gastroenteritis"]
    if "peptic ulcer" in n:
        aliases += ["peptic ulcer disease"]
    if "umbilical hernia" in n or "intestinal obstruction" in n:
        aliases += ["bowel obstruction", "umbilical hernia"]
    if "hernia" in n:
        aliases += ["hernia"]
    if "pericarditis" in n:
        aliases += ["pericarditis"]
    if "pulmonary embol" in n or "deep vessels of lower extremity" in n or "venous embolism" in n:
        aliases += ["pulmonary embolism", "deep vein thrombosis"]
    if "carotid" in n:
        aliases += ["carotid artery stenosis", "carotid artery disease"]
    if "cerebral artery occlusion" in n or "transient cerebral ischemia" in n or "stroke" in n:
        aliases += ["stroke", "transient ischemic attack", "cerebral ischemia"]
    if "vertebral artery dissection" in n:
        aliases += ["vertebral artery dissection"]
    if "pneumonia" in n:
        aliases += ["pneumonia"]
    if "emphysema" in n or "respiratory abnormalities" in n:
        aliases += ["pneumothorax", "emphysema", "shortness of breath"]
    if "psychosis" in n or "schizophrenia" in n or "schizoaffective" in n or "bipolar" in n:
        aliases += ["psychosis", "schizophrenia", "schizoaffective disorder", "bipolar disorder"]
    if "backache" in n or "lumbago" in n or "disc" in n or "spondylosis" in n or "fracture" in n:
        aliases += ["back pain", "lumbar disc herniation", "cervical radiculopathy", "vertebral fracture"]
    if "lyme" in n:
        aliases += ["lyme disease"]
    if "mononucleosis" in n:
        aliases += ["infectious mononucleosis"]
    if "abscess" in n and "pilonidal" in n:
        aliases += ["pilonidal cyst"]
    if "otitis" in n:
        aliases += ["otitis externa", "otitis media"]
    if "sinusitis" in n:
        aliases += ["sinusitis"]
    if "epistaxis" in n:
        aliases += ["nosebleeds", "epistaxis"]
    if "paronychia" in n or "onychia" in n:
        aliases += ["paronychia"]
    if "testis" in n:
        aliases += ["testicular torsion"]
    if "achalasia" in n:
        aliases += ["achalasia"]
    if "syncope" in n:
        aliases += ["syncope"]

    seen = set()
    deduped = []
    for alias in aliases:
        alias = clean_diagnosis(alias)
        if len(alias.split()) == 1 and alias in GENERIC_SINGLETON_ALIASES and len(toks) > 1:
            continue
        if alias and alias not in seen:
            seen.add(alias)
            deduped.append(alias)
    deduped.sort(key=lambda x: (-len(x.split()), -len(x)))
    return deduped


def local_entries() -> tuple[list[dict], list[dict]]:
    mayo_entries = []
    for item in json.loads(MAYO_PATH.read_text(encoding="utf-8")):
        title = extract_mayo_title(item.get("text", ""))
        if title:
            mayo_entries.append(
                {
                    "source": "mayoclinic",
                    "id": item.get("id"),
                    "title": title,
                    "normalized_title": clean_diagnosis(title),
                    "path": str(MAYO_PATH),
                    "url": None,
                }
            )

    utd_entries = []
    for txt_file in sorted(UTD_DIR.glob("*.txt")):
        with txt_file.open(encoding="utf-8", errors="ignore") as handle:
            first_line = handle.readline().strip()
        if first_line:
            utd_entries.append(
                {
                    "source": "uptodate",
                    "id": txt_file.name,
                    "title": first_line,
                    "normalized_title": clean_diagnosis(first_line),
                    "path": str(txt_file),
                    "url": None,
                }
            )
    return mayo_entries, utd_entries


def score_match(diagnosis: str, entry: dict, aliases: list[str]) -> tuple[float, list[str], str]:
    diag_tokens = set(content_tokens(diagnosis))
    title_tokens = set(entry["normalized_title"].split())
    if not title_tokens:
        return 0.0, [], ""

    common = sorted(diag_tokens & title_tokens)
    overlap = len(common) / len(diag_tokens) if diag_tokens else 0.0
    precision = len(common) / len(title_tokens) if title_tokens else 0.0
    ratio = SequenceMatcher(None, clean_diagnosis(diagnosis), entry["normalized_title"]).ratio()

    phrase_score = 0.0
    matched_alias = ""
    for alias in aliases:
        alias_len = len(alias.split())
        alias_bonus = min(0.08, 0.02 * max(alias_len - 1, 0))
        if alias == entry["normalized_title"]:
            candidate = 1.0 + alias_bonus
        elif alias and alias in entry["normalized_title"]:
            candidate = 0.88 + alias_bonus
        elif alias and entry["normalized_title"] in alias:
            candidate = 0.82 + alias_bonus
        else:
            continue
        if candidate > phrase_score or (candidate == phrase_score and len(alias) > len(matched_alias)):
            phrase_score = candidate
            matched_alias = alias

    lead_bonus = 0.08 if aliases and aliases[0] and entry["normalized_title"].startswith(aliases[0]) else 0.0
    score = max(phrase_score + lead_bonus, 0.60 * overlap + 0.25 * precision + 0.15 * ratio + lead_bonus)
    return round(score, 4), common, matched_alias


def pick_best_match(diagnosis: str, entries: list[dict]) -> dict | None:
    aliases = diagnosis_aliases(diagnosis)
    best = None
    for entry in entries:
        score, common, matched_alias = score_match(diagnosis, entry, aliases)
        if score < 0.40:
            continue
        candidate = {
            "score": score,
            "shared_tokens": common,
            "matched_alias": matched_alias or None,
            **entry,
        }
        candidate_rank = (
            candidate["score"],
            len(candidate["shared_tokens"]),
            len((candidate["matched_alias"] or "").split()),
            int(candidate["title"].lower().startswith(clean_diagnosis(diagnosis))),
            -len(candidate["title"]),
        )
        if best is None:
            best = candidate
            best["_rank"] = candidate_rank
        elif candidate_rank > best["_rank"]:
            best = candidate
            best["_rank"] = candidate_rank
    if best is not None:
        best.pop("_rank", None)
        best["match_strength"] = "strong" if best["score"] >= 0.85 else "moderate" if best["score"] >= 0.60 else "weak"
    return best


def is_wrong_diagnosis(diagnosis: str) -> tuple[bool, str | None]:
    if diagnosis.startswith(WRONG_DIAGNOSIS_PREFIX):
        return True, "Ground-truth label is a narrative assessment/plan rather than a disease or syndrome name."
    if len(diagnosis.split()) > 25 and any(
        phrase in diagnosis.lower() for phrase in ["recommended", "watchful waiting", "return or seek further care"]
    ):
        return True, "Diagnosis text is sentence-like clinical advice, not a canonical diagnosis label."
    return False, None


def specialty_sources(diagnosis: str) -> list[str]:
    n = norm(diagnosis)
    if any(k in n for k in ["cellulitis", "abscess", "pharyngitis", "tonsillitis", "pneumonia", "meningitis", "pyelonephritis", "vaginosis", "mononucleosis", "lyme"]):
        return ["IDSA", "CDC", "NICE", "UpToDate"]
    if any(k in n for k in ["chest pain", "atrial fibrillation", "pericarditis", "pulmonary embol", "venous embol", "carotid", "cerebral", "ischemia", "stroke", "dissection"]):
        return ["AHA/ACC", "ESC", "CHEST", "NICE"]
    if any(k in n for k in ["appendicitis", "diverticulitis", "gallbladder", "bile duct", "cholecystitis", "ulcerative", "colitis", "gastroenteritis", "achalasia", "hernia", "intestinal obstruction", "ulcer"]):
        return ["ACG/AGA", "ASCRS/SAGES/WSES", "NICE", "UpToDate"]
    if any(k in n for k in ["kidney", "ureter", "renal colic", "hydronephrosis"]):
        return ["AUA", "EAU", "NICE", "UpToDate"]
    if any(k in n for k in ["pregnancy", "tubal", "premature labor", "uterus", "ovary"]):
        return ["ACOG", "RCOG", "SMFM", "NICE"]
    if any(k in n for k in ["depressive", "anxiety", "suicidal", "psychosis", "schiz", "bipolar", "opioid abuse", "alcohol abuse"]):
        return ["APA", "VA/DoD", "NICE", "SAMHSA"]
    if any(k in n for k in ["diabetes", "goiter", "thyroid", "endocrine"]):
        return ["ADA", "AACE/Endocrine Society", "ATA", "NICE"]
    if any(k in n for k in ["disc", "spondylosis", "backache", "lumbago", "fracture", "vertigo", "hemicrania", "migraine", "neuralgia", "convulsions", "myelitis", "polyneuritis"]):
        return ["AAN", "ACP/AAOS/NASS", "NICE", "UpToDate"]
    if any(k in n for k in ["malignant neoplasm", "cancer", "neoplasm"]):
        return ["NCCN", "ASCO", "organ-specific society guideline", "UpToDate"]
    return ["NICE", "UpToDate", "Mayo Clinic", "specialty society guideline"]


def recommended_query(diagnosis: str) -> str:
    wrong, _ = is_wrong_diagnosis(diagnosis)
    if wrong:
        return "No query suggested because the label is not a valid diagnosis."
    aliases = diagnosis_aliases(diagnosis)
    anchor = aliases[0] if aliases else clean_diagnosis(diagnosis) or norm(diagnosis)
    source = specialty_sources(diagnosis)[0].split("/")[0].lower()
    return f"\"{anchor}\" guideline OR consensus OR society guideline site:{source}.org"


def main() -> None:
    by_dx: dict[str, dict[str, object]] = {}
    with INPUT_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            dx = row["correct_diagnosis"].strip()
            by_dx.setdefault(dx, {"count": 0, "scenario_ids": []})
            by_dx[dx]["count"] += 1
            by_dx[dx]["scenario_ids"].append(row["scenario_id"])

    mayo_entries, utd_entries = local_entries()
    results = []
    summary_counter = Counter()

    for diagnosis in sorted(by_dx):
        wrong, wrong_reason = is_wrong_diagnosis(diagnosis)
        mayo_match = None if wrong else pick_best_match(diagnosis, mayo_entries)
        utd_match = None if wrong else pick_best_match(diagnosis, utd_entries)
        found_any = mayo_match is not None or utd_match is not None

        if wrong:
            status = "wrong_diagnosis_label"
            summary_counter["wrong"] += 1
        elif found_any:
            status = "local_guideline_found"
            summary_counter["matched"] += 1
        else:
            status = "no_local_guideline_found"
            summary_counter["unmatched"] += 1

        results.append(
            {
                "diagnosis": diagnosis,
                "count_in_file": by_dx[diagnosis]["count"],
                "scenario_ids": by_dx[diagnosis]["scenario_ids"],
                "is_wrong_diagnosis": wrong,
                "wrong_reason": wrong_reason,
                "local_guideline_status": status,
                "local_guideline_note": (
                    "No diagnosis-level guideline is expected for a malformed narrative label."
                    if wrong
                    else (
                        "Local concept-level match found; this is not guaranteed to be an exact ICD-label match."
                        if found_any
                        else "No convincing Mayo Clinic or UpToDate match found in the local corpus."
                    )
                ),
                "mayoclinic_match": mayo_match,
                "uptodate_match": utd_match,
                "online_search_plan": {
                    "recommended_query": recommended_query(diagnosis),
                    "preferred_sources": specialty_sources(diagnosis),
                    "fallback_strategy": (
                        "Search the disease name plus guideline and the organ-specific society name; "
                        "if nothing authoritative appears, search NICE, CDC, or specialty-society "
                        "guideline hubs, then UpToDate/Mayo for review articles."
                    ),
                },
            }
        )

    payload = {
        "source_file": str(INPUT_PATH),
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "unique_diagnosis_count": len(results),
            "wrong_diagnosis_count": summary_counter["wrong"],
            "local_guideline_found_count": summary_counter["matched"],
            "no_local_guideline_found_count": summary_counter["unmatched"],
            "wrong_diagnoses": [item["diagnosis"] for item in results if item["is_wrong_diagnosis"]],
        },
        "diagnoses": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(OUTPUT_PATH)
    print(json.dumps(payload["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
