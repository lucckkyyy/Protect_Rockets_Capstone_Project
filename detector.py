"""Rule-based phishing detector for Aware Rockets.

The detector looks at four areas:
  1. Sender information  (who is it really from?)
  2. Email language      (what is it asking me to do?)
  3. URL information     (where do the links really go?)

  4. Authentication      (do the SPF / DKIM / DMARC header checks pass?)

Every rule adds points. The total is turned into a verdict:
    0-2  -> Low Risk
    3-5  -> Suspicious
    6+   -> High Risk

One urgent word or one unfamiliar sender is NOT enough to call something
phishing. If the email is missing key fields the result is "Check incomplete"
- it is never silently treated as Low Risk.

This is a teaching tool, not a production security product.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from urllib.parse import urlparse

# --------------------------------------------------------------------------
# Configuration - edit these to match your own fictional university
# --------------------------------------------------------------------------
TRUSTED_DOMAINS = ("northfield.example",)

FREE_MAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "freemail.example", "mail-free.example",
}

URL_SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "go-short.example",
}

# Words in a display name that claim to be part of the university
INSTITUTIONAL_WORDS = [
    "northfield", "university", "campus", "registrar", "helpdesk", "help desk",
    "it support", "it security", "financial aid", "student", "payroll",
    "scholarship", "dean", "library", "housing", "single sign-on", "bursar",
]

LOW, SUSPICIOUS, HIGH, INCOMPLETE = "Low Risk", "Suspicious", "High Risk", "Check incomplete"

HIGH_THRESHOLD = 6
SUSPICIOUS_THRESHOLD = 3

# Language patterns: (compiled regex, label)
URGENCY_PATTERNS = [
    (re.compile(p, re.I), label) for p, label in [
        (r"\burgent\b", "urgent"),
        (r"\bimmediately\b", "immediately"),
        (r"within \d+ (hours?|days?)", "short deadline"),
        (r"\bact now\b", "act now"),
        (r"\bfinal notice\b", "final notice"),
        (r"\blast chance\b", "last chance"),
        (r"this week only", "this week only"),
        (r"\bdeadline\b", "deadline"),
        (r"\bexpires?\b", "expires"),
        (r"closes tonight", "closes tonight"),
    ]
]
THREAT_RE = re.compile(
    r"\b(suspend(ed)?|terminated?|deactivated?|locked|legal action|lose access|closed)\b", re.I)
SENSITIVE_RE = re.compile(
    r"((verify|confirm|update|enter|provide|submit).{0,30}(password|credentials|\bpin\b))"
    r"|social security|\bssn\b|date of birth|student id number|bank account|routing number|card number",
    re.I)
PAYMENT_RE = re.compile(
    r"gift cards?|wire transfer|registration fee|processing fee|shipping fee|bitcoin|western union",
    re.I)
GENERIC_GREETING_RE = re.compile(
    r"\bdear (user|student|customer|member|account holder|applicant)\b", re.I)
REWARD_RE = re.compile(
    r"you'?ve won|you have won|you have been selected|you've been selected|claim your|voucher|"
    r"reward|prize|no experience", re.I)
PAY_PROMISE_RE = re.compile(r"\$\d{3,}\s*(/|per)\s*(week|day|hour)", re.I)

URL_RE = re.compile(r"https?://[^\s)>\"']+", re.I)


# --------------------------------------------------------------------------
# Result types
# --------------------------------------------------------------------------
@dataclass
class Finding:
    category: str   # "sender" | "language" | "url" | "auth"
    label: str
    points: int
    detail: str = ""


@dataclass
class DetectionResult:
    verdict: str
    score: int
    findings: list[Finding] = field(default_factory=list)
    complete: bool = True
    message: str = ""

    def by_category(self, category: str) -> list[Finding]:
        return [f for f in self.findings if f.category == category]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def extract_domain(email_address: str) -> str:
    """'a@b.example' -> 'b.example' (lower-case). Empty string if no '@'."""
    if not email_address or "@" not in email_address:
        return ""
    return email_address.rsplit("@", 1)[1].strip().lower()


def registered_domain(host: str) -> str:
    """Naive 'last two labels' domain. Good enough for this teaching game."""
    parts = [p for p in host.lower().strip(".").split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else host.lower()


def is_trusted(host: str) -> bool:
    host = host.lower()
    return any(host == t or host.endswith("." + t) for t in TRUSTED_DOMAINS)


def _normalize_lookalike(domain: str) -> str:
    """Undo common character swaps (1 -> l, 0 -> o, rn -> m ...)."""
    d = domain.lower()
    for fake, real in (("rn", "m"), ("1", "l"), ("0", "o"), ("5", "s"), ("vv", "w")):
        d = d.replace(fake, real)
    return d


def _brand(trusted: str) -> str:
    return trusted.split(".")[0]


def domain_findings(host: str, category: str, where: str) -> list[Finding]:
    """Checks that apply to any host name (sender domain or link domain)."""
    host = host.lower()
    findings: list[Finding] = []
    if not host or is_trusted(host):
        return findings

    reg = registered_domain(host)

    # IP address instead of a name
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host):
        findings.append(Finding(category, "IP address used as the web address", 4,
                                f"{where} points at a raw IP address ({host})."))
        return findings

    # Trusted domain hidden inside a longer, different domain
    for t in TRUSTED_DOMAINS:
        if t in host:
            findings.append(Finding(category, "Trusted name used as a subdomain trick", 4,
                                    f"'{host}' contains '{t}' but really belongs to '{reg}'."))
            break
    else:
        # Character-swap look-alikes (northfie1d.example) or brand inside another domain
        looked = False
        for t in TRUSTED_DOMAINS:
            if reg != t and SequenceMatcher(None, _normalize_lookalike(reg), t).ratio() >= 0.85:
                findings.append(Finding(category, "Look-alike domain", 4,
                                        f"'{reg}' imitates '{t}' with swapped characters."))
                looked = True
                break
        if not looked:
            for t in TRUSTED_DOMAINS:
                if _brand(t) in reg:
                    findings.append(Finding(category, "Look-alike domain", 4,
                                            f"'{reg}' uses the name '{_brand(t)}' but is not '{t}'."))
                    break

    if any(label.startswith("xn--") for label in host.split(".")):
        findings.append(Finding(category, "Punycode (disguised characters) in address", 3,
                                f"'{host}' uses xn-- encoding, which can hide look-alike letters."))
    if reg in URL_SHORTENERS or host in URL_SHORTENERS:
        findings.append(Finding(category, "URL shortener hides the destination", 2,
                                f"'{host}' is a link shortener."))
    if len(host.split(".")) > 4:
        findings.append(Finding(category, "Unusually many subdomains", 1,
                                f"'{host}' has a long chain of subdomains."))
    return findings


# --------------------------------------------------------------------------
# The three analysers
# --------------------------------------------------------------------------
def analyze_sender(sender_name: str, sender_email: str, reply_to: str = "") -> list[Finding]:
    findings: list[Finding] = []
    domain = extract_domain(sender_email)
    if not domain:
        return findings
    trusted = is_trusted(domain)

    if not trusted:
        claims_inst = any(re.search(r"\b" + re.escape(w), sender_name or "", re.I)
                          for w in INSTITUTIONAL_WORDS)
        if claims_inst:
            findings.append(Finding(
                "sender", "Display name claims to be the university", 3,
                f"'{sender_name}' sounds official, but the address is @{domain}."))
        elif domain in FREE_MAIL_DOMAINS:
            findings.append(Finding(
                "sender", "Free personal mail address", 2,
                f"Sent from a free provider (@{domain}), not an organisation."))
        else:
            findings.append(Finding(
                "sender", "Sender is outside the university", 1,
                f"@{domain} is not a trusted university domain."))
        findings += domain_findings(domain, "sender", "The sender address")

    if reply_to:
        rdom = extract_domain(reply_to)
        if rdom and rdom != domain:
            findings.append(Finding(
                "sender", "Reply-To goes somewhere else", 3,
                f"Replies would go to @{rdom}, not @{domain}."))
    return findings


def analyze_language(subject: str, body: str) -> list[Finding]:
    text = f"{subject}\n{body}"
    findings: list[Finding] = []

    hits = sorted({label for rx, label in URGENCY_PATTERNS if rx.search(text)})
    if hits:
        findings.append(Finding("language", "Pressure / urgency wording", min(len(hits), 2),
                                "Found: " + ", ".join(hits) + "."))
    if THREAT_RE.search(text):
        findings.append(Finding("language", "Threat of losing access", 2,
                                "The message threatens suspension, closure or similar."))
    if SENSITIVE_RE.search(text):
        findings.append(Finding("language", "Asks for sensitive information", 3,
                                "Requests a password, ID number, birth date or bank details."))
    if PAYMENT_RE.search(text):
        findings.append(Finding("language", "Asks for payment or gift cards", 3,
                                "Requests an unusual payment, fee or gift-card codes."))
    if GENERIC_GREETING_RE.search(text):
        findings.append(Finding("language", "Generic greeting", 1,
                                "Does not address you by name."))
    if REWARD_RE.search(text):
        findings.append(Finding("language", "Too-good-to-be-true offer", 1,
                                "Promises a prize, reward or easy opportunity."))
    if PAY_PROMISE_RE.search(text):
        findings.append(Finding("language", "Unrealistic pay promise", 1,
                                "Offers high pay for little detail."))
    return findings


def analyze_urls(links: list[dict], sender_email: str = "") -> list[Finding]:
    """`links` is a list of {"text": shown text, "url": real destination}."""
    findings: list[Finding] = []
    sender_reg = registered_domain(extract_domain(sender_email))
    for link in links or []:
        url = (link.get("url") or "").strip()
        text = (link.get("text") or "").strip()
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            continue

        if parsed.scheme == "http":
            findings.append(Finding("url", "Link is not encrypted (http)", 1,
                                    f"{host} is reached over plain http."))
        if "@" in parsed.netloc:
            findings.append(Finding("url", "'@' hides the real destination", 3,
                                    "Everything before '@' in a URL is ignored by the browser."))

        findings += domain_findings(host, "url", f"The link to {host}")

        if not is_trusted(host) and registered_domain(host) != sender_reg \
                and not any(f.category == "url" and f.points >= 3 for f in findings):
            findings.append(Finding("url", "Link goes to an unfamiliar domain", 1,
                                    f"{host} differs from the sender's domain."))

        # Shown text looks like a URL but points somewhere else
        m = re.match(r"(https?://)?([\w.-]+\.[a-z]{2,})", text, re.I)
        if m and m.group(2).lower() != host and registered_domain(m.group(2).lower()) != registered_domain(host):
            findings.append(Finding("url", "Link text does not match the real address", 3,
                                    f"Shows '{text}' but actually goes to {host}."))
    return findings


def analyze_auth(auth: dict | None) -> list[Finding]:
    """SPF / DKIM / DMARC results taken from the email headers.

    'fail' adds points. 'pass' or 'none' adds nothing: passing only proves the
    email came from that domain, not that the domain is trustworthy.
    """
    findings: list[Finding] = []
    explain = {
        "spf": "SPF failed: the sending server is not allowed to send for this domain.",
        "dkim": "DKIM failed: the email's digital signature is invalid.",
        "dmarc": "DMARC failed: the domain's own policy says this email is not authentic.",
    }
    for key, text in explain.items():
        if str((auth or {}).get(key, "")).lower() == "fail":
            findings.append(Finding("auth", f"{key.upper()} check failed", 2, text))
    return findings


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------
def analyze_email(email: dict) -> DetectionResult:
    """Analyse an email dict (same shape as the entries in questions.json)."""
    sender = (email.get("sender_email") or "").strip()
    subject = (email.get("subject") or "").strip()
    body = (email.get("body") or "").strip()

    if not sender or "@" not in sender or not (subject or body):
        return DetectionResult(
            verdict=INCOMPLETE, score=0, complete=False,
            message="Missing sender, subject or body - cannot judge this email.")

    findings = (
        analyze_sender(email.get("sender_name", ""), sender, email.get("reply_to", ""))
        + analyze_language(subject, body)
        + analyze_urls(email.get("links", []), sender)
        + analyze_auth(email.get("auth"))
    )
    score = sum(f.points for f in findings)
    if score >= HIGH_THRESHOLD:
        verdict = HIGH
    elif score >= SUSPICIOUS_THRESHOLD:
        verdict = SUSPICIOUS
    else:
        verdict = LOW
    return DetectionResult(verdict=verdict, score=score, findings=findings)
