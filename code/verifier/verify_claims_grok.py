"""
Stage 2 (grok): Verify claims against references using Grok API with prompt caching.

Key differences vs verify_claims.py:
  - Reads verification_prompt_grok.txt (from generate_verification_prompts_v2.py)
  - Uses claims_grok_4_1.json for claim metadata
  - Splits prompt into stable system header + variable user body, then sets
    x-grok-conv-id so Grok caches the system header across calls
  - Tracks cached_tokens via usage.prompt_tokens_details.cached_tokens
  - Writes verification_result_grok-4-1-fast-reasoning_v2.json
  - Final summary prints cache-hit rate

Usage (calls the API and writes verification results):
    python verify_claims_grok.py --data_dir ../../work --limit 1
    python verify_claims_grok.py --data_dir ../../work --skip_existing
"""

import argparse
import hashlib
import json
import logging
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from glob import glob
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

XAI_API_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4-1-fast-reasoning"
DEFAULT_API_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xai_api_key.txt")

# Marker used to split the pre-generated prompt file into a stable system
# header (above) and a variable user body (below). Matches the template in
# generate_verification_prompts_v2.py.
PROMPT_SPLIT_MARKER = "Keyword: \""


def split_prompt(full_prompt: str) -> tuple[str, str]:
    """Split the pre-generated prompt into (stable system, variable user).

    System part is the boilerplate: Objective + label defs + few-shot examples
    + 'Now verify ALL...' line. Everything after the first 'Keyword: "'
    (keyword + claims + cited + refs + output spec + rules) is the user body.
    """
    idx = full_prompt.find(PROMPT_SPLIT_MARKER)
    if idx == -1:
        # Fallback: entire thing in user, empty system
        return ("", full_prompt)
    # Include the trailing blank line before 'Keyword:' in the system portion
    return (full_prompt[:idx].rstrip() + "\n", full_prompt[idx:])


def call_grok(
    system_prompt: str,
    user_prompt: str,
    api_key: str,
    model: str,
    conv_id: str,
    max_tokens: int = 4096,
    temperature: float = 0.0,
    timeout: int = 300,
    max_retries: int = 2,
) -> dict:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "x-grok-conv-id": conv_id,
    }

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
                "content": content,
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
            log.warning(f"HTTP {e.code} (attempt {attempt+1}): {body[:200]}")
            if attempt < max_retries and is_retryable:
                time.sleep(min(20, 2 ** (attempt + 1)))
                continue
            return {
                "content": "", "elapsed_s": 0, "prompt_tokens": 0, "cached_tokens": 0,
                "completion_tokens": 0, "total_tokens": 0, "model": model,
                "error": f"HTTP {e.code}: {body[:200]}",
            }
        except (URLError, TimeoutError, OSError) as e:
            log.warning(f"Request error (attempt {attempt+1}): {e}")
            if attempt < max_retries:
                time.sleep(min(20, 2 ** (attempt + 1)))
                continue
            return {
                "content": "", "elapsed_s": 0, "prompt_tokens": 0, "cached_tokens": 0,
                "completion_tokens": 0, "total_tokens": 0, "model": model, "error": str(e),
            }

    return {
        "content": "", "elapsed_s": 0, "prompt_tokens": 0, "cached_tokens": 0,
        "completion_tokens": 0, "total_tokens": 0, "model": model, "error": "max_retries_exceeded",
    }


def parse_verification_response(text: str) -> list | None:
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    start = text.find("[")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
            if depth == 0:
                try:
                    result = json.loads(text[start:i+1])
                    if isinstance(result, list):
                        return result
                except json.JSONDecodeError:
                    break
    return None


def _model_tag(model: str) -> str:
    return model.replace("/", "-")


