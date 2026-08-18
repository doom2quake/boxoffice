"""Named, parameterised analytical queries, and the intent router that picks one.

The keyless path used to run one canned query no matter what was asked, so a
question about a different market got the same answer as the demo question.
That is a grounding failure dressed as an answer.

Here every supported question maps to a NAMED template with typed parameters.
Anything the router cannot map to a template is refused with
`UnsupportedQuestion` and the agent abstains, saying what it does support. No
template interpolates free text: identifiers are fixed and literals are
escaped, so the router cannot be talked into new SQL.

The SQL is deliberately written in the intersection of ClickHouse SQL and
SQLite SQL (`CASE WHEN` rather than `countIf`) so the identical statement runs
on the live warehouse and on the offline snapshot. That is what makes
`scripts/verify_parity.py` a real comparison instead of two different queries.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

DATABASE = "imdb"


class UnsupportedQuestion(ValueError):
    """The router has no grounded template for this question."""


def quote(value: str) -> str:
    """Escape a string literal for SQL. Only used for values, never identifiers."""
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


@dataclass(frozen=True)
class PlannedQuery:
    name: str
    sql: str
    note: str
    params: dict[str, Any]


# --- templates ----------------------------------------------------------------

def genre_underperformance(current_year: int, prior_year: int, min_titles: int = 20) -> PlannedQuery:
    """Genres whose mean IMDb rating fell from `prior_year` to `current_year`."""
    current_year, prior_year, min_titles = int(current_year), int(prior_year), int(min_titles)
    sql = (
        "SELECT g.genre AS genre,\n"
        f"       avg(CASE WHEN m.year = {current_year} THEN m.rank END) AS rating_current,\n"
        f"       avg(CASE WHEN m.year = {prior_year} THEN m.rank END) AS rating_prior,\n"
        f"       count(CASE WHEN m.year = {current_year} THEN 1 END) AS titles_current,\n"
        f"       count(CASE WHEN m.year = {prior_year} THEN 1 END) AS titles_prior\n"
        f"FROM {DATABASE}.genres AS g\n"
        f"INNER JOIN {DATABASE}.movies AS m ON m.id = g.movie_id\n"
        f"WHERE m.year IN ({current_year}, {prior_year}) AND m.rank > 0\n"
        "GROUP BY g.genre\n"
        f"HAVING count(CASE WHEN m.year = {current_year} THEN 1 END) >= {min_titles}\n"
        f"   AND count(CASE WHEN m.year = {prior_year} THEN 1 END) >= {min_titles}\n"
        "ORDER BY rating_current - rating_prior ASC"
    )
    return PlannedQuery(
        name="genre_underperformance", sql=sql,
        note=f"mean rating by genre, {current_year} vs {prior_year}",
        params={"current_year": current_year, "prior_year": prior_year, "min_titles": min_titles},
    )


def genre_worst_titles(genre: str, year: int, limit: int = 5) -> PlannedQuery:
    """Lowest-rated titles inside ONE genre and year.

    This is the correlated signal, and it is joined to the genre/year the
    headline result actually named. The previous build pulled a global
    'most negative' row and labelled an unrelated cohort as the explanation.
    """
    year, limit = int(year), max(1, min(int(limit), 50))
    sql = (
        "SELECT m.name AS title, m.year AS year, m.rank AS rating\n"
        f"FROM {DATABASE}.genres AS g\n"
        f"INNER JOIN {DATABASE}.movies AS m ON m.id = g.movie_id\n"
        f"WHERE g.genre = {quote(genre)} AND m.year = {year} AND m.rank > 0\n"
        f"ORDER BY m.rank ASC, m.name ASC\n"
        f"LIMIT {limit}"
    )
    return PlannedQuery(
        name="genre_worst_titles", sql=sql,
        note=f"lowest-rated {genre} titles in {year}",
        params={"genre": genre, "year": year, "limit": limit},
    )


def top_titles(year: int, limit: int = 5) -> PlannedQuery:
    """Highest-rated titles in one year."""
    year, limit = int(year), max(1, min(int(limit), 50))
    sql = (
        "SELECT m.name AS title, m.year AS year, m.rank AS rating\n"
        f"FROM {DATABASE}.movies AS m\n"
        f"WHERE m.year = {year} AND m.rank > 0\n"
        f"ORDER BY m.rank DESC, m.name ASC\n"
        f"LIMIT {limit}"
    )
    return PlannedQuery(name="top_titles", sql=sql, note=f"highest-rated titles of {year}",
                        params={"year": year, "limit": limit})


def genre_volume(year: int) -> PlannedQuery:
    """How many rated titles each genre released in one year."""
    year = int(year)
    sql = (
        "SELECT g.genre AS genre, count(*) AS titles, avg(m.rank) AS rating\n"
        f"FROM {DATABASE}.genres AS g\n"
        f"INNER JOIN {DATABASE}.movies AS m ON m.id = g.movie_id\n"
        f"WHERE m.year = {year} AND m.rank > 0\n"
        "GROUP BY g.genre\n"
        "ORDER BY titles DESC"
    )
    return PlannedQuery(name="genre_volume", sql=sql, note=f"rated titles per genre in {year}",
                        params={"year": year})


#: Questions the agent can ground. Shown to the user when it abstains.
SUPPORTED = (
    "which genres underperformed in <year> versus <prior year>",
    "the best rated titles of <year>",
    "how many titles each genre released in <year>",
)

_YEAR = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")


# --- router -------------------------------------------------------------------

def route(question: str) -> PlannedQuery:
    """Map a plain-English question to a named template, or raise."""
    q = (question or "").lower()
    years = [int(y) for y in _YEAR.findall(q)]

    if any(w in q for w in ("underperform", "under-perform", "declin", "worse", "dropped", "fell", "down")):
        if len(years) >= 2:
            current, prior = max(years[0], years[1]), min(years[0], years[1])
        elif len(years) == 1:
            current, prior = years[0], years[0] - 1
        else:
            raise UnsupportedQuestion(
                "an underperformance question needs a year to compare (e.g. '1999 vs 1998')"
            )
        return genre_underperformance(current, prior)

    if any(w in q for w in ("best", "top", "highest rated", "highest-rated")):
        if not years:
            raise UnsupportedQuestion("a 'best titles' question needs a release year")
        return top_titles(years[0])

    if any(w in q for w in ("how many", "volume", "count", "released")):
        if not years:
            raise UnsupportedQuestion("a release-volume question needs a year")
        return genre_volume(years[0])

    raise UnsupportedQuestion("no grounded query template matches this question")
