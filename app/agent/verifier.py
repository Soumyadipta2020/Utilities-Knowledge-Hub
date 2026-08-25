"""
Verification agent: an independent second derivation of the headline numbers.

The main agent asserts figures and nothing currently checks them. Before a leader
repeats a number to a board or a regulator, it is worth knowing whether it
survives being derived a second time by a different route.

This is deliberately adversarial. The verifier is NOT shown the first agent's
query - only the claim - and is told to derive the figure independently and to
report disagreement rather than smooth it over.
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from langchain_core.messages import HumanMessage, SystemMessage

    HAS_MESSAGES = True
except ImportError:  # pragma: no cover
    HAS_MESSAGES = False
    HumanMessage = SystemMessage = None  # type: ignore[assignment]


CLAIM_EXTRACTION_PROMPT = """You extract checkable numeric claims from an analyst's answer.

Return JSON only: {"claims": [{"claim": "...", "value": "..."}]}

Include at most {max_claims} claims, choosing the ones a decision would actually rest on -
headline totals, rates, rankings. Skip numbers that are merely illustrative.
If the answer contains no checkable numeric claim, return {"claims": []}.
"""

VERIFIER_PROMPT = """You are an independent verification analyst. Another analyst has made a
numeric claim about the company's data. You have not seen how they derived it.

Your job is to derive the figure YOURSELF from the underlying data, using
query_datasets_sql, and then judge whether their claim holds.

Be adversarial. Do not assume the claim is correct. If your figure differs
materially (more than 2%), say so plainly and give your figure. If the claim is
too vague to check, say that.

CONFIDENCE is a whole number 0-100: how confident you are that the analyst's
claim is correct, after your own derivation. A claim you reproduced exactly sits
near 100; one you could not check at all sits near 50; one your own figure
contradicts sits low. Do not round everything to 100 or 0 - the number is read
by a leader deciding how much weight to put on the figure.

The final line is shown to a business reader, not to an analyst. Write it as a
short plain sentence they could act on. Say what you got and whether it backs the
claim - "I got the same figure", "I got 654,000 hours, about 20% lower", "I could
not check this without knowing how the shortfall was defined". Do not use
shorthand, method names or phrases like "pooled result" or "rule absent"; if your
method differed from theirs, say so in words a non-specialist understands.

Finish with EXACTLY one line in this format:
VERDICT: CONFIRMED | REFUTED | UNVERIFIABLE — CONFIDENCE: <0-100>% — <plain sentence, under 25 words>
"""

# Used only when the verifier ignores the CONFIDENCE field. Deliberately coarse -
# these are read off the verdict, not measured, and the UI marks them as such.
ASSUMED_SCORE = {"CONFIRMED": 90, "UNVERIFIABLE": 50, "REFUTED": 10}


def _extract_json(content: Any) -> dict:
    if isinstance(content, list):
        content = "".join(
            str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content
        )
    text = str(content).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def extract_claims(llm: Any, answer: str, max_claims: int = 2) -> list[dict[str, str]]:
    """Pull the load-bearing numeric claims out of an answer."""
    if llm is None or not HAS_MESSAGES or not answer.strip():
        return []
    try:
        # The cap lives in the prompt as well as the slice below, so the extractor
        # is never asked for claims that would then be silently dropped.
        response = llm.invoke([
            SystemMessage(content=CLAIM_EXTRACTION_PROMPT.replace("{max_claims}", str(max_claims))),
            HumanMessage(content=f"ANALYST ANSWER:\n{answer[:4000]}"),
        ])
        parsed = _extract_json(getattr(response, "content", response))
        claims = parsed.get("claims", [])
        return [c for c in claims if isinstance(c, dict) and c.get("claim")][:max_claims]
    except Exception as error:  # noqa: BLE001 - verification is best-effort
        print(f"[Verifier] Claim extraction failed: {error}")
        return []


def verify_claim(runtime: Any, claim: dict[str, str]) -> dict[str, Any]:
    """Independently re-derive one claim. Returns verdict, detail and the text."""
    statement = f"{claim.get('claim', '')} (stated value: {claim.get('value', 'n/a')})"
    prompt = (
        f"{VERIFIER_PROMPT}\n\nCLAIM TO CHECK:\n{statement}\n\n"
        "Derive it independently from the data now."
    )
    try:
        text = runtime.run(prompt, "verifier@system", None) or ""
    except Exception as error:  # noqa: BLE001
        print(f"[Verifier] Verification run failed: {error}")
        return {
            "claim": statement, "verdict": "UNVERIFIABLE", "detail": str(error)[:200],
            "score": 0, "score_stated": False, "text": "",
        }

    match = re.search(
        r"VERDICT:\s*(CONFIRMED|REFUTED|UNVERIFIABLE)\s*[-—:]*\s*"
        r"(?:CONFIDENCE:\s*(\d{1,3})\s*%?\s*[-—:]*\s*)?(.*)",
        text,
        re.IGNORECASE,
    )
    if match:
        verdict = match.group(1).upper()
        detail = match.group(3).strip()[:240]
        stated = match.group(2)
    else:
        verdict, detail, stated = "UNVERIFIABLE", "The verifier did not return a parseable verdict.", None

    # A stated score is the verifier's own; anything else is read off the verdict
    # and flagged so the UI never presents a guess as a measured number.
    score_stated = stated is not None
    score = min(100, max(0, int(stated))) if score_stated else ASSUMED_SCORE.get(verdict, 50)
    return {
        "claim": statement, "verdict": verdict, "detail": detail,
        "score": score, "score_stated": score_stated, "text": text,
    }


def verify_answer(llm: Any, runtime: Any, answer: str, max_claims: int = 2) -> dict[str, Any]:
    """Extract the key claims from an answer and independently check each."""
    claims = extract_claims(llm, answer, max_claims=max_claims)
    if not claims:
        return {"checked": 0, "confidence": "unchecked", "results": []}

    results = [verify_claim(runtime, claim) for claim in claims]
    verdicts = [r["verdict"] for r in results]

    if any(v == "REFUTED" for v in verdicts):
        confidence = "disputed"
    elif all(v == "CONFIRMED" for v in verdicts):
        confidence = "verified"
    else:
        confidence = "partial"

    return {"checked": len(results), "confidence": confidence, "results": results}
