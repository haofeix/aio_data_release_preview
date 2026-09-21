"""
Stage 2 (v2): Generate claim verification prompts for each keyword folder.

Differences from v1 (generate_verification_prompts.py):
  - Reads claims from claims_grok_4_1.json (was: claims.json)
  - Reads page content from page_analysis/<hash>.json (was: content/*.json)
  - Filters references via quality_audit_v2 classifier — only "good" pages
    are included (skipped/empty/captcha/nav_only/etc. are dropped)
  - Writes to verification_prompt_grok.txt (does not overwrite v1 output)

Usage:
    python generate_verification_prompts_v2.py --data_dir ../../work
    python generate_verification_prompts_v2.py --data_dir ../../work --dry_run
"""

import argparse
import json
import logging
import os
import sys
from glob import glob

# Pull in the v2 classifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quality_audit_v2 import classify  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

MIN_CONTENT_WORDS = 30
MAX_TOTAL_CONTENT_WORDS = 50000

PROMPT_TEMPLATE = """\
Objective:
You are a content representativeness checker. You analyze whether an AI Overview (AIO) faithfully represents the information from its cited reference sources.

You will be given a list of factual claims extracted from an AI Overview, along with the text content of all reference sources cited by that AI Overview. For each claim, determine which reference(s) are relevant, whether they support or contradict the claim, and assign one of the following labels:

  CLEAR: The claim is clearly and directly supported by the reference content.
  VAGUE: The claim is supported but the reference content describes it in broader or less precise terms.
  AMBIGUOUS: The reference sources contain contradictory information about the claim. For example, one source supports the claim while another contradicts it.
  INCORRECT: The reference content directly contradicts the claim.
  OMITTED: The reference content does not mention the claim at all.

Here are some examples of individual claim assessments:

Claim: "The Tesla Model 3 starts at $38,990 in the United States."
Reference: "The Model 3 rear-wheel drive variant has a base price of $38,990."
→ CLEAR — reference directly states the exact price.

Claim: "The iPhone 16 has an improved camera system."
Reference: "Apple's latest smartphone features several hardware upgrades."
→ VAGUE — reference mentions upgrades but not the camera specifically.

Claim: "The event will be held in New Orleans."
Reference 1: "...takes place at the Caesars Superdome in New Orleans."
Reference 2: "...scheduled for MetLife Stadium in New Jersey."
→ AMBIGUOUS — sources contradict each other.

Claim: "Python 4.0 was released in January 2026."
Reference: "There are currently no plans for a Python 4.0 release."
→ INCORRECT — reference directly contradicts the claim.

Claim: "The restaurant offers free parking."
Reference: "Open Monday–Saturday, serving Italian and Mediterranean cuisine."
→ OMITTED — reference does not mention parking at all.

Now verify ALL of the following claims against the reference sources below.

Keyword: "{keyword}"

Claims:
{claims_section}
Cited text snippets from the AI Overview (for additional context):
{cited_section}
Reference Sources:

{refs_section}Output ONLY a valid JSON array. Each element must have the following fields:
[
  {{
    "claim_id": 1,
    "claim": "<the claim text>",
    "label": "<CLEAR | VAGUE | AMBIGUOUS | INCORRECT | OMITTED>",
    "confidence": <0.0-1.0, how confident you are in this label>,
    "matched_references": ["R1", "R2"],
    "evidence": "<key phrase(s) from the reference that support your judgment>",
    "reasoning": "<brief explanation>"
  }},
  ...
]

Rules:
1. You MUST output exactly one entry per claim, in the same order as the claims above.
2. matched_references should list ALL reference IDs (R1, R2, etc.) that are relevant to the claim. Use an empty list [] for OMITTED.
3. evidence should quote or closely paraphrase the specific text from references. Use "No relevant content found" for OMITTED.
4. confidence reflects how clearly the references support your judgment (1.0 = unambiguous match/contradiction, 0.5 = borderline).
5. CRITICAL: When a claim contains numbers, dates, or attributes paired with specific entities, verify that each value is assigned to the CORRECT entity. If the claim assigns value A to entity X and value B to entity Y, but the reference assigns value A to entity Y and value B to entity X, that is INCORRECT — the values are swapped. Do not label a claim CLEAR just because the same numbers appear in the reference; check that they are attributed to the same things.
6. Only answer with the specified JSON array, no other text."""


