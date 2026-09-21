"""
Claim extraction from AI Overview text using xAI Grok.

This is a Grok-based adaptation of the previously used:
content_representativeness_llm/extract_claims_v2.py

It preserves the same directory traversal, AIO sanitization, output files, and
production-mode claims.json writing, while replacing the model transport layer
with the xAI OpenAI-compatible chat completions API.
"""

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from prompts import CLAIMIFY_SYSTEM_PROMPT, CLAIMIFY_USER_PROMPT_TEMPLATE

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4-1-fast-reasoning"
DEFAULT_WORKERS = 24
OUTPUT_FILENAME = "claims_grok_4_1.json"
DEFAULT_API_KEY_FILE = "xai_api_key.txt"

SOCIAL_CARD_PATTERNS = [
    r"sn\._setImageSrc\(",
    r"data:image/",
    r"\b\d{2}:\d{2}[A-Za-z@#]",
]


def sanitize_aio_text(text: str) -> str:
    """Trim off social-card/image blobs that pollute extracted AIO text."""
    if not text:
        return text

    cleaned = text.replace("\r\n", "\n")
    cut_points = []
    for pattern in SOCIAL_CARD_PATTERNS:
        match = re.search(pattern, cleaned)
        if match:
            cut_points.append(match.start())

    if cut_points:
        cleaned = cleaned[: min(cut_points)]

    cleaned = re.sub(r"(?:%[0-9A-Fa-f]{2}){20,}", " ", cleaned)
    cleaned = re.sub(r"[A-Za-z0-9+/]{400,}={0,2}", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def postprocess_claims(claims: list[str]) -> list[str]:
    """Clean up and deduplicate extracted claims."""
    cleaned = []
    for claim in claims:
        claim = re.sub(r"^[A-Z][A-Za-z\s&'/()-]+:\s+", "", claim).strip()
        if claim and claim[0].islower():
            claim = claim[0].upper() + claim[1:]
        if claim:
            cleaned.append(claim)

    deduped = []
    for i, claim in enumerate(cleaned):
        claim_core = claim.lower().rstrip(".")
        is_dup = False
        for j, other in enumerate(cleaned):
            if i == j:
                continue
            other_core = other.lower().rstrip(".")
            if claim_core in other_core and len(other_core) > len(claim_core):
                is_dup = True
                break
        if not is_dup:
            deduped.append(claim)
    return deduped


def build_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "claim_extraction_result",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "claims": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "no_claim_reason": {
                        "type": "string",
                    },
                },
                "required": ["claims", "no_claim_reason"],
                "additionalProperties": False,
            },
        },
    }


