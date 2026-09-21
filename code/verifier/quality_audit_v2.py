"""
Quality audit v2 (relaxed) — refined classifier.

Policy: "good" means there is article body text. Some boilerplate / nav / cookie
banner / paywall snippet next to the article is fine. We only mark a page as
non-good when the page is dominated by junk and has no article body.

New classes vs v1: consent_wall, geo_block, js_required, nav_only.
All non-good walls fire only when word_count is low enough that no real
article body is present.
"""

import re

SOCIAL_DOMAINS = {
    "youtube.com", "facebook.com", "instagram.com", "x.com", "twitter.com",
    "tiktok.com", "reddit.com", "linkedin.com", "pinterest.com",
    "threads.net", "threads.com",
}

# Strong nav/boilerplate token list — used to score fallback extractions
NAV_TOKENS = re.compile(
    r"\b(sign in|log in|home|about us|contact|privacy policy|terms of (use|service)|"
    r"newsletter|subscribe|search|menu|skip to (main )?content|cookie|accept all|"
    r"manage (your )?(cookies|preferences|consent)|opens in a new window|"
    r"site search|my account|dashboard)\b",
    re.I,
)

CAPTCHA_PAT = re.compile(
    r"just a moment|checking your browser|captcha|are you a robot|"
    r"verify you are human|performing security verification|security service to protect|"
    r"attention required|cloudflare|pardon our interruption|bot detection|"
    r"please verify you are a human|access to this page has been denied",
    re.I,
)
ACCESS_DENIED_PAT = re.compile(
    r"access denied|forbidden|error 403|you don'?t have permission",
    re.I,
)
NOT_FOUND_PAT = re.compile(
    r"page not found|404 -|sorry, this page|"
    r"oops!?\s*it looks like we cannot find|404 error|file not found|"
    r"we (couldn'?t|cannot|can'?t) find (this|the|that) page|"
    r"this page (is no longer|isn'?t|cannot be found|has moved)|"
    r"page no longer (available|exists)|"
    r"the (link|url|page) (is broken|may have expired)|"
    r"site you were looking for couldn'?t be found|"
    r"^\s*404\b|\bpage you (were|are) looking for",
    re.I,
)
PAYWALL_PAT = re.compile(
    r"already a subscriber|free articles? remaining|metered limit|"
    r"this story is for subscribers|subscriber-?only|"
    r"sign up to read more",
    re.I,
)
LOGIN_WALL_PAT = re.compile(
    r"sign in to (like videos|home shorts|continue|access)|"
    r"log in to continue|create (an? )?account to (read|view|continue)",
    re.I,
)
GEO_BLOCK_PAT = re.compile(
    r"not available in your (region|country|location)|"
    r"this (video|content|page) is not available in your|"
    r"due to (your|geographic) location|"
    r"access from your country (is )?(not )?(allowed|restricted)",
    re.I,
)
CONSENT_PAT = re.compile(
    r"this website utilizes technologies such as cookies|"
    r"manage (your )?(cookie|consent|preferences)|"
    r"we use cookies to (enhance|personalise|provide|analyse|improve|optimize)|"
    r"your privacy preferences|consent details \[#iabv2settings#\]|"
    r"opens in a new window\s+opens an external website",
    re.I,
)
JS_REQUIRED_PAT = re.compile(
    r"javascript is (disabled|required|not enabled)|"
    r"this site (requires|needs) javascript",
    re.I,
)


def _consent_dominates(text: str) -> bool:
    """True if the cookie/consent boilerplate makes up the bulk of the text."""
    if not text:
        return False
    head = text[:1500].lower()
    consent_chars = 0
    for m in CONSENT_PAT.finditer(head):
        consent_chars += len(m.group(0))
    consent_chars += len(re.findall(r"opens in a new window", head, re.I)) * 25
    consent_chars += len(re.findall(r"cookie", head, re.I)) * 10
    return consent_chars > len(head) * 0.30


def _is_nav_only(text: str, wc: int) -> bool:
    if wc >= 400 or not text:
        return False
    head = text[:1500]
    nav_hits = len(NAV_TOKENS.findall(head))
    return nav_hits >= 6 and nav_hits / max(wc, 1) > 0.05


def classify(rec):
    domain = rec.get("domain", "")
    base_domain = re.sub(r"^(www\.|m\.)", "", domain)

    if base_domain in SOCIAL_DOMAINS:
        return "skipped"

    content = rec.get("content") or {}
    wc = content.get("word_count", 0)

    if rec.get("error") and wc == 0:
        return "error"
    if wc == 0:
        return "empty"

    title = (content.get("title") or "").lower()
    text = (content.get("text") or "")[:1500]
    head = text.lower()
    combined = title + " " + head

    # Only fire walls when there's clearly no article body (very low wc).
    if wc < 250 and CAPTCHA_PAT.search(combined):
        return "captcha"
    if wc < 250 and ACCESS_DENIED_PAT.search(combined):
        return "access_denied"
    if wc < 200 and JS_REQUIRED_PAT.search(combined):
        return "js_required"
    if wc < 250 and NOT_FOUND_PAT.search(combined):
        return "not_found"
    if wc < 100 and PAYWALL_PAT.search(combined):
        return "paywall"
    if wc < 200 and LOGIN_WALL_PAT.search(combined):
        return "login_wall"
    if wc < 200 and GEO_BLOCK_PAT.search(combined):
        return "geo_block"

    # Consent wall: only when consent text dominates and there's no real article
    if wc < 300 and _consent_dominates(text):
        return "consent_wall"

    # Fallback extraction with nav-heavy text and no real article
    if content.get("extraction_method") == "fallback" and _is_nav_only(text, wc):
        return "nav_only"

    if wc < 50:
        return "junk_short"

    return "good"
