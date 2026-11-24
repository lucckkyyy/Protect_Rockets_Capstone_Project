"""Optional bridge to an external detection service (for example, a team's own API).

If the environment variable PHISHGUARD_API_URL is set, the game sends each email to
that URL and uses the answer instead of the built-in detector. If the service is
down or replies with something unexpected, the result is clearly shown as
"Check incomplete" - it is never silently treated as Low Risk.

Expected request  (POST, JSON):  {"sender_name", "sender_email", "reply_to", "subject", "body",
                                  "links": [...], "auth": {"spf", "dkim", "dmarc"}}
Expected response (JSON):        {"verdict": "Low Risk" | "Suspicious" | "High Risk",
                                  "score": 0, "reasons": ["...", "..."]}
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

import detector

VALID_VERDICTS = (detector.LOW, detector.SUSPICIOUS, detector.HIGH)


def remote_url() -> str:
    return os.environ.get("PHISHGUARD_API_URL", "").strip()


def call_remote_detector(email: dict, url: str, timeout: float = 5.0) -> detector.DetectionResult:
    payload = {k: email.get(k, "") for k in
               ("sender_name", "sender_email", "reply_to", "subject", "body")}
    payload["links"] = email.get("links", [])
    payload["auth"] = email.get("auth", {})   # {"spf": "pass|fail|none", "dkim": ..., "dmarc": ...}
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
        return detector.DetectionResult(
            verdict=detector.INCOMPLETE, score=0, complete=False,
            message=f"Detection service unavailable ({type(exc).__name__}).")

    verdict = data.get("verdict") if isinstance(data, dict) else None
    if verdict not in VALID_VERDICTS:
        return detector.DetectionResult(
            verdict=detector.INCOMPLETE, score=0, complete=False,
            message="Detection service returned an unexpected response.")
    findings = [detector.Finding("remote", str(r), 0) for r in data.get("reasons", [])]
    return detector.DetectionResult(verdict=verdict, score=int(data.get("score", 0)),
                                    findings=findings)


def detect(email: dict) -> detector.DetectionResult:
    """Use the remote service if configured, otherwise the built-in rule engine."""
    url = remote_url()
    if url:
        return call_remote_detector(email, url)
    return detector.analyze_email(email)
