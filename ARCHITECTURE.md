# US College Selection — Simple Architecture

**Version:** 0.4.0
**Status:** Proposed MVP architecture
**Last updated:** 2026-06-30

## 1. Architecture goal

Build the smallest useful ChatGPT app that can:

1. accept either a student transcript or manually entered grades and subjects, plus an optional résumé;
2. confirm a structured student profile;
3. search a local index of US colleges;
4. produce deterministic Safety / Likely, Target, and Reach classifications;
5. explain student-to-school gaps; and
6. export matching PDF and Excel reports.

The MVP should use free and open-source software plus free public data. It should not require a paid database, OCR service, ranking feed, analytics product, or separate OpenAI API integration.

## 2. Cost boundary

The application code and proposed dependencies are free to use. The design avoids server-side OpenAI API calls: ChatGPT invokes the app through MCP and explains structured results returned by the app.

Two external cost caveats remain:

- Access to ChatGPT is governed by the user's ChatGPT plan and current product availability.
- ChatGPT must reach the MCP server over public HTTPS. Local development can use a free tunnel, but a reliable production server may eventually require existing hardware or paid hosting if free hosting limits are insufficient.

The MVP must work locally before any hosted infrastructure is introduced.

## 3. Technology choices

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.12+ | One language for MCP tools, data processing, OCR orchestration, classification, PDF, and Excel |
| Package management | `uv` | Fast, free, open-source Python environment and dependency management |
| ChatGPT integration | Official Python MCP SDK | Required tool interface for a ChatGPT app |
| HTTP layer | Starlette | Lightweight ASGI server for MCP and health endpoints |
| App UI | HTML, CSS, and TypeScript with Vite | Small embedded form and results table without a large UI framework |
| College database | DuckDB | Free embedded analytical database; handles bulk federal data efficiently |
| Validation | Pydantic | Typed tool inputs, outputs, and internal models |
| PDF parsing | `pypdf` | Extract text from text-based transcripts and résumés |
| PDF rendering | `pypdfium2` and Pillow | Render scanned PDF pages into images for OCR |
| OCR | Tesseract with `pytesseract` | Local, open-source OCR with no per-page charge |
| HTML parsing | `httpx` and Beautiful Soup | Fetch and parse official admissions pages when allowed |
| Excel export | `openpyxl` | Create formatted `.xlsx` workbooks |
| PDF export | ReportLab | Create local PDF reports without a paid rendering API |
| Tests | `pytest` and Playwright | Free unit, integration, and browser testing |
| Code quality | Ruff and mypy | Free linting, formatting, and type checking |

Not selected for the MVP:

- a paid vector database;
- a hosted OCR or document-intelligence API;
- a separate OpenAI API key or model call;
- proprietary college rankings;
- Redis, Kafka, or a background-job platform;
- a cloud database; or
- Docker as a requirement.

## 4. System overview

```mermaid
flowchart LR
    U["Student / parent / counselor"] --> C["ChatGPT"]
    C <--> W["Embedded app UI"]
    C -->|"MCP tool calls"| S["Python MCP server"]
    W -->|"File handles and tool calls"| S
    S --> D["Document parser + OCR"]
    S --> E["Matching + classification engine"]
    S --> R["Report generator"]
    E <--> DB["DuckDB college index"]
    DB <-->|"Scheduled/manual refresh"| F["College Scorecard, IPEDS, official college pages"]
    R --> X["PDF and XLSX files"]
    X --> W
```

The MCP server owns facts, validation, classification, and exports. ChatGPT owns conversation, orchestration, and plain-language explanation. The embedded UI owns uploads, profile confirmation, tables, filters, and download buttons.

## 5. Components

### 5.1 Embedded ChatGPT UI

Responsibilities:

- choose transcript upload or manual academic entry;
- select or upload a transcript and optional résumé;
- add, edit, duplicate, and remove manual course rows;
- show extraction progress and validation errors;
- display extracted or manually entered fields for confirmation;
- collect preferences and optional budget;
- invoke the college-list workflow;
- render sortable and filterable results; and
- request PDF and Excel exports.