def call_grok(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 2000,
    timeout: int = 300,
    max_retries: int = 4,
    conv_id: str | None = None,
) -> dict:
    """Call Grok API via OpenAI-compatible endpoint with structured output."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": build_response_format(),
    }).encode()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    if conv_id:
        headers["x-grok-conv-id"] = conv_id

    for attempt in range(max_retries + 1):
        try:
            req = Request(XAI_API_URL, data=payload, headers=headers)
            start = time.time()
            resp = urlopen(req, timeout=timeout)
            data = json.loads(resp.read())
            elapsed = time.time() - start

            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return {
                "response": content,
                "elapsed_s": round(elapsed, 1),
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "cached_tokens": usage.get("prompt_tokens_details", {}).get("cached_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "model": data.get("model", model),
                "error": None,
            }
        except HTTPError as e:
            body = e.read().decode() if hasattr(e, "read") else ""
            is_retryable = e.code in {408, 429, 500, 502, 503, 504}
            log.warning(f"HTTP {e.code} (attempt {attempt + 1}): {body[:200]}")
            if attempt < max_retries and is_retryable:
                wait = min(20, 2 ** (attempt + 1))
                time.sleep(wait)
                continue
            return {
                "response": "",
                "elapsed_s": 0,
                "prompt_tokens": 0,
                "cached_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "model": model,
                "error": f"HTTP {e.code}: {body[:200]}",
            }
        except (URLError, TimeoutError, OSError) as e:
            log.warning(f"Request error (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                time.sleep(min(20, 2 ** (attempt + 1)))
                continue
            return {
                "response": "",
                "elapsed_s": 0,
                "prompt_tokens": 0,
                "cached_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "model": model,
                "error": str(e),
            }

    return {
        "response": "",
        "elapsed_s": 0,
        "prompt_tokens": 0,
        "cached_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "model": model,
        "error": "max_retries_exceeded",
    }


def parse_structured_claims(text: str) -> dict | None:
    """Parse the xAI structured output response."""
    if not text:
        return None

    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
            return {
                "claims": [str(item) for item in parsed["claims"]],
                "no_claim_reason": str(parsed.get("no_claim_reason", "") or ""),
            }
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "{":
                depth += 1
            elif stripped[i] == "}":
                depth -= 1
            if depth == 0:
                chunk = stripped[start : i + 1]
                try:
                    parsed = json.loads(chunk)
                    if isinstance(parsed, dict) and isinstance(parsed.get("claims"), list):
                        return {
                            "claims": [str(item) for item in parsed["claims"]],
                            "no_claim_reason": str(parsed.get("no_claim_reason", "") or ""),
                        }
                except json.JSONDecodeError:
                    break
    return None


def write_single_result_file(result: dict) -> str:
    """Write one per-query claims file next to the source result.json."""
    source_dir = os.path.dirname(result["source_path"])
    claims_path = os.path.join(source_dir, OUTPUT_FILENAME)
    claims_data = {
        "keyword": result["keyword"],
        "aio_word_count": result["aio_word_count"],
        "aio_sentence_count": result["aio_sentence_count"],
        "n_claims": result["n_claims"],
        "claims": result["claims"],
        "no_claim_reason": result.get("no_claim_reason", ""),
        "model": result.get("model", ""),
        "prompt_name": "claimify",
        "elapsed_s": result["elapsed_s"],
        "prompt_tokens": result["prompt_tokens"],
        "cached_tokens": result.get("cached_tokens", 0),
        "completion_tokens": result["completion_tokens"],
        "total_tokens": result["total_tokens"],
        "error": result["error"],
    }
    with open(claims_path, "w") as handle:
        json.dump(claims_data, handle, indent=2)
    return claims_path


def load_aio_records(data_dir: str, limit: int | None = None) -> list[dict]:
    """Load result.json files that have AIO content."""
    pattern = os.path.join(data_dir, "**", "result.json")
    paths = sorted(glob(pattern, recursive=True))

    records = []
    for path in paths:
        try:
            data = json.load(open(path))
        except (json.JSONDecodeError, OSError):
            continue

        aio = data.get("aiOverview", {})
        content = sanitize_aio_text(aio.get("content", ""))
        if not content or not data.get("aioExists"):
            continue

        rel = os.path.relpath(path, data_dir)
        query_id = rel.replace("/result.json", "").replace("/", "__")

        protected = content
        abbreviations = [
            "U.S.", "u.s.", "U.K.", "u.k.", "E.U.", "e.u.",
            "a.m.", "A.M.", "p.m.", "P.M.",
            "Dr.", "Mr.", "Mrs.", "Ms.", "Jr.", "Sr.", "St.",
            "Inc.", "Corp.", "Ltd.", "Co.", "vs.", "Vol.",
            "Gen.", "Gov.", "Sen.", "Rep.", "Prof.",
            "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.",
            "Sep.", "Oct.", "Nov.", "Dec.",
            "approx.", "est.", "dept.", "avg.",
            "e.g.", "i.e.", "etc.", "al.", "fig.",
        ]
        for abbr in abbreviations:
            protected = protected.replace(abbr, abbr.replace(".", "<DOT>"))
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s*(?=[A-Z])", protected)
            if s.strip()
        ]

        records.append({
            "query_id": query_id,
            "keyword": data.get("keyword", ""),
            "category": os.path.basename(os.path.dirname(os.path.dirname(path))),
            "aio_text": content,
            "aio_char_count": len(content),
            "aio_word_count": len(content.split()),
            "aio_sentence_count": len(sentences),
            "n_references": len(aio.get("references", [])),
            "source_path": path,
        })

    if limit and limit < len(records):
        records = random.sample(records, limit)
    return records


def extract_claims_single(
    record: dict,
    api_key: str,
    model: str,
    conv_id: str,
    max_retries: int = 2,
) -> dict:
    system_prompt = CLAIMIFY_SYSTEM_PROMPT
    user_prompt = CLAIMIFY_USER_PROMPT_TEMPLATE.format(aio_text=record["aio_text"])

    result = None
    for attempt in range(max_retries + 1):
        result = call_grok(
            system_prompt,
            user_prompt,
            api_key=api_key,
            model=model,
            conv_id=conv_id,
        )
        if result["error"]:
            if attempt < max_retries:
                time.sleep(2)
                continue
            return {
                **record,
                "claims": [],
                "n_claims": 0,
                "no_claim_reason": "",
                "error": result["error"],
                "raw_response": result["response"],
                "elapsed_s": result["elapsed_s"],
                "prompt_tokens": result["prompt_tokens"],
                "cached_tokens": result["cached_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
            }

        claims = parse_structured_claims(result["response"])
        if claims is not None:
            processed_claims = postprocess_claims(claims["claims"])
            return {
                **record,
                "claims": processed_claims,
                "n_claims": len(processed_claims),
                "no_claim_reason": claims["no_claim_reason"],
                "error": None,
                "raw_response": result["response"],
                "elapsed_s": result["elapsed_s"],
                "prompt_tokens": result["prompt_tokens"],
                "cached_tokens": result["cached_tokens"],
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
            }

        log.warning(
            f"[{record['keyword']}] JSON parse failed (attempt {attempt + 1}), "
            f"response: {result['response'][:200]}"
        )
        if attempt < max_retries:
            time.sleep(1)

    return {
        **record,
        "claims": [],
        "n_claims": 0,
        "no_claim_reason": "",
        "error": "json_parse_failed",
        "raw_response": result["response"] if result else "",
        "elapsed_s": result["elapsed_s"] if result else 0,
        "prompt_tokens": result["prompt_tokens"] if result else 0,
        "cached_tokens": result["cached_tokens"] if result else 0,
        "completion_tokens": result["completion_tokens"] if result else 0,
        "total_tokens": result["total_tokens"] if result else 0,
    }


def run_extraction(
    records: list[dict],
    api_key: str,
    model: str,
    conv_id: str,
    workers: int = DEFAULT_WORKERS,
    write_each: bool = True,
) -> list[dict]:
    """Run claim extraction on all records, preserving original order."""
    indexed_records = list(enumerate(records))
    ordered_results = [None] * len(indexed_records)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(extract_claims_single, record, api_key, model, conv_id): idx
            for idx, record in indexed_records
        }
        total = len(futures)
        completed = 0
        for future in as_completed(futures):
            idx = futures[future]
            out = future.result()
            out["model"] = model
            if write_each:
                write_single_result_file(out)
            ordered_results[idx] = out
            completed += 1
            log.info(
                f"[{completed}/{total}] {out['keyword']}: "
                f"{out['n_claims']} claims in {out['elapsed_s']}s"
                + (f" ERROR: {out['error']}" if out["error"] else "")
            )
    return ordered_results


def save_results(
    results: list[dict],
    output_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)
    log.info(f"Per-query files already written incrementally as {OUTPUT_FILENAME}")

    jsonl_path = os.path.join(output_dir, "claims_extracted.jsonl")
    with open(jsonl_path, "w") as handle:
        for result in results:
            row = {
                "query_id": result["query_id"],
                "keyword": result["keyword"],
                "category": result["category"],
                "aio_char_count": result["aio_char_count"],
                "aio_word_count": result["aio_word_count"],
                "aio_sentence_count": result["aio_sentence_count"],
                "n_references": result["n_references"],
                "n_claims": result["n_claims"],
                "claims": result["claims"],
                "no_claim_reason": result.get("no_claim_reason", ""),
                "prompt_tokens": result["prompt_tokens"],
                "cached_tokens": result.get("cached_tokens", 0),
                "completion_tokens": result["completion_tokens"],
                "total_tokens": result["total_tokens"],
                "error": result["error"],
                "elapsed_s": result["elapsed_s"],
            }
            handle.write(json.dumps(row) + "\n")

    raw_path = os.path.join(output_dir, "raw_responses.jsonl")
    with open(raw_path, "w") as handle:
        for result in results:
            handle.write(json.dumps({
                "query_id": result["query_id"],
                "keyword": result["keyword"],
                "raw_response": result["raw_response"],
            }) + "\n")

    csv_path = os.path.join(output_dir, "extraction_summary.csv")
    with open(csv_path, "w") as handle:
        handle.write("query_id,keyword,category,aio_chars,n_refs,n_claims,prompt_tokens,cached_tokens,completion_tokens,total_tokens,elapsed_s,error\n")
        for result in results:
            handle.write(
                f"{result['query_id']},{result['keyword']},{result['category']},"
                f"{result['aio_char_count']},{result['n_references']},{result['n_claims']},"
                f"{result['prompt_tokens']},{result.get('cached_tokens', 0)},{result['completion_tokens']},{result['total_tokens']},"
                f"{result['elapsed_s']},{result['error'] or ''}\n"
            )

    total = len(results)
    ok = sum(1 for result in results if not result["error"])
    total_claims = sum(result["n_claims"] for result in results)
    total_time = sum(result["elapsed_s"] for result in results)
    total_prompt_tokens = sum(result["prompt_tokens"] for result in results)
    total_cached_tokens = sum(result.get("cached_tokens", 0) for result in results)
    total_completion_tokens = sum(result["completion_tokens"] for result in results)
    avg_claims = total_claims / ok if ok else 0
    avg_time = total_time / ok if ok else 0

    print(f"\n{'=' * 50}")
    print(f"Extraction complete: {ok}/{total} succeeded")
    print(f"Total claims: {total_claims} (avg {avg_claims:.1f} per query)")
    print(f"Total time: {total_time:.0f}s (avg {avg_time:.1f}s per query)")
    print(f"Prompt tokens: {total_prompt_tokens:,}")
    print(f"Cached prompt tokens: {total_cached_tokens:,}")
    print(f"Completion tokens: {total_completion_tokens:,}")
    print(f"Total tokens: {total_prompt_tokens + total_completion_tokens:,}")
    print(f"Output: {output_dir}")
    print(f"Per-query files: {OUTPUT_FILENAME} written alongside each result.json")
    print(f"{'=' * 50}")


def default_conv_id(data_dir: str, model: str) -> str:
    seed = f"{os.path.abspath(data_dir)}::{model}::claimify"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:32]
    return f"claimify-{digest}"


def load_local_api_key() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(script_dir, DEFAULT_API_KEY_FILE)
    try:
        with open(key_path) as handle:
            return handle.read().strip()
    except OSError:
        return ""


def main():
    parser = argparse.ArgumentParser(description="Extract claims from AIO text using Grok")
    parser.add_argument("--data_dir", required=True, help="Path to downloaded AIO batch folder")
    parser.add_argument("--output_dir", default=None, help="Output directory (default: ./outputs)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"xAI model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--api_key", default=None, help="xAI API key (or set XAI_API_KEY env var)")
    parser.add_argument("--conv_id", default=None, help="Stable xAI prompt-caching conversation ID")
    parser.add_argument("--limit", type=int, default=None, help="Max records to process")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help=f"Concurrent workers (default: {DEFAULT_WORKERS})")
    args = parser.parse_args()

    api_key = args.api_key or os.environ.get("XAI_API_KEY") or load_local_api_key()
    if not api_key:
        log.error(
            f"No API key. Use --api_key, set XAI_API_KEY, or place it in "
            f"{DEFAULT_API_KEY_FILE} inside the extract_claims_grok folder"
        )
        sys.exit(1)

    if args.output_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.output_dir = os.path.join(script_dir, "outputs")

    log.info(f"Loading records from {args.data_dir}")
    records = load_aio_records(args.data_dir, limit=args.limit)
    log.info(f"Found {len(records)} AIO records")

    if not records:
        log.error("No records found. Check data_dir path.")
        sys.exit(1)

    log.info(f"Using model: {args.model}")
    log.info("Using prompt: claimify")
    conv_id = args.conv_id or default_conv_id(args.data_dir, args.model)
    log.info(f"Using x-grok-conv-id: {conv_id}")

    results = run_extraction(
        records,
        api_key=api_key,
        model=args.model,
        conv_id=conv_id,
        workers=args.workers,
        write_each=True,
    )

    save_results(results, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
