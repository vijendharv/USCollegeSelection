# US College Selection — Product Specification

**Version:** 0.2.0
**Status:** Initial draft  
**Last updated:** 2026-06-29

## 1. Product summary

US College Selection is a ChatGPT app that turns a student's academic record, résumé, and preferences into a researched, explainable college shortlist. A student, parent, or counselor can upload a transcript and résumé or enter a profile manually, run one command, and receive:

- 5–10 defensible **Safety / Likely**, **Target**, and **Reach** schools per category when enough matches exist;
- a comparison table with admissions, academic, cost, outcome, ranking, and deadline information;
- a printable school-by-school gap analysis; and
- downloadable PDF and Excel reports.

The product is decision support, not an admissions predictor. It must never describe admission as guaranteed.

## 2. Goals

1. Reduce the work required to discover and compare US colleges.
2. Make every recommendation and classification understandable and traceable to source data.
3. Identify academic, financial, and application gaps the student can act on.
4. Keep time-sensitive information, especially deadlines and testing policies, visibly sourced and dated.
5. Produce artifacts that families and counselors can review offline.

## 3. Non-goals for the initial release

- Guaranteeing admission or presenting a precise probability of admission.
- Writing application essays or submitting applications.
- Replacing a college's net-price calculator or a financial-aid award.
- Supporting transfer, international, graduate, conservatory, portfolio, or recruited-athlete admissions.
- Republishing proprietary rankings without a license.
- Making unsupported major-level admissions claims when a college does not publish major-level data.

## 4. Target users

- US high-school students applying to four-year undergraduate programs.
- Parents or guardians helping a student build an application list.
- School and independent college counselors working with multiple students.

## 5. Primary user journey

1. The user uploads an unofficial transcript and, optionally, a student résumé, or chooses manual entry.
2. The app extracts academic and activity information and asks the user to confirm or correct it.
3. The user supplies preferences: residency, intended entry term, majors, geography, existing schools, and optional budget.
4. The user runs a single action: **Build my college list and gap analysis**.
5. The app searches the college universe, verifies matches, classifies candidates, and displays an interactive shortlist.
6. The user pins, removes, replaces, sorts, and filters schools.
7. The user downloads a printable PDF and a formatted Excel workbook.

## 6. Student profile

### 6.1 Required fields

- GPA and GPA scale.
- Whether the GPA is weighted, unweighted, or unknown.
- State of residence.
- Intended entry year and term.
- At least one intended major or broad field of study.

### 6.2 Optional fields

- SAT and ACT scores, including section scores and test dates.
- Whether the student plans to submit test scores.
- Class rank, class size, or class percentile.
- AP, IB, honors, dual-enrollment, and other advanced coursework.
- Annual family budget.
- Whether budget means maximum net price, maximum out-of-pocket cost, or maximum published cost.
- Household income band for estimated net-price comparisons.
- Geographic preferences and exclusions.
- Campus setting, enrollment size, public/private status, and religious affiliation.
- HBCU, women's college, or other institution-type preferences.
- Existing college list.
- Early Decision or Early Action preferences.
- Extracurricular strength and relevant special circumstances.
- A student résumé containing activities, leadership, employment, service, projects, awards, and skills.

Budget and test scores are optional. When budget is absent, cost must remain visible but must not filter or penalize schools. When test scores are absent or withheld, the app must use other supported data and lower confidence where appropriate.

## 7. Transcript upload and extraction

### 7.1 Accepted inputs

- PDF, including multi-page PDFs.
- PNG, JPEG, and HEIC images.
- DOCX.
- Maximum upload size and page count must be configurable and stated before upload.

### 7.2 Extracted information

The app should extract, when present:

- cumulative GPA, GPA scale, and weighted/unweighted status;
- course names, academic years, terms, grades, credits, and subject areas;
- AP, IB, honors, dual-enrollment, and other advanced-course designations;
- class rank and class size;
- school grading notes; and
- grade trends and preparation in subjects related to the intended major.

### 7.3 Verification requirements

- Show a review screen before extracted data can be used.
- Let the user edit every extracted field.
- Associate extraction confidence with ambiguous fields.
- Display the transcript page or region supporting a value when practical.
- Flag unreadable, contradictory, or missing fields rather than guessing.
- Fall back to manual entry when extraction fails.
- Explain that colleges may recalculate GPA differently.