def process_folder(folder: str, api_key: str, model: str, conv_id: str) -> dict:
    prompt_path = os.path.join(folder, "verification_prompt_grok.txt")
    claims_path = os.path.join(folder, "claims_grok_4_1.json")
    with open(prompt_path) as f:
        prompt_full = f.read()
    with open(claims_path) as f:
        claims_data = json.load(f)

    keyword = claims_data.get("keyword", "")
    n_claims = claims_data.get("n_claims", len(claims_data.get("claims", [])))

    system_prompt, user_prompt = split_prompt(prompt_full)

    # Scale max_tokens with claim count
    max_tokens = max(4096, min(32768, n_claims * 250 + 1000))

    resp = call_grok(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        api_key=api_key,
        model=model,
        conv_id=conv_id,
        max_tokens=max_tokens,
    )
    if resp["error"]:
        log.error(f"[{keyword}] API error: {resp['error']}")
        return {
            "keyword": keyword, "n_claims": n_claims, "n_verified": 0,
            "error": resp["error"], "elapsed_s": resp["elapsed_s"],
            "prompt_tokens": resp["prompt_tokens"],
            "cached_tokens": resp["cached_tokens"],
            "completion_tokens": resp["completion_tokens"],
        }

    verifications = parse_verification_response(resp["content"])
    if verifications is None:
        log.error(f"[{keyword}] JSON parse failed, raw: {resp['content'][:200]}")
        raw_path = os.path.join(folder, f"verification_raw_{_model_tag(model)}.txt")
        with open(raw_path, "w") as f:
            f.write(resp["content"])
        return {
            "keyword": keyword, "n_claims": n_claims, "n_verified": 0,
            "error": "json_parse_failed", "elapsed_s": resp["elapsed_s"],
            "prompt_tokens": resp["prompt_tokens"],
            "cached_tokens": resp["cached_tokens"],
            "completion_tokens": resp["completion_tokens"],
        }

    labels = [v.get("label", "UNKNOWN") for v in verifications]
    label_counts = {lab: labels.count(lab) for lab in
                    ["CLEAR", "VAGUE", "AMBIGUOUS", "INCORRECT", "OMITTED"]}

    result = {
        "keyword": keyword,
        "model": resp["model"],
        "n_claims": n_claims,
        "n_verified": len(verifications),
        "label_counts": label_counts,
        "consistent": label_counts["CLEAR"] + label_counts["VAGUE"],
        "inconsistent": label_counts["AMBIGUOUS"] + label_counts["INCORRECT"] + label_counts["OMITTED"],
        "fidelity_rate": round((label_counts["CLEAR"] + label_counts["VAGUE"]) / len(verifications), 4) if verifications else 0,
        "verifications": verifications,
        "elapsed_s": resp["elapsed_s"],
        "prompt_tokens": resp["prompt_tokens"],
        "cached_tokens": resp["cached_tokens"],
        "completion_tokens": resp["completion_tokens"],
        "error": None,
    }
    out_path = os.path.join(folder, f"verification_result_{_model_tag(model)}_v2.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    return result


def default_conv_id(data_dir: str, model: str) -> str:
    seed = f"{os.path.abspath(data_dir)}::{model}::verify"
    digest = hashlib.sha256(seed.encode()).hexdigest()[:32]
    return f"verify-{digest}"


def load_local_api_key() -> str:
    try:
        with open(DEFAULT_API_KEY_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data_dir", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--api_key", default=None)
    p.add_argument("--conv_id", default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--skip_existing", action="store_true")
    p.add_argument("--workers", type=int, default=16)
    args = p.parse_args()

    api_key = args.api_key or os.environ.get("XAI_API_KEY") or load_local_api_key()
    if not api_key:
        log.error("No API key. Set XAI_API_KEY or --api_key")
        return

    prompt_files = sorted(glob(os.path.join(args.data_dir, "**", "verification_prompt_grok.txt"), recursive=True))
    folders = [os.path.dirname(f) for f in prompt_files]

    if args.skip_existing:
        tag = _model_tag(args.model)
        before = len(folders)
        folders = [f for f in folders if not os.path.exists(os.path.join(f, f"verification_result_{tag}_v2.json"))]
        log.info(f"Skipping {before - len(folders)} already-processed")

    if args.limit and args.limit < len(folders):
        random.seed(123)
        folders = random.sample(folders, args.limit)

    conv_id = args.conv_id or default_conv_id(args.data_dir, args.model)
    log.info(f"Processing {len(folders)} folders | model={args.model} | workers={args.workers}")
    log.info(f"conv_id (cache key): {conv_id}")

    total_prompt_tokens = 0
    total_cached_tokens = 0
    total_completion_tokens = 0
    total_claims = 0
    total_verified = 0
    errors = 0
    all_labels = {lab: 0 for lab in ["CLEAR", "VAGUE", "AMBIGUOUS", "INCORRECT", "OMITTED"]}

    completed = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        fut_to_folder = {pool.submit(process_folder, f, api_key, args.model, conv_id): f for f in folders}
        for fut in as_completed(fut_to_folder):
            folder = fut_to_folder[fut]
            completed += 1
            kw = os.path.basename(folder)
            try:
                r = fut.result()
            except Exception as e:
                errors += 1
                log.error(f"[{completed}/{len(folders)}] {kw} -> EXCEPTION: {e}")
                continue

            total_prompt_tokens += r.get("prompt_tokens", 0)
            total_cached_tokens += r.get("cached_tokens", 0)
            total_completion_tokens += r.get("completion_tokens", 0)
            total_claims += r.get("n_claims", 0)
            if r.get("error"):
                errors += 1
                log.error(f"[{completed}/{len(folders)}] {kw} -> ERROR: {r['error']}")
            else:
                total_verified += r["n_verified"]
                for lab, cnt in r.get("label_counts", {}).items():
                    all_labels[lab] = all_labels.get(lab, 0) + cnt
                cache_pct = (100 * r.get("cached_tokens", 0) / r.get("prompt_tokens", 1)) if r.get("prompt_tokens") else 0
                log.info(
                    f"[{completed}/{len(folders)}] {kw}: "
                    f"{r['n_verified']} verified in {r['elapsed_s']}s | "
                    f"fidelity={r['fidelity_rate']:.2%} | "
                    f"tokens={r['prompt_tokens']}+{r['completion_tokens']} "
                    f"(cached={r['cached_tokens']}, {cache_pct:.0f}%)"
                )

    # Summary
    print(f"\n{'=' * 70}")
    print(f"Verification complete: {len(folders) - errors}/{len(folders)} succeeded")
    print(f"Total claims: {total_claims}, verified: {total_verified}")
    print(f"Errors: {errors}")
    print()
    print(f"=== Token usage ===")
    print(f"  Prompt tokens:      {total_prompt_tokens:,}")
    print(f"  Cached tokens:      {total_cached_tokens:,}")
    if total_prompt_tokens:
        hit_rate = 100 * total_cached_tokens / total_prompt_tokens
        print(f"  Cache hit rate:     {hit_rate:.1f}% of prompt tokens")
        billed_prompt = total_prompt_tokens - total_cached_tokens
        print(f"  Billed-new tokens:  {billed_prompt:,} (non-cached portion)")
    print(f"  Completion tokens:  {total_completion_tokens:,}")
    print(f"  Total tokens:       {total_prompt_tokens + total_completion_tokens:,}")

    if total_verified > 0:
        print(f"\n=== Label distribution ===")
        for lab in ["CLEAR", "VAGUE", "AMBIGUOUS", "INCORRECT", "OMITTED"]:
            cnt = all_labels[lab]
            pct = 100 * cnt / total_verified
            print(f"  {lab:<12} {cnt:>5,} ({pct:>5.1f}%)")
        consistent = all_labels["CLEAR"] + all_labels["VAGUE"]
        inconsistent = all_labels["AMBIGUOUS"] + all_labels["INCORRECT"] + all_labels["OMITTED"]
        print(f"\n  Consistent (CLEAR+VAGUE):    {consistent:>5,} ({100*consistent/total_verified:.1f}%)")
        print(f"  Inconsistent (AMB+INC+OMIT): {inconsistent:>5,} ({100*inconsistent/total_verified:.1f}%)")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