def load_page_analysis(pa_dir: str) -> list[dict]:
    """Load good-quality pages from page_analysis/<hash>.json files."""
    if not os.path.isdir(pa_dir):
        return []

    sources = []
    for cf in sorted(glob(os.path.join(pa_dir, "*.json"))):
        if cf.endswith("_prebid_raw.json"):
            continue
        try:
            with open(cf) as f:
                rec = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Quality gate: only "good" pages enter the prompt
        if classify(rec) != "good":
            continue

        content = rec.get("content") or {}
        text = (content.get("text") or "").strip()
        if not text:
            continue
        wc = content.get("word_count", 0) or len(text.split())
        if wc < MIN_CONTENT_WORDS:
            continue

        sources.append({
            "url": rec.get("url", ""),
            "title": content.get("title", "") or "",
            "text": text,
            "word_count": wc,
        })

    # Cap total words to fit context window
    total_words = sum(s["word_count"] for s in sources)
    if total_words > MAX_TOTAL_CONTENT_WORDS:
        sources.sort(key=lambda s: s["word_count"], reverse=True)
        while total_words > MAX_TOTAL_CONTENT_WORDS and sources:
            longest = sources[0]
            excess = total_words - MAX_TOTAL_CONTENT_WORDS
            if excess >= longest["word_count"]:
                total_words -= longest["word_count"]
                sources.pop(0)
            else:
                words = longest["text"].split()
                keep = len(words) - excess
                longest["text"] = " ".join(words[:keep]) + "\n[... truncated ...]"
                longest["word_count"] = keep
                total_words = sum(s["word_count"] for s in sources)
        sources.sort(key=lambda s: s["url"])

    return sources


def build_prompt(keyword: str, claims: list, references: list, sources: list) -> str:
    claims_section = ""
    for i, c in enumerate(claims, 1):
        claims_section += f'[{i}] "{c}"\n'

    cited_lines = []
    for ref in references:
        ct = ref.get("cited_text", "")
        if ct:
            title = ref.get("title", "").replace(". Opens in new tab.", "")
            cited_lines.append(f'- {title}: "{ct}"')
    cited_section = "\n".join(cited_lines) if cited_lines else "(No cited text snippets available)"

    refs_section = ""
    for i, s in enumerate(sources, 1):
        refs_section += f'[R{i}] {s["title"]}\n'
        refs_section += f'({s["url"]})\n'
        refs_section += f'"""\n{s["text"]}\n"""\n\n'

    return PROMPT_TEMPLATE.format(
        keyword=keyword,
        claims_section=claims_section,
        cited_section=cited_section,
        refs_section=refs_section,
    )


def process_batch(data_dir: str, dry_run: bool = False) -> dict:
    claims_files = sorted(glob(
        os.path.join(data_dir, "**", "claims_grok_4_1.json"),
        recursive=True,
    ))

    stats = {"total": 0, "generated": 0, "skipped_no_claims": 0,
             "skipped_no_content": 0, "skipped_no_result": 0, "total_words": 0}

    for cp in claims_files:
        keyword_dir = os.path.dirname(cp)
        stats["total"] += 1

        try:
            with open(cp) as f:
                cd = json.load(f)
        except (json.JSONDecodeError, OSError):
            stats["skipped_no_claims"] += 1
            continue

        claims = cd.get("claims", []) or []
        n_claims = cd.get("n_claims", len(claims))
        if n_claims == 0 or not claims:
            stats["skipped_no_claims"] += 1
            continue

        result_path = os.path.join(keyword_dir, "result.json")
        if not os.path.exists(result_path):
            stats["skipped_no_result"] += 1
            continue
        try:
            with open(result_path) as f:
                rd = json.load(f)
        except (json.JSONDecodeError, OSError):
            stats["skipped_no_result"] += 1
            continue
        references = (rd.get("aiOverview") or {}).get("references") or []

        pa_dir = os.path.join(keyword_dir, "page_analysis")
        sources = load_page_analysis(pa_dir)
        if not sources:
            stats["skipped_no_content"] += 1
            log.warning(f"No usable content for: {cd.get('keyword', keyword_dir)}")
            continue

        prompt = build_prompt(
            keyword=cd.get("keyword", rd.get("keyword", "")),
            claims=claims,
            references=references,
            sources=sources,
        )

        prompt_words = len(prompt.split())
        stats["total_words"] += prompt_words

        if not dry_run:
            out_path = os.path.join(keyword_dir, "verification_prompt_grok.txt")
            with open(out_path, "w") as f:
                f.write(prompt)

        stats["generated"] += 1
        if stats["generated"] % 200 == 0 or stats["generated"] <= 5:
            log.info(
                f"[{stats['generated']}] {cd.get('keyword', '')}: "
                f"{n_claims} claims, {len(sources)} refs, ~{prompt_words} words"
            )

    return stats


def main():
    parser = argparse.ArgumentParser(description="Stage 2 v2: prompts from grok claims + good page_analysis")
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    log.info(f"Scanning {args.data_dir}")
    stats = process_batch(args.data_dir, dry_run=args.dry_run)

    print(f"\n{'=' * 50}")
    print(f"Total claims_grok_4_1.json folders: {stats['total']}")
    print(f"Prompts generated:              {stats['generated']}")
    print(f"Skipped (no claims):            {stats['skipped_no_claims']}")
    print(f"Skipped (no result.json):       {stats['skipped_no_result']}")
    print(f"Skipped (no usable content):    {stats['skipped_no_content']}")
    if stats['generated'] > 0:
        avg_words = stats['total_words'] // stats['generated']
        print(f"Avg prompt size:                ~{avg_words} words")
    if args.dry_run:
        print("(Dry run — no files written)")
    else:
        print("Output:                         verification_prompt_grok.txt in each keyword folder")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
