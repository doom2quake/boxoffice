# BoxOffice Brain — Winning Playbook

How to present BoxOffice Brain to win the ClickHouse track of Agentic Cinema: The
Blockbuster Hackathon (Devpost). This is grounded in how comparable Google
Cloud / Gemini / ADK hackathons and ClickHouse-sponsored hackathons were actually
won, mapped onto our four judging criteria. Every claim about a past event is
cited. No fabrication.

Event facts we are optimizing for (from the official rules page,
https://agentic-cinema.devpost.com/rules):

- Five partner tracks, each with 1st / 2nd / 3rd prizes of $7,500 / $4,500 /
  $3,000. We are in the ClickHouse track, so we compete only against other
  ClickHouse-track entries, not against IBM/Grafana/Parallel/Replit entries.
- Stage One is pass/fail baseline viability: all requirements met, addresses the
  challenge, actually applies the Partner data and Google Cloud.
- Stage Two is four equal-weighted criteria: Technological Implementation, Design,
  Potential Impact, Quality of the Idea (verbatim wording in section 3).
- Hard requirement: the code must show runtime imports/calls to Google Cloud and
  the Partner service, "not just named in the README". For our track that means
  the official ClickHouse MCP server (mcp-clickhouse) must be used at runtime.
- Deliverables: a hosted project URL, a public repo with an OSI-approved
  open-source license, a text writeup, and a demo video of max 3 minutes that
  shows the functioning project.

---

## 1. Past winners of comparable hackathons, and why they won

There is no prior edition of Agentic Cinema, so we lean on the three closest
analogue families: Google Cloud / ADK agent hackathons, ClickHouse-sponsored
agent hackathons, and general data-agent hackathons. Sources cited inline.

### 1a. Google Cloud / Gemini / ADK agent hackathons (Devpost)

The reference event is the Agent Development Kit Hackathon with Google Cloud
(10,400+ participants, 62 countries, 477 projects). Organizer writeup:
https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights

- Grand Prize: SalesShortcut (Merdan Durdyyev, Sergazy Nurbavliyev). An
  autonomous AI sales-development-rep system. Multi-agent architecture: the
  builders documented 34 agents (21 LLM agents, 7 sequential, 1 parallel, 2
  custom, 1 loop) across 5 Cloud Run microservices, on Vertex AI, BigQuery,
  Cloud Run, Pub/Sub, Firebase Studio. Devpost page:
  https://devpost.com/software/salesshortcut ; builder writeup:
  https://medium.com/@sernur213/salesshortcut-building-an-autonomous-ai-sales-team-with-multi-agent-ai-architecture-using-google-e794c2c72152
  Why it won / presentation traits: an authentic first-person problem story
  (a freelancer grinding cold calls), a clear four-step pipeline framed with
  plain-language "what it does", a live hosted URL on Cloud Run, full source,
  concrete numbers that convey real scale (the agent counts and service list),
  frank "challenges we ran into" sections, and a credible post-hackathon future
  (they moved to launch it). It reads as a real product, not a proof of concept.
- Regional winners, all real multi-agent systems solving a specific audience's
  problem: Energy Agent AI (energy customer management, North America), Edu.AI
  (Brazilian education, essay grading + study plans, LatAm), GreenOps (cloud
  sustainability auditing, APAC), Nexora-AI (personalized education, EMEA).
- Honorable mentions that are directly analogous to us: Particle Physics Agent
  (natural language into validated Feynman diagrams "using real physical laws
  and high-fidelity data" — grounding in real data, exactly our stance) and
  TradeSageAI (multi-agent financial analysis on ADK, Agent Engine, Cloud Run,
  Vertex AI).

The organizer's own summary of why these won: winners "demonstrated exceptional
skill, ingenuity, and a deep understanding of ADK", and the event rewarded real
orchestration of multiple agents to automate processes, analyze data, improve
service, and generate content (same source URL above).

### 1b. ClickHouse-sponsored agent hackathons

Primary source: ClickHouse's own writeup of the NYC AI Agents Hackathon, where
ClickHouse was the only database sponsor:
https://clickhouse.com/blog/nyc-ai-agents-hackathon

- 1st place: VitalSignal — an autonomous agent that delivers personalized global
  disease-outbreak alerts by monitoring health signals and regional risk. ClickHouse
  stored user profiles, streamed JSON alerts, and tool metadata. Stated reasons it
  won: it "tackled a genuine personal need" with "a complete, polished end-to-end
  workflow", and the builder showed "disciplined" execution (core decisions first,
  MVP focus, knowing when to ship). The builder's quote ClickHouse chose to feature:
  "I never once had to worry about database limitations... that confidence let me
  stay ambitious."
- 2nd place: RedBot — an agent that probes chatbot endpoints for prompt injection
  and data leakage, then generates ROI-aware remediation. ClickHouse handled large
  attack datasets and fast queries across endpoints and severity. Stated reasons:
  it addressed "a real security gap in production AI deployments" and the team
  "prioritized functional prototypes over feature creep".

ClickHouse states explicitly what made the strong projects strong (same URL):
clear specific user problems; narrow, usable scope shipped completely; a
real-time data loop of ingest to store to compute to act; and ClickHouse as the
"source of truth" that prevents mid-build performance walls.

How ClickHouse frames a good analytics agent (directly relevant to our pitch):

- ClickHouse Agents beta: agents should ground responses in actual query
  execution "rather than hallucinated outputs", the MCP server is "read-only by
  default", and best-practice "skills" ground the agent instead of letting it
  invent SQL. https://clickhouse.com/blog/clickhouse-agents-beta
- Building a data platform for agents: agents "inspect available tools, reason
  over schema, generate SQL, run queries, observe the results, and iterate";
  the MCP interface lets them "list databases, inspect tables, and run queries
  through a standard MCP interface".
  https://clickhouse.com/blog/building-a-data-platform-for-agents
- Agentic Analytics Benchmark: a strong analytics agent is measured on pass rate
  (correctness), token cost (efficiency), and wall-clock time; the biggest
  failure mode is a wrong plan (53–82% of failures), and weak agents fail at
  schema discovery (finding the right tables); the benchmark validates answers
  by result-set equivalence so an agent cannot pass with "plausible-sounding but
  incorrect results". https://clickhouse.com/blog/agentic-analytics-benchmark-data-agent-mnist

### 1c. General AI-agent / data-analytics hackathons

- DataHub "Build with DataHub: The Agent Hackathon" judging criteria are the
  clearest analogue to ours: Depth of platform usage, Technical Execution,
  Real-World Usefulness, Submission Quality; and they ask for "sample generated
  outputs in an examples/ folder so judges can evaluate quality without running
  the project themselves", and outputs "your data team would actually merge".
  https://datahub.com/blog/build-with-datahub-agent-hackathon/
- Devpost's own judges (Square, Google, Databricks, Atlassian, NEAR) on how to
  win: "The demo video gives the most amount of scope" (Richard Moot, Square);
  actually play/use the project, don't rely on the video alone (Kelvin Boateng,
  Google); "Presentation and storytelling matters and it can be a huge part of
  your success" (Karen Bajza-Terlouw, Databricks); meet every requirement,
  because "it's not sufficient to just build the app and have it out there"
  (Warren Marusiak, Atlassian); over-indexing on one criterion "really negatively
  impacts the score"; judges penalize reskinned templates and recycled prior
  projects. https://info.devpost.com/blog/hackathon-judging-tips
