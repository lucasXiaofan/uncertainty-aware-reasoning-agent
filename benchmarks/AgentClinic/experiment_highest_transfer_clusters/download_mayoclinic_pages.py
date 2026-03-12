#!/usr/bin/env python3
"""Download and clean Mayo Clinic disease pages into JSON."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import random
import re
import time
from pathlib import Path
from typing import Any

import requests

DISEASES = [
    {
        "disease": "Hirschsprung's disease",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/hirschsprungs-disease/symptoms-causes/syc-20351556",
        "rank": 1,
        "selected": "",
    },
    {
        "disease": "Lung cancer",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/lung-cancer/symptoms-causes/syc-20374620",
        "rank": 2,
        "selected": 1,
    },
    {
        "disease": "Parkinson disease",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/parkinsons-disease/symptoms-causes/syc-20376055",
        "rank": 3,
        "selected": "",
    },
    {
        "disease": "Somatization disorder (Somatic symptom disorder)",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/somatic-symptom-disorder/symptoms-causes/syc-20377776",
        "rank": 4,
        "selected": 1,
    },
    {
        "disease": "MEN1",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/multiple-endocrine-neoplasia-type-1/symptoms-causes/syc-20353064",
        "rank": 5,
        "selected": 1,
    },
    {
        "disease": "Psoriatic arthritis",
        "symptoms_causes_url": "https://www.mayoclinic.org/diseases-conditions/psoriatic-arthritis/symptoms-causes/syc-20354076",
        "rank": 6,
        "selected": 1,
    },
]

STOP_HEADINGS = {
    "related",
    "request an appointment",
    "living with",
    "from mayo clinic to your inbox",
    "associated procedures",
    "products & services",
}


def build_fallback_diagnosis_treatment_url(symptoms_causes_url: str) -> str:
    url = symptoms_causes_url.replace("/symptoms-causes/", "/diagnosis-treatment/")
    url = url.replace("/syc-", "/drc-")
    return url


def clean_text(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", " ", fragment)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_main_article(html_text: str) -> str:
    main_article = re.search(
        r"<article[^>]*id=['\"]main-content['\"][^>]*>(.*?)</article>",
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if main_article:
        return main_article.group(1)

    first_article = re.search(
        r"<article[^>]*>(.*?)</article>", html_text, flags=re.IGNORECASE | re.DOTALL
    )
    return first_article.group(1) if first_article else html_text


def extract_title(html_text: str) -> str:
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if h1:
        return clean_text(h1.group(1))

    title = re.search(
        r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL
    )
    if title:
        return clean_text(title.group(1))
    return ""


def extract_clean_blocks(article_html: str) -> list[dict[str, str]]:
    cleaned = re.sub(
        r"<(script|style|noscript|svg|form|template)[^>]*>.*?</\1>",
        "",
        article_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    blocks: list[dict[str, str]] = []
    pattern = re.compile(r"<(h1|h2|h3|p|li)[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
    for match in pattern.finditer(cleaned):
        tag = match.group(1).lower()
        text = clean_text(match.group(2))
        if not text:
            continue
        blocks.append({"type": tag, "text": text})
    return blocks


def heading_level(tag: str) -> int:
    if tag.startswith("h") and len(tag) == 2 and tag[1].isdigit():
        return int(tag[1])
    return 99


def select_section(
    blocks: list[dict[str, str]], section_names: tuple[str, ...]
) -> list[dict[str, str]]:
    normalized_targets = tuple(s.lower() for s in section_names)
    section_start = -1
    start_level = 99

    for i, block in enumerate(blocks):
        if not block["type"].startswith("h"):
            continue
        heading = block["text"].strip().lower()
        if any(heading == t or heading.startswith(f"{t}:") for t in normalized_targets):
            section_start = i
            start_level = heading_level(block["type"])
            break

    if section_start == -1:
        return []

    selected = [blocks[section_start]]
    for block in blocks[section_start + 1 :]:
        if block["type"].startswith("h"):
            lvl = heading_level(block["type"])
            if lvl <= start_level:
                break
        selected.append(block)
    return selected


def trim_blocks(blocks: list[dict[str, str]]) -> list[dict[str, str]]:
    trimmed: list[dict[str, str]] = []
    for block in blocks:
        if block["type"].startswith("h"):
            heading = block["text"].strip().lower()
            if any(stop in heading for stop in STOP_HEADINGS):
                break
        trimmed.append(block)
    return trimmed


def blocks_to_text(blocks: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for block in blocks:
        tag = block["type"]
        text = block["text"]
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag in {"h2", "h3"}:
            lines.append(f"## {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    return "\n".join(lines).strip()


def resolve_diagnosis_url(
    symptoms_causes_url: str, symptoms_html: str, final_symptoms_url: str
) -> str:
    base_path = ""
    m = re.search(r"https?://[^/]+(/diseases-conditions/[^/]+)", final_symptoms_url)
    if m:
        base_path = m.group(1).lower()

    hrefs = re.findall(r'href=["\']([^"\']+)["\']', symptoms_html, flags=re.IGNORECASE)
    for href in hrefs:
        if "/diagnosis-treatment/" not in href:
            continue
        if href.startswith("http"):
            url = href
        else:
            url = f"https://www.mayoclinic.org{href}"
        if base_path and base_path in url.lower():
            return url
        if not base_path:
            return url

    return build_fallback_diagnosis_treatment_url(symptoms_causes_url)


def fetch_clean_page(
    session: requests.Session,
    url: str,
    retries: int,
    section_names: tuple[str, ...] | None = None,
    include_raw_html: bool = False,
) -> dict[str, Any]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(
                url, headers=headers, timeout=(10, 20), allow_redirects=True
            )
            html_text = response.text
            article_html = extract_main_article(html_text)
            blocks = extract_clean_blocks(article_html)
            if section_names:
                section_blocks = select_section(blocks, section_names)
                if section_blocks:
                    blocks = section_blocks
            blocks = trim_blocks(blocks)
            headings = [b["text"] for b in blocks if b["type"] in {"h1", "h2", "h3"}]
            clean_content = blocks_to_text(blocks)
            return {
                "source_url": url,
                "final_url": response.url,
                "status_code": response.status_code,
                "title": extract_title(html_text),
                "headings": headings,
                "clean_content": clean_content,
                "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
                "error": "",
                "raw_html": html_text if include_raw_html else "",
            }
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(1.5 * attempt)

    return {
        "source_url": url,
        "final_url": "",
        "status_code": None,
        "title": "",
        "headings": [],
        "clean_content": "",
        "fetched_at": dt.datetime.now(dt.UTC).isoformat(),
        "error": last_error or "Unknown request error",
        "raw_html": "",
    }


def run(output_path: Path, retries: int, sleep_seconds: float) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    records: list[dict[str, Any]] = []

    for item in DISEASES:
        sc_url = item["symptoms_causes_url"]
        sc_data = fetch_clean_page(
            session,
            sc_url,
            retries=retries,
            section_names=("Symptoms", "Signs and symptoms"),
            include_raw_html=True,
        )
        time.sleep(sleep_seconds + random.uniform(0.1, 0.7))
        diagnosis_url = resolve_diagnosis_url(
            sc_url, sc_data.get("raw_html", ""), sc_data["final_url"] or sc_url
        )
        dt_data = fetch_clean_page(
            session,
            diagnosis_url,
            retries=retries,
            section_names=("Diagnosis",),
        )
        sc_data.pop("raw_html", None)
        dt_data.pop("raw_html", None)
        time.sleep(sleep_seconds + random.uniform(0.1, 0.7))

        records.append(
            {
                "disease": item["disease"],
                "rank": item["rank"],
                "selected": item["selected"],
                "symptoms_causes": sc_data,
                "diagnosis_url": diagnosis_url,
                "diagnosis_treatment": dt_data,
            }
        )

    payload = {
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "source": "mayoclinic.org",
        "count": len(records),
        "records": records,
    }
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(records)} diseases to: {output_path}")


def main() -> None:
    default_output = (
        Path(__file__).resolve().parent
        / "med_resource"
        / "mayoclinic_disease_pages_clean.json"
    )
    parser = argparse.ArgumentParser(
        description=(
            "Download and clean Mayo Clinic symptoms-causes and diagnosis-treatment pages."
        )
    )
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args()
    run(args.output, retries=args.retries, sleep_seconds=args.sleep_seconds)


if __name__ == "__main__":
    main()
