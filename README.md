# Multi-Agent Code Security Scanner

A small AI-powered service that reviews pull requests for security bugs.

You point it at a PR (or paste a few files), and a team of specialized agents
takes a look: one runs fast pattern-based checks, one reads the code with an
LLM, one searches a CVE knowledge base for related public vulnerabilities,
one calibrates the severity, and the last one writes a short summary you can
drop into a PR comment.

It's built with **FastAPI**, **LangGraph**, **PostgreSQL + pgvector**, and
ships in a single **Docker** image. There's an **AWS Fargate** task
definition included for deploys.

> Why I built this: code review is the single best place to catch security
> bugs, but reviewers are busy and humans miss things that machines find
> easily — and machines miss things that LLMs catch instantly. Combining
> both turned out to work surprisingly well.

---

## What it actually does

When you submit a scan, the request flows through a **LangGraph** pipeline
of five agents:

```
                 ┌────────────────────────┐
files in ───────▶│  1. Static Analyzer    │  regex + AST rules (no LLM)
                 │     CWE-tagged rules   │  catches secrets, eval, pickle, ...
                 └───────────┬────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ 2. Vulnerability Detector│  LLM agent for context-dependent
                 │    (gpt-4o-mini)        │  bugs: authz, SSRF, taint flow
                 └───────────┬────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ 3. Merger              │  dedupes overlapping findings
                 └───────────┬────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ 4. CVE Researcher (RAG)│  pgvector cosine search over
                 │    over CVE knowledge  │  embedded CVE descriptions
                 └───────────┬────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ 5. Severity Assessor   │  bumps/demotes severity using
                 │                        │  CVSS + clustering signals
                 └───────────┬────────────┘
                             ▼
                 ┌────────────────────────┐
                 │ 6. Report Generator    │  LLM writes the executive summary
                 └───────────┬────────────┘
                             ▼
                       findings + summary
                       persisted in Postgres
```

A scan record is stored for every run, so you can come back later and see
exactly what was flagged, when, and on which commit.

---

## Quick start

### Option 1 — Run locally (no Docker, no Postgres needed)

The fastest way to see it work. Uses SQLite under the hood so there's
nothing to install beyond Python.

```bash
git clone https://github.com/saloni111/Scanner && cd Scanner

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

make local        # starts the API on http://127.0.0.1:8000
```

Then in a second terminal:

```bash
make scan-demo    # POSTs the bundled vulnerable file and prints findings
```

You should get back **9 findings in under 100ms** — a hardcoded AWS key,
`pickle.loads`, `subprocess(shell=True)`, a SQL injection via f-string,
weak MD5, debug mode on, and more. Each one comes with the file path,
line number, CWE id, and a fix recommendation.

Want to try it interactively? Open **http://127.0.0.1:8000/docs** in your
browser — the Swagger UI lets you paste any code snippet and hit "Execute"
without writing a single curl command.

> **Optional:** add `OPENAI_API_KEY=sk-...` to a `.env` file to unlock
> the LLM agent (catches context-dependent bugs like missing auth checks,
> SSRF, taint-flow issues) and the AI-written scan summary. The scanner
> works fully without it — the LLM agents just skip gracefully.

---

### Option 2 — One-click cloud deploy