- Devpost winners on process: scope to "2-3 must-have features that are necessary
  to demonstrate that this is a viable idea", adopt a prototype mindset, and
  submit early to avoid the last-day frenzy.
  https://info.devpost.com/blog/tips-from-hackathon-winners

---

## 2. The recurring winning traits

Distilled across all the sources above, winners consistently show:

1. A working, watchable demo. The video is the single highest-leverage artifact
   ("gives the most amount of scope"), and judges also try the live URL.
2. One crisp, real problem for a real audience, stated in the first breath — not
   a platform tour.
3. Narrow scope shipped completely (an end-to-end loop), not a broad half-built
   feature list. ClickHouse and DataHub both say this outright.
4. One memorable wow beat the whole story is built around.
5. Genuinely load-bearing sponsor tech, visible at runtime, not name-dropped.
   Our rules make this a Stage-One gate.
6. Honest grounding in real data. This is a differentiator, not a caveat:
   ClickHouse explicitly rewards agents that ground answers in query results and
   do not hallucinate. BoxOffice Brain's refusal to invent numbers is a feature
   to headline.
7. A clean writeup and README with an architecture diagram, concrete numbers,
   and a "challenges / what's next" section that signals real engineering.
8. A story of authentic motivation and credible impact beyond the hackathon.

