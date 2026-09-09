"""Gemini as the storyteller for a data-backed projection.

The projector (``projection.py``) produces only real numbers from ClickHouse.
This module hands those numbers to Gemini on Vertex AI and asks for a short,
plain-language *read* of the scenario: crowded or thin field, rising or fading
genre, tight or wide spread, notable real titles. The model is told, firmly, to
use only the numbers it is given and never to invent a figure, so the story is a
narration of the evidence, not a hallucination on top of it. If Gemini is not
reachable, a deterministic grounded summary is returned instead and labelled as
such, so the experience never breaks and never pretends the model spoke when it
did not.
"""

from __future__ import annotations

from typing import Any

from .config import settings

_SYSTEM = (
    "You are the narrator of a data-backed film projector. You are given REAL "
    "statistics computed by ClickHouse over a film catalogue. Write a short, "
    "confident read of the scenario in 3 or 4 sentences for a studio analyst. "
    "Hard rules: use ONLY the numbers you are given; never invent a rating, a "
    "count, or a title; speak in qualitative and relative terms (a crowded or a "
    "thin field, a rising or a fading genre, a tight or a wide spread, clear "
    "upside cases). You may name the real titles you are given. If confidence is "
    "low or the projection abstained, say plainly that the data is too thin to "
    "call it. No hype, no marketing words, no em dashes."
)


def _facts(projection: dict[str, Any]) -> str:
    s = projection.get("scenario", {})
    lines = [
        f"Scenario: a {s.get('genre')} film in {s.get('year')}.",
        f"Comparable real titles: {s.get('n')}. Mean rating {s.get('mean')} out of 10, "
        f"spread (1 sd) {s.get('spread')}, range {s.get('lo')} to {s.get('hi')}. "
        f"Confidence from sample size: {s.get('confidence')}.",
    ]
    traj = projection.get("trajectory") or []
    if len(traj) >= 2:
        first, last = traj[0], traj[-1]
        lines.append(
            f"Genre trajectory: mean rating {first.get('mean')} in {first.get('year')} "
            f"to {last.get('mean')} in {last.get('year')} across the window."
        )
    genres = projection.get("genres") or []
    if genres:
        top = genres[0]
        same = next((g for g in genres if g.get("genre") == s.get("genre")), None)
        rank = genres.index(same) + 1 if same else None
        lines.append(
            f"Among {len(genres)} genres in {s.get('year')}, the strongest by mean is "
            f"{top.get('genre')} at {top.get('mean')}"
            + (f"; this genre ranks {rank} of {len(genres)}." if rank else ".")
        )
    crowd = projection.get("crowd") or []
    if crowd:
        top_titles = ", ".join(f"{c.get('name')} ({c.get('rating')})" for c in crowd[:3])
        lines.append(f"Highest-rated comparable titles: {top_titles}.")
    return "\n".join(lines)


def _fallback(projection: dict[str, Any]) -> str:
    s = projection.get("scenario", {})
    if projection.get("abstained"):
        return (projection.get("reason") or "The data is too thin to project this scenario.")
    n, mean, spread = s.get("n"), s.get("mean"), s.get("spread")
    field = "a crowded field" if (n or 0) >= 150 else "a modest field" if (n or 0) >= 30 else "a thin field"
    tight = "a tight spread" if (spread or 9) <= 1.1 else "a wide spread"
    traj = projection.get("trajectory") or []
    trend = ""
    if len(traj) >= 2 and traj[0].get("mean") is not None and traj[-1].get("mean") is not None:
        trend = " The genre is trending up." if traj[-1]["mean"] > traj[0]["mean"] else " The genre is trending down."
    return (f"A {s.get('genre')} film in {s.get('year')} lands in {field}: {n} comparable "
            f"titles, a mean rating of {mean} with {tight} ({spread}).{trend} "
            f"Confidence is {s.get('confidence')} given the sample size.")


def narrate(projection: dict[str, Any]) -> dict[str, Any]:
    """Return {story, by} where by is 'gemini' or 'grounded-summary'."""
    facts = _facts(projection)
    try:
        from google import genai  # noqa: PLC0415

        client = genai.Client(
            vertexai=settings.use_vertexai,
            project=settings.project or None,
            location=settings.location or None,
        )
        resp = client.models.generate_content(
            model=settings.model_fast,
            contents=f"{_SYSTEM}\n\nThe real data:\n{facts}\n\nWrite the read now.",
        )
        text = (getattr(resp, "text", "") or "").strip()
        if text:
            return {"story": text, "by": "gemini", "model": settings.model_fast}
    except Exception as exc:  # noqa: BLE001 - never break the demo on a model error
        pass
    return {"story": _fallback(projection), "by": "grounded-summary"}
