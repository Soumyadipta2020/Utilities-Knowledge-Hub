"""
Briefing pack generator.

A leader gets a good analysis and currently cannot do anything with it. This
turns a conversation thread, or the open Watchtower findings, into a one-page
summary they can forward: headline, findings, recommendation, sources.

Written as markdown so it renders in the app and pastes cleanly into email.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Sequence

try:
    from langchain_core.messages import HumanMessage, SystemMessage

    HAS_MESSAGES = True
except ImportError:  # pragma: no cover
    HAS_MESSAGES = False
    HumanMessage = SystemMessage = None  # type: ignore[assignment]


BRIEFING_PROMPT = """You write one-page executive briefings for utility company leadership.

Rules:
- Open with a BOTTOM LINE of at most two sentences that a busy executive could read alone.
- Then 'Key findings' as at most 4 bullets. Every bullet must carry a number.
- Then 'Recommended actions' as at most 3 bullets, each one specific and owned.
- Then 'Basis' - the datasets and record counts the analysis rested on.
- Translate impact into pounds wherever the material allows it.
- Never invent a figure that is not in the material. If something was not measured, omit it.
- Under 350 words. Markdown. No preamble, no sign-off.
"""


def _fallback_briefing(title: str, material: str) -> str:
    """Deterministic briefing when no model is configured."""
    lines = [line.strip() for line in material.splitlines() if line.strip()]
    highlights = [l for l in lines if any(ch.isdigit() for ch in l)][:4]
    stamp = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    body = "\n".join(f"- {l.lstrip('-•* ')[:200]}" for l in highlights) or "- No quantified findings captured."
    return (
        f"# {title}\n\n_Generated {stamp}. Model unavailable - this is a mechanical extract, "
        "not a written summary._\n\n## Key findings\n" + body +
        "\n\n## Recommended actions\n- Review the findings above with the accountable owner.\n"
    )


def generate_briefing(
    llm: Any,
    title: str,
    material: str,
    audience: str = "Executive leadership",
) -> str:
    """Summarise supplied material into an executive briefing."""
    if not material.strip():
        return f"# {title}\n\nThere is nothing to brief yet - run an analysis or a Watchtower scan first."

    if llm is None or not HAS_MESSAGES:
        return _fallback_briefing(title, material)

    stamp = datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")
    try:
        response = llm.invoke([
            SystemMessage(content=BRIEFING_PROMPT),
            HumanMessage(content=(
                f"AUDIENCE: {audience}\nTITLE: {title}\n\nMATERIAL TO SUMMARISE:\n{material[:12000]}"
            )),
        ])
        content = getattr(response, "content", "")
        if isinstance(content, list):
            content = "".join(
                str(p.get("text", "")) if isinstance(p, dict) else str(p) for p in content
            )
        text = str(content).strip()
        if not text:
            return _fallback_briefing(title, material)
        # Models tend to restate the title as an H1 even when not asked. Strip a
        # leading heading so the pack does not show the title twice.
        text = re.sub(r"^#{1,2}\s+.*\n+", "", text, count=1)
        return f"# {title}\n\n_Prepared for {audience} · {stamp}_\n\n{text}"
    except Exception as error:  # noqa: BLE001
        print(f"[Briefing] Generation failed: {error}")
        return _fallback_briefing(title, material)


def material_from_thread(history: Sequence[dict[str, str]]) -> str:
    """Flatten a conversation into briefing material."""
    parts = []
    for turn in history:
        role = "QUESTION" if turn.get("role") == "user" else "ANALYSIS"
        content = str(turn.get("content", "")).strip()
        if content:
            parts.append(f"{role}: {content}")
    return "\n\n".join(parts)


def material_from_findings(findings: Sequence[dict[str, Any]]) -> str:
    """Flatten Watchtower findings into briefing material."""
    parts = []
    for finding in findings:
        block = [f"FINDING: {finding.get('headline', '')}"]
        if finding.get("impact_gbp"):
            block.append(f"Estimated impact: £{finding['impact_gbp']:,.0f}")
        evidence = finding.get("evidence") or {}
        if evidence.get("impact_basis"):
            block.append(f"Impact basis: {evidence['impact_basis']}")
        if finding.get("explanation"):
            block.append(f"Root cause analysis: {finding['explanation']}")
        parts.append("\n".join(block))
    return "\n\n".join(parts)