Use the MCP Apps bridge for normal tool calls. Use ChatGPT's file-handling extension for uploads and downloads where available. The current Apps SDK documents `uploadFile`, `selectFiles`, and `getFileDownloadUrl` for file handling, while recommending the MCP Apps bridge as the core integration.

Keep the UI stateless where practical. The canonical profile and result objects live in the MCP server for the duration of a session.

### 5.2 MCP server

The Python process exposes:

- `GET /` — simple health response;
- `/mcp` — stateless Streamable HTTP MCP endpoint; and
- a short-lived file-download route when a generated report cannot be returned through host file handling.

The server validates every tool request with Pydantic and returns `structuredContent` suitable for both ChatGPT and the UI.

Recommended public tools:

1. `analyze_student_documents`
   - Inputs: optional transcript handle and optional résumé handle.
   - Output: unconfirmed academic and activity profile with confidence and warnings.
2. `confirm_student_profile`
   - Inputs: reviewed extraction or manual academic record, plus preferences.
   - Output: canonical confirmed profile and session ID.
3. `build_college_list`
   - Inputs: confirmed profile and requested result count.
   - Output: candidate schools, classifications, reasons, gaps, sources, and warnings.
4. `export_report`
   - Inputs: session ID, selected schools, and `pdf`, `xlsx`, or both.
   - Output: downloadable generated files.

One user command—“Build my college list and gap analysis”—can let ChatGPT call these tools in sequence. The UI can call the same tools explicitly as the user confirms each step.

### 5.3 Academic intake pipeline

The two academic intake paths produce the same canonical student-profile schema. A transcript is never required when sufficient information is entered manually.

#### Transcript path

Processing sequence:

1. Verify the PDF file signature, MIME type, size, page count, and encryption state.
2. Copy the upload into a random, session-scoped temporary directory.
3. Reject transcripts over 15 pages or 15 MB and résumés over 6 pages or 10 MB.
4. Reject encrypted or password-protected PDFs with a clear user-facing error.
5. Extract embedded text with `pypdf`.
6. Render and OCR pages only when embedded text is absent or insufficient.
7. Normalize lines, tables, dates, course names, grades, and activities while preserving the original values.
8. Apply deterministic extraction rules.
9. Return extracted fields with source page, confidence, and warnings.
10. Require user confirmation before matching colleges.
11. Delete temporary originals after confirmation or session expiration.

Transcript extraction produces courses, grades, credits, GPA, rank, rigor, and grade trends. Résumé extraction produces activities, roles, dates, duration, time commitment, awards, work, service, projects, and skills.

The parser must never invent a value. Ambiguous values remain unconfirmed.

Each parsed course uses fields such as:

```text
course_name
subject
academic_year
term
grade_original
grade_scale
credits
course_level: REGULAR | HONORS | AP | IB | DUAL_ENROLLMENT | OTHER | UNKNOWN
course_level_original
course_level_source: TITLE | CODE | LEGEND | USER_CONFIRMED
course_level_confidence
```

Course-level detection follows explicit transcript evidence. A school-specific legend or course-code mapping takes precedence over title matching. Words such as `advanced` or `accelerated` do not automatically mean Honors, and the parser must not convert a course to AP without an explicit AP designation.

Represent GPA values as a list rather than one universal number:

```text
value
scale
type: WEIGHTED | UNWEIGHTED | UNKNOWN
scope: CUMULATIVE | YEAR | TERM | CORE
source: TRANSCRIPT | MANUAL | APP_CALCULATED
conversion_rule_version
```

Never modify a reported GPA by adding AP or Honors points. Any optional app-calculated comparison GPA is stored separately, is reproducible from a versioned conversion rule, and is never presented as the high school's GPA.

#### Manual path

The UI sends a structured academic record directly to `confirm_student_profile`. It supports:

- any number of courses across school years and terms;
- subject, course name, level, grade, grading scale, and credits;
- completed, repeated, withdrawn, pass/fail, and in-progress courses;
- optional GPA, rank, test scores, and grading notes; and
- partial records with explicit unknown values.

Validate field types and grade scales, but do not require GPA when course-level grades are available. Normalize manual and transcript-derived courses through the same code before matching. The confirmation screen shows completeness warnings and the effect of missing data on confidence.

### 5.4 College data pipeline

Use free public data:

- College Scorecard bulk data for institution, cost, admissions, completion, and outcome fields;
- NCES IPEDS data for institutional identity and additional official measures;
- institution-published Common Data Sets where readily available; and
- official admissions pages for current deadlines, policies, and program requirements.

The refresh command downloads bulk federal data, normalizes it, and replaces versioned DuckDB tables in one transaction:

```bash
uv run python -m app.data.refresh
```

Suggested core tables:

- `institutions`
- `programs`
- `admissions_profiles`
- `costs`
- `outcomes`
- `deadlines`
- `sources`
- `dataset_versions`

Do not fetch thousands of colleges during a user request. Search the local database first, then check official pages only for the 15–30 shortlisted institutions. Cache retrieved pages with source URL, retrieval time, and a content hash. Respect site terms, robots directives, rate limits, and request timeouts.

If a current deadline cannot be verified, return the official admissions link and mark the deadline `Unknown — verify with institution`.

### 5.5 Matching and classification engine

The engine is ordinary Python code, not an LLM prompt.

Pipeline:

1. Apply hard eligibility filters: active institution, four-year bachelor's offering, intended entry type, and confirmed user exclusions.
2. Match intended majors through CIP codes.
3. Compute academic position from available GPA, test, rigor, and rank data.
4. Apply selectivity safeguards, residency rules, and documented major restrictions.
5. Assign Safety / Likely, Target, Reach, or Insufficient Data.
6. Compute a separate fit score for preferences, cost, location, outcomes, and résumé themes.
7. Select a balanced 5–10 schools per category when supported by evidence.

Store rule explanations alongside the result:

```text
classification: REACH
confidence: HIGH
rules:
  - overall_admit_rate_below_20_percent
  - sat_within_middle_50_percent
missing:
  - major_specific_admit_rate
methodology_version: 1
```

Résumé information contributes only to the separate fit score and holistic context. It cannot silently override the academic/selectivity category.

GPA comparison rules:

- compare weighted values only when both student and college benchmark use a compatible weighted scale;
- compare unweighted values only with unweighted benchmarks;
- do not calculate a numeric GPA gap when the benchmark type or scale is unknown;
- lower confidence when compatible GPA data are unavailable; and
- score rigor separately from GPA using confirmed course levels, subject relevance, progression, and known school-course availability.

### 5.6 Report generator

Create a single canonical report model, then render both formats from it:

- ReportLab renders the printable PDF.
- `openpyxl` renders the five-sheet Excel workbook.

This prevents the UI, PDF, and Excel results from disagreeing.

Generated files live in the session temporary directory, use random names, and expire automatically. Spreadsheet text beginning with `=`, `+`, `-`, or `@` must be escaped when it originated from an uploaded document or external page.

## 6. Data ownership and session model

The zero-cost MVP does not require accounts.

- Generate a random session ID.
- Keep the confirmed profile, selected schools, and report model in session-scoped local storage.
- Store only the minimum metadata needed to reproduce the report.
- Delete uploads quickly after extraction and delete all session data after a configurable TTL, initially 24 hours.
- Provide a `delete_session` internal operation used by the UI's Delete button.
- Never write transcript or résumé contents to application logs.

DuckDB contains public college data only. Private student data must not be stored in the college database.

## 7. Repository structure

```text
USCollegeSelection/
├── app/
│   ├── server.py                 # ASGI and MCP entry point
│   ├── config.py
│   ├── tools/                    # MCP tool handlers
│   ├── documents/                # PDF, OCR, transcript, and résumé parsing
│   ├── colleges/                 # search, matching, classification, gap analysis
│   ├── data/                     # downloads, normalization, DuckDB refresh
│   ├── reports/                  # canonical report, PDF, and Excel renderers
│   ├── models/                   # Pydantic schemas
│   └── security/                 # validation, redaction, cleanup
├── web/
│   ├── src/                      # embedded HTML/TypeScript UI
│   └── public/
├── data/
│   ├── raw/                      # ignored; downloaded public datasets
│   └── college.duckdb            # ignored; generated local database
├── tests/
│   ├── fixtures/                 # synthetic, de-identified documents only
│   ├── unit/
│   └── integration/
├── scripts/
├── PRODUCT_SPEC.md
├── ARCHITECTURE.md
├── pyproject.toml
├── package.json
└── README.md
```