### 7.4 Privacy requirements

- Do not retain student ID, address, birth date, counselor information, or other identifiers that are unnecessary for analysis.
- Redact detected unnecessary identifiers from stored derived data.
- Encrypt uploads in transit and at rest.
- Permit immediate deletion of the original file, profile, and derived data.
- Define and publish a short default retention period.
- Do not use transcript contents for model training or unrelated analytics.

## 8. Résumé upload and extraction

### 8.1 Accepted inputs

- PDF and DOCX.
- PNG, JPEG, and HEIC images for scanned résumés.
- Plain text pasted into the profile form.
- Multi-page files within configurable upload limits.

### 8.2 Extracted information

The app should extract, when present:

- extracurricular activities and participation dates;
- leadership roles and scope of responsibility;
- volunteer and community-service work;
- paid employment, internships, and family responsibilities;
- awards, honors, publications, certifications, and competitions;
- research, technical, creative, entrepreneurial, and independent projects;
- athletics, arts, clubs, and other sustained interests;
- skills, languages, and tools; and
- time commitment, duration, progression, and measurable outcomes.

The app may organize activities into themes related to intended majors and student interests, but it must preserve the student's original facts and wording for verification.

### 8.3 Verification and interpretation

- Show all extracted activities on a review screen before using them.
- Let the user correct titles, dates, time commitments, roles, and descriptions.
- Detect likely duplicates without silently merging them.
- Flag vague, contradictory, or implausible information for user review rather than rejecting it automatically.
- Never invent impact metrics, hours, awards, selectivity, or leadership scope.
- Treat résumé formatting quality as irrelevant to admissions classification.
- Allow users without a résumé to enter activities manually or skip this section.

### 8.4 Use in recommendations

Confirmed résumé information may be used to:

- identify alignment with intended majors and distinctive campus programs;
- surface relevant honors programs, research opportunities, clubs, and experiential learning;
- describe sustained interests, leadership, initiative, service, work, and responsibilities;
- identify gaps or opportunities in the holistic profile; and
- personalize application-strategy suggestions.

Résumé content must not be converted into a fabricated numerical admissions advantage. Because colleges rarely publish comparable extracurricular benchmarks, the app must keep the academic/selectivity classification separate from a **holistic context** assessment. Résumé evidence may add context to a classification explanation but must not silently move a school from Reach to Target or from Target to Safety / Likely.

### 8.5 Privacy

- Apply the transcript privacy, retention, encryption, and deletion requirements to résumés.
- Ignore and redact unnecessary addresses, phone numbers, personal email addresses, references, and social-media identifiers.
- Do not contact organizations, employers, recommenders, or other people named in the résumé.
- Do not attempt to verify private résumé claims through web searches without explicit user consent.

## 9. College universe and matching

The initial college universe consists of accredited, US, bachelor’s-granting institutions that admit first-year undergraduates.

The system must:

- use IPEDS `UNITID` as the canonical institution identifier;
- map majors to Classification of Instructional Programs (CIP) codes;
- distinguish campuses and admissions units rather than merging similarly named institutions;
- exclude closed, non-degree, and ineligible institutions;
- evaluate every user-entered school, even if it violates a preference or filter;
- explain why a user-entered school is a poor match instead of silently removing it;
- return 5–10 schools in each category when defensible; and
- report that too few matches exist rather than padding a category with weak recommendations.

Hard filters and soft preferences must be visibly different. The app must ask for confirmation before treating an ambiguous preference as a hard exclusion.

## 10. Recommendation results

### 10.1 Default table columns

1. Institution.
2. Safety / Likely, Target, Reach, or Insufficient Data.
3. Classification confidence.
4. Overall fit rank.
5. City and state.
6. Intended-major availability.
7. Overall acceptance rate.
8. Published GPA and test-score profile.
9. Tuition, total cost of attendance, and net price.
10. Application deadlines.

### 10.2 Optional columns

- Graduation and retention rates.
- Enrollment and student-to-faculty ratio.
- In-state and out-of-state cost.
- Median post-college earnings.
- Application fee.
- Test policy.
- Early Action and Early Decision availability.
- Campus setting and distance from home.
- Data year, source, and last-verified date.

### 10.3 Interactions

Users must be able to:

- sort and filter results;
- pin, remove, and replace schools;
- compare selected schools side by side;
- see why a school matched;
- see why a school received its classification;
- open source and admissions pages; and
- regenerate recommendations without losing pinned schools.

