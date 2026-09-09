"""Multiverse Projector: data-backed what-if projection over real comparable cohorts.

You pose a scenario (a genre and a year). This module pulls the real
comparable-title cohort from ClickHouse through the SAME guarded
``run_clickhouse_sql`` path the agent uses (read-only screen, table allowlist,
action limiter, chosen transport), and returns a "multiverse" of real cohorts:

  * ``scenario``   the base cohort's real mean rating, spread and sample size,
                   with an honest confidence label derived from ``n``.
  * ``crowd``      the actual comparable titles (name, rating) in that cohort,
                   so the "crowd" on screen is real films, not invented personas.
  * ``trajectory`` the same genre across a window of years (the time multiverse).
  * ``genres``     sibling genres in the same year (the genre multiverse).

Every number is a value that came back in a row. If the base cohort is too small
to say anything, it abstains instead of projecting a shape from thin air. The
LLM is not in this path at all: the projection is pure ClickHouse aggregation,
which is exactly why it cannot hallucinate a number.
"""

from __future__ import annotations

import uuid
from typing import Any

from .clickhouse_tools import bind_run, run_clickhouse_sql

MIN_PROJECT_N = 6  # below this, abstain rather than project a distribution
_CONFIDENCE = ((30, "high"), (15, "moderate"), (MIN_PROJECT_N, "low"))


def _lit(value: str) -> str:
    """A safe single-quoted SQL literal (genre names never contain quotes, but
    escape defensively; the read-only + scope guards still run on top)."""
    return "'" + str(value).replace("'", "''") + "'"


def _confidence(n: int) -> str:
    for threshold, label in _CONFIDENCE:
        if n >= threshold:
            return label
    return "insufficient"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _num(value: Any) -> float | None:
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def options() -> dict[str, Any]:
    """Genres with enough rated titles to project, and the year range, for the UI."""
    bind_run("project-opts-" + uuid.uuid4().hex[:8])
    genres = run_clickhouse_sql(
        "SELECT g.genre AS genre, count() AS n "
        "FROM imdb.genres g INNER JOIN imdb.movies m ON m.id = g.movie_id "
        "WHERE m.rank > 0 GROUP BY genre HAVING n >= 150 ORDER BY n DESC",
        note="projector: available genres",
    )
    years = run_clickhouse_sql(
        "SELECT min(year) AS lo, max(year) AS hi FROM imdb.movies "
        "WHERE year > 1920 AND rank > 0",
        note="projector: year range",
    )
    genre_list = [r["genre"] for r in genres.get("rows", [])] if genres.get("status") == "ok" else []
    yr = (years.get("rows") or [{}])[0] if years.get("status") == "ok" else {}
    return {
        "genres": genre_list,
        "year_min": _int(yr.get("lo"), 1930),
        "year_max": _int(yr.get("hi"), 2004),
    }


def project(genre: str, year: int, window: int = 7) -> dict[str, Any]:
    """Project the scenario (genre, year) onto its real comparable cohorts."""
    bind_run("project-" + uuid.uuid4().hex[:8])
    year = _int(year)
    gq = _lit(genre)
    traces: list[dict] = []

    def run(sql: str, note: str) -> dict:
        result = run_clickhouse_sql(sql, note)
        g = result.get("grounding", {})
        if g:
            traces.append({k: g.get(k) for k in ("source", "transport", "elapsed_ms", "rows_read") if k in g})
        return result

    base = run(
        "SELECT round(avg(m.rank), 2) AS mean, round(stddevPop(m.rank), 2) AS spread, "
        "count() AS n, round(min(m.rank), 1) AS lo, round(max(m.rank), 1) AS hi "
        "FROM imdb.movies m INNER JOIN imdb.genres g ON g.movie_id = m.id "
        f"WHERE g.genre = {gq} AND m.year = {year} AND m.rank > 0",
        note=f"cohort: {genre} in {year}",
    )
    transport = (base.get("grounding") or {}).get("transport")
    if base.get("status") != "ok" or not base.get("rows"):
        return {"scenario": {"genre": genre, "year": year}, "abstained": True,
                "reason": base.get("reason") or "the query did not return a cohort",
                "crowd": [], "trajectory": [], "genres": [], "traces": traces, "transport": transport}

    row = base["rows"][0]
    n = _int(row.get("n"))
    scenario = {
        "genre": genre, "year": year, "mean": _num(row.get("mean")),
        "spread": _num(row.get("spread")), "n": n,
        "lo": _num(row.get("lo")), "hi": _num(row.get("hi")),
        "confidence": _confidence(n),
    }
    if n < MIN_PROJECT_N:
        return {"scenario": scenario, "abstained": True,
                "reason": f"only {n} comparable {genre} titles in {year}; too few to project a distribution",
                "crowd": [], "trajectory": [], "genres": [], "traces": traces, "transport": transport}

    crowd_res = run(
        "SELECT m.name AS name, round(m.rank, 1) AS rating "
        "FROM imdb.movies m INNER JOIN imdb.genres g ON g.movie_id = m.id "
        f"WHERE g.genre = {gq} AND m.year = {year} AND m.rank > 0 "
        "ORDER BY m.rank DESC LIMIT 40",
        note=f"the crowd: real {genre} titles in {year}",
    )
    crowd = [{"name": r["name"], "rating": _num(r.get("rating"))}
             for r in crowd_res.get("rows", [])] if crowd_res.get("status") == "ok" else []

    traj_res = run(
        "SELECT m.year AS year, round(avg(m.rank), 2) AS mean, round(stddevPop(m.rank), 2) AS spread, "
        "count() AS n FROM imdb.movies m INNER JOIN imdb.genres g ON g.movie_id = m.id "
        f"WHERE g.genre = {gq} AND m.rank > 0 AND m.year BETWEEN {year - window} AND {year + window} "
        "GROUP BY year ORDER BY year",
        note=f"time multiverse: {genre} across years",
    )
    trajectory = [{"year": _int(r.get("year")), "mean": _num(r.get("mean")),
                   "spread": _num(r.get("spread")), "n": _int(r.get("n"))}
                  for r in traj_res.get("rows", [])] if traj_res.get("status") == "ok" else []

    genres_res = run(
        "SELECT g.genre AS genre, round(avg(m.rank), 2) AS mean, round(stddevPop(m.rank), 2) AS spread, "
        "count() AS n FROM imdb.movies m INNER JOIN imdb.genres g ON g.movie_id = m.id "
        f"WHERE m.year = {year} AND m.rank > 0 GROUP BY genre HAVING n >= 15 ORDER BY mean DESC LIMIT 14",
        note=f"genre multiverse: all genres in {year}",
    )
    genres = [{"genre": r["genre"], "mean": _num(r.get("mean")), "spread": _num(r.get("spread")),
               "n": _int(r.get("n"))} for r in genres_res.get("rows", [])] if genres_res.get("status") == "ok" else []

    return {"scenario": scenario, "abstained": False, "reason": None,
            "crowd": crowd, "trajectory": trajectory, "genres": genres,
            "traces": traces, "transport": transport}
