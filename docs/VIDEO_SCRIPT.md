# BoxOffice Brain — 3-minute demo script (Multiverse Projector)

Real screen capture of the live demo, calm voiceover. Target 2:45, hard cap 3:00.
Record against the live URL so the green LIVE banner is real:
https://boxoffice-brain-744757588430.us-central1.run.app

Tagline to land at the end: "It runs real ClickHouse SQL, and it will not invent a
box-office number."

---

## 0:00 - 0:18  Hook + the toy
On screen: the Multiverse Projector loaded, green LIVE banner visible.
Say: "This is BoxOffice Brain. You pick a genre and a year, and it projects the real
crowd of comparable films. Every dot, line and number you are about to see is a row
that ClickHouse actually returned."

## 0:18 - 0:48  Project a scenario
Do: genre Drama, year 1999, click Project. Let the crowd of films settle onto the
0 to 10 rating axis; the mean line and the spread band appear; the confidence badge
reads HIGH.
Say: "Here is Drama in 1999. Eight hundred and nine real titles, a mean rating of
6.1, the real spread, the real range. This is not a model guessing a shape. It is
the actual distribution of what comparable films did."

## 0:48 - 1:22  The multiverse
Do: on the Multiverse Rail, flip TIME (scrub the year trajectory for that genre),
then switch to GENRE (click through sibling genres in 1999). The crowd re-forms each
time.
Say: "Now the fun part. Flip through parallel universes. The same scenario across
time, and across genres. Each universe is its own real cohort, so you can see where
your idea would actually land."

## 1:22 - 1:48  The honesty beat (the wow)
Do: pick a thin cohort (for example a genre and year with very few titles) and click
Project. The projector shows the honest abstain state, naming that there are too few
comparable titles to project.
Say: "And when the data cannot support a projection, it refuses. No invented curve,
no fake number. In an industry full of confident guesses, this is the one that will
tell you it does not know."

## 1:48 - 2:12  Under the hood (load-bearing ClickHouse)
Do: open the Advanced / Under the hood accordion. Show the grounding chip expand to
the real SQL and "run_query via the official ClickHouse MCP server" with the latency.
Say: "Under the hood, every projection is read-only SQL run through ClickHouse's own
MCP server. That is the official mcp-clickhouse run_query tool, not a wrapper of
ours. The number on screen and the row in the warehouse are the same thing."

## 2:12 - 2:36  Ask in plain English (Gemini + ADK)
Do: in the Ask panel, type "which genres underperformed in 1999 versus 1998" and run
it. Show the grounded answer; open "show how" to reveal the SQL Gemini wrote.
Say: "You can also just ask. Gemini, on Vertex through the Agent Development Kit,
plans the analysis and writes the SQL itself, then calls the same ClickHouse tool.
It only quotes numbers that came back in a row, and it abstains otherwise."

## 2:36 - 2:50  Close
On screen: the projector, then a beat on the repo + live URL.
Say: "BoxOffice Brain. Gemini and ADK, over the official ClickHouse MCP server. It
runs real ClickHouse SQL, and it will not invent a box-office number."

---

Notes for the recording:
- Keep the working product on screen the whole time; no slides.
- Let the crowd animation finish before speaking over it.
- The abstain beat is the memorable moment; give it a full breath.
- If a live query is slow, wait it out on camera rather than cutting; the latency
  chip proves it is real.
