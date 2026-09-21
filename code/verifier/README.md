# Claim extraction and verification

This folder contains the Grok-based pipeline that extracts factual claims from an AI Overview and judges how faithfully those claims represent the AIO's cited pages. It uses captured source text; it does not browse the web or independently establish whether a claim is true in the world.

## Files and workflow

| File | Purpose |
|---|---|
| `extract_claims_grok.py` | Reads AIOs from `result.json`, cleans their text, calls Grok to extract factual claims, postprocesses the claims, and writes `claims_grok_4_1.json`. |
| `prompts.py` | System and user prompts for factual-claim extraction. |
| `quality_audit_v2.py` | Filters captured pages with insufficient text, access/CAPTCHA walls, navigation-only content, or excluded social-platform domains. |
| `generate_verification_prompts_v2.py` | Combines extracted claims and usable captured source text into `verification_prompt_grok.txt`. This stage runs offline. |
| `verify_claims_grok.py` | Sends each saved verification prompt to Grok and writes claim labels, evidence, matched references, and summary statistics. |

Default model: `grok-4-1-fast-reasoning`. Both API stages accept `--model`, `--workers`, and `--limit`. Verification additionally supports `--skip_existing`.

## Requirements and input

Requires Python 3.10+; the scripts use only the Python standard library and sibling modules, so no Python packages need to be installed. Extraction and verification require an xAI API key supplied through `XAI_API_KEY` and incur API usage. No key is distributed with this repository.

Each observation lives in its own folder:

```text
observation/
├── result.json
├── page_analysis/
│   └── <url-hash>.json
├── claims_grok_4_1.json             # Written by extraction
├── verification_prompt_grok.txt    # Written by prompt generation
└── verification_result_grok-4-1-fast-reasoning_v2.json
```

`result.json` supplies `keyword`, `aioExists`, and `aiOverview.content`/`references`. Each page-analysis JSON supplies `url`, `domain`, optional `error`, and `content` with `title`, `text`, `word_count`, and `extraction_method`. The input must already contain the cited-page captures; the scraper in this repository collects the Google search page only.

The scripts recursively discover observations below `--data_dir`. Extraction requires nonempty AIO text with `aioExists=true`. Prompt generation skips observations with no claims, no result file, or no usable source text. Reference text is limited to 50,000 words per prompt.

## Run

Use a working copy of an observation or collection folder. These scripts write alongside their inputs and can overwrite the saved study outputs. `--output_dir` on the extractor controls aggregate outputs only; per-observation claims still go into `--data_dir`.

From this directory, with the working observations under `../../work`:

```sh
export XAI_API_KEY="your-own-key"

# 1. Extract claims (API calls).
python3 extract_claims_grok.py --data_dir ../../work --workers 4

# 2. Assemble prompts from claims and captured evidence (offline).
python3 generate_verification_prompts_v2.py --data_dir ../../work

# 3. Verify claims (API calls).
python3 verify_claims_grok.py --data_dir ../../work --workers 4 --skip_existing
```

The extractor also writes aggregate JSONL/CSV and summary files under `./outputs` by default. `--skip_existing` checks only whether the verdict file exists; it does not validate the saved file.

To inspect prompt-generation coverage on the released data without changing it or making API calls:

```sh
python3 generate_verification_prompts_v2.py \
  --data_dir ../../raw/aio_results --dry_run
```

Only the prompt generator supports `--dry_run`. Limiting either API stage to one observation still calls the API and writes output.

## Verification labels

| Label | Meaning relative to the supplied reference text |
|---|---|
| `CLEAR` | Directly supported. |
| `VAGUE` | Supported in broader or less precise terms. |
| `AMBIGUOUS` | References contain conflicting information. |
| `INCORRECT` | Contradicted by the references. |
| `OMITTED` | Not mentioned by the references. |

The saved fidelity rate is `(CLEAR + VAGUE) / number of returned verdicts`. Output also records the claim count, verdict count, label counts, model, token usage, elapsed time, and error status.

## Provenance and current limitations

These five modules come from `content_representativeness_llm/` in the research project. Only usage examples were adjusted for this release; model prompts, quality rules and verification behavior are unchanged. Historical results are provided under `raw/aio_results/`; new model calls need not return identical judgments.

The current verifier accepts a parsed JSON array without enforcing one verdict per claim, valid labels, or valid reference IDs. A historical observation has 34 claims and 35 verdicts, including two different labels for claim 34. Validate new outputs before deriving statistics.

The prompt generator accepts every quality-approved capture in an observation's `page_analysis/` directory. Keep that directory restricted to the AIO's cited pages; mixing in uncited organic-search captures changes the evidence supplied to the verifier. These known review findings are preserved here rather than silently changing the study implementation.