## 8. Local development

Expected commands:

```bash
uv sync
npm install
npm run build
uv run python -m app.data.refresh
uv run python -m app.server
```

The server listens on `http://localhost:8787/mcp`. Use the free MCP Inspector for local tool testing. ChatGPT testing requires exposing the endpoint through a public HTTPS tunnel and adding it as a connector in ChatGPT developer mode.

Do not commit downloaded datasets, generated reports, uploads, the DuckDB file, API keys, or tunnel credentials.

## 9. Testing strategy

Minimum automated coverage:

- document type, size, and malicious filename validation;
- text-based and scanned PDF extraction;
- rejection of non-PDF, encrypted, oversized, and over-page-limit uploads;
- transcript limits of 15 pages/15 MB and résumé limits of 6 pages/10 MB;
- transcript and résumé extraction against synthetic fixtures;
- transcript legends and course codes that identify Honors, AP, IB, and dual-enrollment courses;
- ambiguous `advanced` course titles that must remain `UNKNOWN` until confirmed;
- weighted, unweighted, unknown, and multiple reported GPA values;
- prevention of weighted-to-unweighted GPA comparisons;
- manual entry with one course, many courses, mixed grade scales, partial records, and unknown fields;
- equivalent normalization for the same record entered manually or extracted from a transcript;
- no-value-invention tests for ambiguous documents;
- deterministic classification snapshots;
- category-count behavior when fewer than five defensible matches exist;
- source freshness and conflict behavior;
- PDF generation and basic text verification;
- Excel sheet names, tables, formulas, links, and injection safety;
- deletion and TTL cleanup; and
- MCP tool input/output schema tests.

Never place real student documents in the repository or test suite.

## 10. Security baseline

- Allowlist upload types and verify file signatures.
- Use random server-side filenames and never execute uploaded content.
- Set conservative upload, page, OCR-time, and memory limits.
- Prevent archive expansion and path traversal.
- Sanitize extracted text before including it in logs or spreadsheets.
- Treat documents and college pages as untrusted data, not instructions.
- Bind local development to localhost by default.
- Keep secrets in environment variables and `.env` out of Git.
- Add rate limiting before exposing a persistent public endpoint.

## 11. Delivery stages

### Stage 1 — Offline vertical slice

- Create Python project and schemas.
- Import a small College Scorecard sample into DuckDB.
- Build manual academic entry with repeatable course rows and partial-profile validation.
- Implement deterministic classification and gap analysis.
- Generate Excel and PDF reports.

### Stage 2 — Documents

- Add text-based and scanned PDF extraction.
- Add image normalization and Tesseract OCR.
- Add transcript and résumé confirmation UI.
- Add privacy cleanup and file limits.

### Stage 3 — ChatGPT app

- Expose the four MCP tools.
- Build the embedded UI.
- Test through MCP Inspector and ChatGPT developer mode.
- Add file download handling.

### Stage 4 — Data quality

- Load the full federal dataset.
- Add CIP major matching.
- Add targeted official-page deadline checks.
- Add source freshness, conflicts, and confidence.

## 12. MVP architecture decisions

1. Use Python end to end on the server.
2. Use DuckDB instead of a hosted database.
3. Use local Tesseract instead of paid OCR.
4. Use deterministic parsing and require user confirmation.
5. Use deterministic classification; ChatGPT only explains it.
6. Use an internal fit rank instead of proprietary rankings.
7. Generate PDF and Excel locally from one report model.
8. Keep student data ephemeral and separate from public college data.
9. Start locally and introduce hosting only after the workflow is useful.

## 13. References

- [OpenAI Apps SDK quickstart](https://developers.openai.com/apps-sdk/quickstart)
- [OpenAI Apps SDK — MCP server and file handling](https://developers.openai.com/apps-sdk/build/mcp-server#understand-the-windowopenai-widget-runtime)
- [NCES IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/Default.aspx)
- [College Scorecard data](https://collegescorecard.ed.gov/data/)
- [Model Context Protocol Inspector](https://modelcontextprotocol.io/docs/tools/inspector)