## 11. Classification methodology

Classification must be produced by deterministic, versioned, testable application code. The language model may explain results but must not invent or silently override the classification.

### 11.1 Supported factors

- Overall acceptance rate.
- Student GPA relative to a published admitted-student distribution.
- SAT/ACT relative to published 25th, 50th, and 75th percentiles.
- Class rank and course rigor when comparable data exist.
- Residency advantage for public institutions when documented.
- Test policy and the student's test-submission choice.
- Major-specific selectivity when published by the institution.
- Direct or automatic admission criteria.
- Data completeness, age, and conflicts.

Race, ethnicity, gender, disability, religion, and other protected traits must not be used to estimate admission likelihood.

### 11.2 Category definitions

- **Safety / Likely:** The student is at or above the institution's typical academic profile, the overall admit rate is reasonably high, no known major restriction materially increases risk, and the supporting data are sufficiently complete.
- **Target:** The student is within the typical admitted-student profile without an overriding selectivity or major constraint.
- **Reach:** The student falls below an important published range, the institution is highly selective, or the intended program is materially more selective.
- **Insufficient Data:** Available information cannot support a responsible classification.

Highly selective institutions remain Reach even for students above their published academic ranges. A missing value must lower confidence; it must never be treated as favorable evidence.

### 11.3 Explainability

Every classification must expose:

- methodology version;
- rules that fired;
- student values and school benchmarks used;
- unavailable or excluded factors;
- source year and URL; and
- a plain-language explanation and confidence level.

## 12. Gap analysis

The app must generate a section for every recommended and user-entered school.

Each comparison row contains:

| Measure | Student | School benchmark | Gap | Status | Source |
|---|---:|---:|---:|---|---|
| GPA | 3.72 | 3.80 median | -0.08 | Slightly below | School CDS |
| SAT | 1380 | 1320–1470 | Within range | Competitive | School CDS |
| Course rigor | 6 AP | Not published | Unknown | Unverified | — |
| Annual budget | $35,000 | $31,500 estimated net | +$3,500 | Within budget | Scorecard |

The report must also include:

- academic strengths;
- résumé-derived themes, relevant experiences, and holistic context;
- material gaps and unknown factors;
- grade trajectory and core-subject preparation;
- intended-major preparation and missing recommended coursework;
- suggested actions and application-strategy notes;
- financial-fit warning where appropriate;
- source links, source years, and verification dates; and
- generation timestamp, methodology version, and disclaimer.

## 13. Cost and affordability

The product must distinguish among:

- published tuition;
- mandatory fees;
- housing and food;
- total cost of attendance;
- average net price;
- estimated student-specific net price; and
- in-state and out-of-state pricing.

A school must not be called affordable based only on tuition or average net price. Student-specific estimates must be labeled as estimates and should link to the institution's official net-price calculator where available.

## 14. Data sources and freshness

### 14.1 Source hierarchy

1. US Department of Education College Scorecard and NCES IPEDS for identity, admissions, cost, aid, completion, and outcomes.
2. Official institution admissions and financial-aid pages for current deadlines, testing policies, costs, and program requirements.
3. Institution-published Common Data Sets for admitted-student academic profiles.
4. A licensed ranking provider if third-party rankings are offered.

The MVP should use a transparent internal **fit rank** rather than scrape or republish proprietary rankings.

### 14.2 Freshness rules

- Store the source URL, data period, retrieval date, and last verification date for each field.
- Label federal annual data as “latest available,” not “live.”
- Refresh bulk federal data after official releases.
- Recheck deadlines and testing policies frequently during application season.
- Prefer a current official institution page for deadlines when sources conflict.
- Display conflicts and unresolved discrepancies.
- Never fabricate missing GPA, rank, deadline, cost, or major-selectivity data.

## 15. Reports and downloads

### 15.1 Printable PDF

The PDF must:

- include the confirmed profile, shortlist, and gap analysis;
- use readable page breaks, repeating table headers, and print-safe colors;
- avoid clipped columns and interactive-only content;
- include source links, generation date, and methodology version; and
- match the final on-screen results.

### 15.2 Excel workbook

The app must generate a formatted `.xlsx` workbook containing:

1. **College List** — all selected and user-entered schools, classification, confidence, fit rank, admissions, cost, outcomes, deadlines, and links.
2. **Gap Analysis** — student-versus-school measures, gaps, statuses, and sources.
3. **Student Profile** — confirmed manual inputs, transcript-derived academic summary, and résumé-derived activity summary.
4. **Application Tracker** — school, plan, deadline, status, fee, supplements, and notes.
5. **Sources & Methodology** — source URLs, data years, verification dates, classification rules, and methodology version.

Workbook requirements:

- native Excel tables with frozen headers, filters, and sensible column widths;
- color-coded categories that remain understandable without color;
- appropriate currency, percentage, score, and date formats;
- clickable admissions and source links;
- wrapped text without clipped content;
- formula-injection-safe exported values;
- `Unknown` or blank cells for unavailable data;
- generation timestamp and methodology version; and
- exact agreement with the on-screen and PDF results.

## 16. ChatGPT app and tool requirements

The app should use the OpenAI Apps SDK architecture:

- an MCP server exposing typed tools;
- a web component for transcript and résumé upload, profile confirmation, results, and exports; and
- structured tool results so the model, UI, PDF exporter, and Excel exporter use the same canonical data.

Recommended MCP tools:

- `create_student_profile`
- `parse_transcript`
- `parse_resume`
- `confirm_student_profile`
- `search_colleges`
- `classify_colleges`
- `compare_colleges`
- `generate_gap_analysis`
- `export_college_report`

The user-facing one-command action may orchestrate multiple tools internally. Long-running steps should report progress and partial failure without discarding successful results.

## 17. Nonfunctional requirements

### Performance and reliability

- Return a typical shortlist within 15 seconds using a pre-indexed college dataset.
- Avoid querying thousands of remote records during an interactive request.
- Produce identical classifications for the same profile, dataset, and methodology version.
- Retry transient source failures and clearly mark unavailable current data.
- Keep PDF and Excel generation independent of optional third-party services.

### Security and privacy

- Encrypt data in transit and at rest.
- Minimize personal-data collection.
- Separate user identity from transcript-derived academic data where practical.
- Provide deletion and export controls.
- Never expose one user's profile or report to another user.
- Log methodology and source versions without logging unnecessary transcript content.
- Establish age, parental-consent, and school-use policies before launch.

### Accessibility

- Target WCAG 2.2 AA.
- Support keyboard navigation and screen readers.
- Do not convey classifications through color alone.
- Provide accessible upload, validation, table, and download states.

### Observability

- Record source health, freshness, extraction confidence, classification version, export failures, and latency.
- Alert on stale deadline data and large source-to-source discrepancies.
- Keep an audit record sufficient to reproduce a generated report.

## 18. Acceptance criteria for the MVP

The MVP is complete when:

1. A user can upload a supported transcript and optional résumé or enter a profile manually.
2. The user can review and correct all extracted academic and activity data before analysis.
3. A profile can be submitted without a budget or test score.
4. The system searches the eligible US college universe and normally returns 15–30 recommendations.
5. The system does not force five schools into a category when evidence is insufficient.
6. User-entered schools are always evaluated and visibly distinguished from discovered schools.
7. Every classification includes reasons, confidence, methodology version, and source dates.
8. Missing and conflicting information is shown explicitly.
9. Intended-major availability is verified using supported program data.
10. Deadlines link to an official institutional source.
11. The gap analysis covers every selected and user-entered school.
12. PDF output prints without clipped tables or missing content.
13. Excel output contains all five required sheets and matches the UI and PDF.
14. Re-running against the same data and methodology produces the same classifications.
15. The product never describes admission or affordability as guaranteed.
16. Résumé evidence is shown as holistic context and cannot silently override the deterministic academic/selectivity classification.

## 19. Future enhancements

- Counselor workspaces and multi-student portfolio views.
- Saved profiles, version history, and application-status reminders.
- Scholarship and honors-college matching.
- International, transfer, and graduate admissions modes.
- Deeper major-level outcomes and program accreditation.
- Financial-aid award comparison.
- Licensed external rankings selectable by methodology.
- Direct admissions and automatic-admission eligibility.

## 20. Reference sources

- [OpenAI Apps SDK quickstart](https://developers.openai.com/apps-sdk/quickstart)
- [NCES IPEDS Data Center](https://nces.ed.gov/ipeds/datacenter/Default.aspx)
- [College Scorecard data](https://collegescorecard.ed.gov/data/)