[**Deploy to Render**](https://render.com/deploy?repo=https://github.com/saloni111/Scanner) — reads `render.yaml` from the repo, provisions a free Postgres + the API container, runs migrations, and gives you a live public HTTPS URL in ~5 minutes.

---

### Option 3 — Full stack with Docker

Spins up Postgres (with pgvector), runs migrations, seeds the CVE
knowledge base, and starts the API — all in one command.

```bash
cp .env.example .env        # optionally paste OPENAI_API_KEY here
docker compose up --build
```

Once it's running, same as above:

```bash
make scan-demo
open http://localhost:8000/docs
```

---

## Using it on a real PR

1. Set `GITHUB_TOKEN` in `.env` (a fine-grained PAT with read access to the
   repo's pull requests is enough).
2. Hit `POST /scans/pr` with the repo + PR number:

```bash
curl -X POST http://localhost:8000/scans/pr \
  -H "Content-Type: application/json" \
  -d '{"repository": "acme/api", "pr_number": 142, "triggered_by": "saloni"}'
```

The scan starts in the background. Poll `GET /scans/{id}` to see it
finish. The scanner pulls each changed file from GitHub, runs it through
the agents, and persists the findings.

---

## API at a glance

| Method | Path | What it does |
|---|---|---|
| `GET`  | `/health` | Liveness probe |
| `POST` | `/scans` | Scan a list of files (synchronous) |
| `POST` | `/scans/pr` | Scan a GitHub PR (async, returns immediately) |
| `GET`  | `/scans` | List scans, with optional filters |
| `GET`  | `/scans/{id}` | Full detail, including all findings |
| `DELETE` | `/scans/{id}` | Delete a scan |
| `GET`  | `/cve/search?q=...` | RAG-powered semantic CVE search |
| `GET`  | `/cve/{cve_id}` | Look up one CVE |

Full schemas and try-it-out forms live at `/docs`.

---

## Project layout

```
app/
├── main.py                 FastAPI app + routes wiring
├── config.py               Pydantic settings, loaded from .env
├── database.py             SQLAlchemy engine + session
├── api/
│   ├── scans.py            /scans and /scans/pr
│   └── cve.py              /cve/search etc.
├── models/                 SQLAlchemy ORM (Scan, ScanFile, Vulnerability, CVERecord)
├── schemas/                Pydantic request/response models
├── services/
│   ├── scanner.py          Orchestrates persistence + graph execution
│   └── github.py           PR-fetching helper around PyGithub
├── agents/
│   ├── graph.py            LangGraph wiring
│   ├── state.py            Shared state between nodes
│   ├── static_analyzer.py  Rule-based detector (no LLM needed)
│   ├── vulnerability_detector.py   LLM agent
│   ├── cve_researcher.py   RAG lookup over CVE store
│   ├── severity_assessor.py        Calibrates final severity
│   ├── report_generator.py         LLM writes the summary
│   └── llm.py              Thin OpenAI wrapper with graceful fallback
├── rag/
│   ├── embeddings.py       OpenAI embeddings (with hash-based fallback)
│   ├── vectorstore.py      pgvector cosine search
│   └── cve_loader.py       CLI: `python -m app.rag.cve_loader --seed`
└── utils/logger.py
alembic/                    Database migrations
data/cve_seed.json          ~20 well-known CVEs to bootstrap the RAG store
deploy/aws/                 ECS task definition + step-by-step deploy guide
examples/                   Vulnerable demo file + ready-to-POST request
scripts/run_local.py        Bootstrap script for `make local` (SQLite, no Docker)
scripts/scan_local.py       CLI: scan a local folder against a running API
tests/                      Pytest suite
```

---

## Design notes

A few things worth calling out, since they're the parts I'd ask about in a
design review.

**The scanner has to work without an API key.** I want anyone cloning the
repo to be able to run the tests, so the LLM agents detect when
`OPENAI_API_KEY` is unset and silently skip. The static-analysis agent
still produces useful findings on its own. Same trick for embeddings —
there's a hash-based fallback so the pgvector pipeline still exercises in
local tests.

**Agents share a typed state, not free-form text.** Every node takes and
returns the same `AgentState` TypedDict. This keeps the graph easy to
reason about and means I can add a node (e.g. a license-compliance agent)
without touching the others.

**Static + LLM, not static *or* LLM.** The static analyzer is fast and has
near-zero false negatives on a fixed list of patterns. The LLM agent
catches the things you can only spot by reading the code. Running both
and deduping in the merger gives the best of both — fast feedback on the
obvious bugs, and thoughtful findings on the rest.

**Severity is calibrated, not just reported.** The severity-assessor
node looks at the related CVEs (their CVSS scores), how many findings
clustered in the same file, and the agent's own confidence, and adjusts
severities accordingly. This is what makes the final summary feel
trustworthy instead of noisy.

**Risk score is a single number on the scan.** Useful for thresholds in CI.
It's a confidence-weighted sum of severity scores, capped at 100.

---

## Running the tests

```bash
make test          # or: pytest -q
```

Tests run against in-memory SQLite + a stubbed CVE researcher, so they
need neither Postgres nor an OpenAI key.

---

## Deploying to AWS

There's a step-by-step guide in [`deploy/aws/README.md`](deploy/aws/README.md).
The short version:

1. Push the image to ECR.
2. Stand up RDS PostgreSQL and `CREATE EXTENSION vector;`.
3. Drop secrets (`DATABASE_URL`, `OPENAI_API_KEY`, `GITHUB_TOKEN`) into
   AWS Secrets Manager.
4. Register `deploy/aws/task-definition.json` (after replacing the
   `ACCOUNT_ID` placeholders).
5. Create an ECS Fargate service behind an ALB pointing at port 8000.

The container has a `HEALTHCHECK`, the app exposes `/health`, and logs
go to CloudWatch — so the usual ECS niceties (rolling deploys, auto
healing) just work.

---

## Limitations + things I'd add next

- **More languages.** The static rules cover Python, JavaScript/TypeScript
  pretty well, plus a few cross-cutting patterns (secrets, TLS verify=False,
  weak crypto). Go, Java, Ruby would be a good next pass.
- **Authenticated GitHub webhooks.** Right now PR scans are pull-based. A
  webhook receiver would let the scanner kick off automatically on every
  PR open/sync.
- **Better CVE corpus.** The seed file has ~20 famous CVEs to demo the
  RAG pipeline. In production you'd ingest the full NVD JSON feeds nightly.
- **Caching.** Identical files (by content hash) shouldn't re-run through
  the LLM. Easy win once usage justifies it.

---

## License

MIT — do what you want, but don't blame me when it tells you your code
is fine and it isn't.