---

## 3. Mapping to our four judging criteria

The four Stage-Two criteria are equal-weighted, so we must score well on all
four; over-indexing on one hurts the total (Devpost judges, section 1c). Verbatim
wording is from https://agentic-cinema.devpost.com/rules

### Technological Implementation

Verbatim: "How well is the project built, and how effectively does it use Google
Cloud and the Partner services as part of the solution?"

What winners did: SalesShortcut showed a real, non-trivial multi-agent graph on
named Google Cloud services and could prove each one ran. ClickHouse winners made
the database the source of truth in a live loop.

What BoxOffice Brain should show and say:

- Put the load-bearing ClickHouse MCP call on screen. Run `boxoffice mcp-check`
  and point at the advertised tool list `['list_databases','list_tables',
  'run_query']` and a real `run_query` call with latency and rows. Say out loud:
  "those tool names are the server's, not ours."
- Show the two-step query flow live in the UI: Step 1 routes to a template, Step
  2 is the exact SQL that ran with a `clickhouse_mcp` grounding trace and latency,
  Step 3 is a follow-up query scoped to the cohort the first query found.
- Show Google Cloud used at runtime, not just imported. This is our known gap:
  Gemini/ADK are wired and importable but the shipped numbers came from the
  keyless router (see HONESTY.md). To maximize this criterion, run at least one
  hero question through the real Gemini/ADK path against a funded Vertex project
  before submission, capture it on video, and keep the deterministic no-LLM mode
  as the reproducibility story rather than as the whole story. If a funded run
  is impossible, show the ADK graph executing (the supervisor and three skills
  from agent-core) and be explicit that the model call is the one dependency a
  judge must supply — do not imply Gemini produced numbers it did not.
- Show the guardrails as engineering: read-only screen, data-scope allowlist,
  action limiter, and the persisted guardrail audit trail. This reads as "built
  well", which is half of this criterion.

### Design

Verbatim: "Does the project deliver a complete, coherent product experience not
just a technical proof of concept?"

What winners did: VitalSignal won on "a complete, polished end-to-end workflow";
SalesShortcut reads as a product with a clear pipeline and a hosted UI.

What BoxOffice Brain should show and say:

- Lead with the UI, not the CLI. The green LIVE banner with the endpoint, the
  four labelled steps, the grounding trace, and the right-column agent activity
  log make it feel like a product. Judges "actually play the project" (Google
  judge), so the hosted URL must load and answer on the first click.
- Make the honest-state design visible as polish, not apology: the banner turns
  amber and says "recorded transcript, not live" when opened as a file. That is
  a designed trust signal; narrate it as one.
- Keep the scope tight and coherent: one clear task (studio catalogue questions),
  four labelled steps, one abstain path, one guardrail path. Do not add panels
  that do not answer a real question.

### Potential Impact

Verbatim: "Does the project make a credible, specific case for solving a real
problem for a real audience and does the solution actually address it based on
what's demonstrated?"

What winners did: winners named a real audience and a real pain (health-crisis
alerts faster than the news; production chatbot security; SDR grind) and showed
the solution addressing it on screen.

What BoxOffice Brain should show and say:

- Name the audience precisely: studio and distributor analysts who need catalogue
  and performance answers now and cannot trust an LLM that invents box-office
  numbers. The pain is not "querying is hard", it is "an analyst cannot ship a
  number they cannot defend."
- Tie impact to the demonstrated behavior: the agent quotes only numbers that
  came back in a row and abstains otherwise, so the answer is defensible in a
  greenlight meeting. Impact is judged "based on what's demonstrated", so the
  abstain and the grounding trace ARE the impact argument — show them.
- Give one concrete, believable outcome sentence: an analyst gets a defensible,
  sourced answer to a catalogue question in seconds without writing SQL or risking
  a hallucinated figure.

### Quality of the Idea

Verbatim: "Is this a creative, non-obvious use of Google Cloud and the Partner
services and does the team show genuine understanding of the problem space?"

What winners did: honorable mentions like Particle Physics Agent won attention
for a non-obvious, rigorously grounded use of real data; judges penalize obvious
reskins and reward "unusual and fresh" approaches (NEAR judge).

What BoxOffice Brain should show and say:

- The non-obvious idea is honest grounding as the product, not a nice-to-have:
  most text-to-SQL demos brag about fluency; ours brags about refusing to answer
  when the data cannot. In an entertainment context full of confident-sounding
  numbers, "an agent that will not lie about box office" is the fresh angle.
- Show genuine understanding of ClickHouse: the read-only MCP path, the
  cohort-scoped follow-up query, and the guardrails against table functions like
  `url()` reaching the cloud metadata endpoint. That specificity signals we know
  the platform, which is exactly what this criterion rewards.
- Show genuine understanding of the Google Cloud stack: the ADK supervisor plus
  three skills, and Gemini as the planner, used deliberately (planning is the
  top differentiator in ClickHouse's benchmark) rather than as a chatbot.

---

## 4. Concrete recommendations: writeup, video, deck

### The narrative arc (use it in all three artifacts)

1. Hook / problem (real audience): "A studio analyst asks a plain-English
   catalogue question. The one thing they cannot do is walk into a greenlight
   meeting with a number they cannot defend. Generic LLMs invent box-office
   numbers with total confidence."
2. The idea: "BoxOffice Brain writes read-only ClickHouse SQL, runs it through
   ClickHouse's own MCP server, and quotes only numbers that came back in a row.
   If the rows cannot answer, it says so."
3. Proof the sponsor tech is real (the wow beat, below).
4. The hero question, end to end, live in the UI.
5. The two honesty beats: the abstain, and the guardrail refusal.
6. Impact + what's next, close on the tagline.

### The single wow beat to build the whole story around

The wow is not a fancy chart. It is the moment the demo proves the numbers are
real and the sponsor is load-bearing: run the hero question live, then show that
the exact SQL on screen was executed by the official ClickHouse MCP server's
`run_query` tool (visible tool list + latency + rows), and then ask a question
the data cannot answer and watch the agent abstain instead of inventing a figure.
"It ran real ClickHouse SQL through ClickHouse's own server, and when it could
not answer, it refused to make something up." That contrast — real number, then
honest refusal — is the beat. Build every artifact to land it.

### What to put on screen (video, in order, under 3:00)

- 0:00–0:20 One sentence of problem over the UI with the green LIVE banner.
- 0:20–0:50 `boxoffice mcp-check`: highlight `run_query` in the advertised tool
  list and the real latency/rows. Say the tool names are the server's.
- 0:50–1:40 Hero question in the UI: Step 1 template, Step 2 exact SQL + grounding
  trace, Step 3 cohort-scoped follow-up, Step 4 answer where every number traces
  to a row above.
- 1:40–2:05 Ask the unanswerable question: the agent abstains and names the data
  it would need. No invented number.
- 2:05–2:25 The guardrail entry: `url()` to the cloud metadata endpoint rejected,
  `system.users` rejected, `DROP TABLE` rejected — real tool return values.
- 2:25–2:45 One line on Google Cloud: Gemini plans, ADK orchestrates the
  supervisor plus three skills. Show the graph or a real Gemini-path run if funded.
- 2:45–3:00 Impact sentence + tagline. Show the hosted URL and repo link.

Keep it real screen capture with a calm voiceover. Judges watch the video first
and it "gives the most amount of scope" — so the working product must be on
screen the whole time, never slides-only.

### The Devpost writeup structure

- One-line elevator pitch + the tagline at the very top.
- "The problem" (2–3 sentences, real audience).
- "What it does" with the plain-language four-step pipeline (this mirrors the
  SalesShortcut structure that worked).
- "How it works" with the architecture diagram: question to router/Gemini plan
  to read-only SQL to ClickHouse MCP `run_query` to grounded answer, with the
  guardrail layer drawn in.
- "Proof it is real" block: the `mcp-check` output, the parity result
  (offline vs http vs mcp IDENTICAL), and a link to HONESTY.md. Borrow DataHub's
  pattern: include sample outputs so judges can evaluate quality without running
  anything.
- "How we used Google Cloud and ClickHouse" — name the exact runtime calls, since
  the rules require runtime evidence "not just named in the README".
- "Challenges" and "What's next" — signals real engineering and future impact.
- Hosted URL, repo URL, OSI license (MIT is fine), 3-min video embed.

### The deck

Keep it to the arc above: title + tagline, problem, the idea, one architecture
slide, one "proof the MCP call is load-bearing" slide, one "it refuses to lie"
slide, impact + what's next. One idea per slide. No wall of features.

### Candidate taglines

- Primary: "It runs real ClickHouse SQL, and it will not lie about box office."
- Alternatives:
  - "Ask in English. Get a number you can defend."
  - "A cinema-analytics agent that quotes rows, not guesses."
  - "Real ClickHouse queries. Honest answers. No invented numbers."

### Pitfalls to avoid

- No live demo, or a hosted URL that does not answer on first click. Judges play
  the project; a dead link is fatal.
- LLM-tells in the writeup and video: no "unleash", "revolutionize", "seamless",
  no em-dashes, no generic AI voiceover reading marketing copy. Write like an
  engineer describing a real system.
- Naming the sponsor without a real runtime call. Our rules make this a
  Stage-One fail. Never let the MCP path silently fall back to in-process tools
  on camera; the `mcp-check` proof exists precisely to prevent this.
- Over-claiming Gemini. Do not imply the model produced numbers when the shipped
  demo used the keyless router. Either run the funded Gemini path on camera or
  state clearly that the model is the one dependency a judge supplies. Honesty
  here is on-brand and protects us from a fact-check.
- Over-indexing on one criterion (e.g. all guardrails, no product experience).
  All four criteria are equal-weighted; the Design and Impact slides matter as
  much as the tech.
- Feature creep. Ship the narrow loop completely. Both ClickHouse and Devpost
  winners say a small complete thing beats a broad half-built one.
- Recycled or reskinned feel. Judges flag it. Lean into the one thing no generic
  text-to-SQL demo does: honest abstention.

---

## 5. ClickHouse-track and Google-Cloud rules specifics judges will reward

These are the concrete, checkable things that move Stage One and Technological
Implementation for our exact track.

### The load-bearing ClickHouse MCP `run_query` call

- The rule for our track: the project must "actively use ClickHouse at runtime
  via the official ClickHouse MCP server (mcp-clickhouse)"
  (https://agentic-cinema.devpost.com/details/clickhouse-resources). We already
  satisfy this: `BOX_TRANSPORT=mcp` launches `uvx --python 3.11 mcp-clickhouse`
  and every query goes through the server's `run_query` tool.
- Make it visibly central: show `mcp-check` printing the server's advertised
  tools and calling `run_query` with real latency and rows; put the
  `-- clickhouse_mcp: elapsed_ms=...` grounding trace under the SQL in the UI;
  and state in the writeup that this is ClickHouse's own server, not a wrapper of
  ours with an MCP-shaped name.
- Use ClickHouse Cloud, not only the public playground, if time allows. New
  accounts get $400 in credits; the rules resources point to spinning up a
  ClickHouse Cloud service. A private service reads as more "production-ready"
  than the demo playground and removes the HONESTY.md caveat that we only ran
  against the public endpoint. If we stay on the playground, keep the caveat
  honest but note anyone can reproduce our results without a key (a reproducibility
  strength).
- Consider adopting the ClickHouse Agent Skills package (schema design, query
  optimization, ingestion patterns) that the resources page recommends; it maps
  directly to the benchmark's finding that planning and schema discovery separate
  strong agents from weak ones.

### Gemini-only compliance (Google Cloud rules)

- The rules prohibit competing AI providers (AWS, Microsoft, OpenAI, Anthropic)
  and accept only google-adk, google-genai, google-generativeai,
  google-cloud-aiplatform. Confirm the shipped code imports and calls only those
  for the model path, and that no other provider SDK is a runtime dependency.
- Show Google Cloud used at runtime, not just imported. This is our weakest point
  against the rules' "runtime imports/calls ... not just named in the README".
  Prioritize one funded Gemini/ADK run on camera; failing that, show the ADK
  graph executing and be explicit that the model call is the supplied dependency.

### Grounded, honest numbers as a scored strength

- ClickHouse's published stance is that trustworthy agents ground answers in
  query results and do not hallucinate, the MCP server is read-only by default,
  and result-set validation (not model assertion) is how correctness is judged
  (benchmark + agents-beta URLs in section 1b). BoxOffice Brain is built exactly
  this way: read-only SQL, quote-only-what-returned, abstain otherwise. Frame
  honest grounding as the product's core value, because it aligns with what the
  sponsor itself says good looks like.
- The parity check (offline vs http vs mcp IDENTICAL, `scripts/verify_parity.py`)
  is our proof that the offline demo is not a mock. Show it; it converts "trust
  me" into "verify me", which is precisely the honesty posture ClickHouse rewards.

### How to make ClickHouse usage visibly central (checklist)

- The UI grounding trace line names `clickhouse_mcp` and shows latency on every
  answer.
- The video spends its strongest 60 seconds on the MCP proof and the live query,
  not on slides.
- The architecture diagram puts ClickHouse MCP `run_query` on the critical path
  between the plan and the answer, with the guardrail layer wrapping it.
- The writeup's "How we used ClickHouse" section names the exact runtime call
  and links the `mcp-check` capture (`docs/live-proof.txt`).
- The abstain and guardrail beats both terminate at "we would not return a number
  the ClickHouse rows did not support", tying every honesty beat back to the
  database as the source of truth.

---

## Sources

- Agentic Cinema rules (judging criteria, requirements): https://agentic-cinema.devpost.com/rules
- Agentic Cinema resources: https://agentic-cinema.devpost.com/resources
- Agentic Cinema ClickHouse track resources: https://agentic-cinema.devpost.com/details/clickhouse-resources
- ADK Hackathon winners and highlights: https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights
- SalesShortcut (Devpost): https://devpost.com/software/salesshortcut
- SalesShortcut builder writeup (Medium): https://medium.com/@sernur213/salesshortcut-building-an-autonomous-ai-sales-team-with-multi-agent-ai-architecture-using-google-e794c2c72152
- ClickHouse NYC AI Agents Hackathon (VitalSignal, RedBot): https://clickhouse.com/blog/nyc-ai-agents-hackathon
- ClickHouse Agents beta: https://clickhouse.com/blog/clickhouse-agents-beta
- ClickHouse building a data platform for agents: https://clickhouse.com/blog/building-a-data-platform-for-agents
- ClickHouse Agentic Analytics Benchmark: https://clickhouse.com/blog/agentic-analytics-benchmark-data-agent-mnist
- DataHub Agent Hackathon (judging criteria analogue): https://datahub.com/blog/build-with-datahub-agent-hackathon/
- Devpost: how to win, advice from 5 judges: https://info.devpost.com/blog/hackathon-judging-tips
- Devpost: tips from hackathon winners: https://info.devpost.com/blog/tips-from-hackathon-winners
