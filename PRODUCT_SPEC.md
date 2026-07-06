# US College Selection — Product Specification

**Version:** 0.7.0
**Status:** Initial draft  
**Last updated:** 2026-06-30

## 1. Product summary

US College Selection is a ChatGPT app that turns a student's academic record, résumé, and preferences into a researched, explainable college shortlist. A student, parent, or counselor can upload a transcript or manually enter the student's grades and subjects, optionally add a résumé, run one command, and receive:

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

1. The user chooses either **Upload transcript** or **Enter academics manually**.
2. For an upload, the app extracts academic information and asks the user to confirm or correct it. For manual entry, the user adds as many courses, subjects, grades, credits, and academic details as are available.
3. The user optionally uploads a student résumé or enters activities manually, then confirms the extracted or entered information.
4. The user supplies preferences: residency, intended entry term, majors, geography, existing schools, and optional budget.
5. The user runs a single action: **Build my college list and gap analysis**.
6. The app searches the college universe, verifies matches, classifies candidates, and displays an interactive shortlist.
7. The user pins, removes, replaces, sorts, and filters schools.
8. The user downloads a printable PDF and a formatted Excel workbook.

## 6. Student profile

### 6.1 Required fields

- Applicant stage: junior, senior, or gap year.
- Expected or actual high-school graduation year.
- State of residence.
- Intended entry year and term.
- At least one intended major or broad field of study.
- At least one academic input: GPA, class rank, test score, or one course with a subject and grade.

### 6.2 Optional fields

- Academic-record as-of date.
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

### 6.3 Manual academic entry

Manual entry is a first-class alternative to transcript upload, not merely an error fallback.

The user must be able to enter as much available information as needed, including:

- cumulative GPA, GPA scale, and weighted/unweighted/unknown status;
- grade level, school year, and term;
- subject area and course name;
- course level, including regular, honors, AP, IB, or dual enrollment;
- grade, grading scale, credits attempted, and credits earned;
- repeated, withdrawn, pass/fail, or in-progress status;
- class rank, class size, and percentile;
- SAT, ACT, AP, and IB scores; and
- free-form academic context or grading notes.

Users must be able to add, edit, duplicate, and remove course rows and save a partial profile. Unknown fields remain blank; the app must not require users to invent values. Before analysis, the app summarizes the entered record and warns when missing information materially lowers classification confidence.

### 6.4 Academic timing

The product evaluates only first-year undergraduate applicants using high-school records:

- A junior profile is evaluated through the latest completed or in-progress junior-year work and is not penalized for absent senior-year grades.
- A senior profile may include senior courses in progress. Those courses count as planned rigor but not as completed grade evidence.
- A gap-year profile uses the completed high-school transcript. Any course still marked in progress must be confirmed or corrected before relying on it.
- Grade level and the academic-record as-of date remain attached to the record so missing work is interpreted for the student's stage.
- College coursework after high-school graduation is not treated as a first-year high-school record.

## 7. Transcript upload and extraction

### 7.1 Accepted inputs

- PDF only, including text-based and scanned PDFs.
- Maximum 15 pages and 15 MB per transcript.
- Reject encrypted or password-protected PDFs with a clear error.
- State the accepted format and limits before upload.

### 7.2 Extracted information

The app should extract, when present:

- cumulative GPA, GPA scale, and weighted/unweighted status;
- course names, academic years, terms, grades, credits, and subject areas;
- AP, IB, honors, dual-enrollment, and other advanced-course designations exactly as reported by the school;
- class rank and class size;
- school grading notes; and
- grade trends and preparation in subjects related to the intended major.

### 7.3 Course rigor and GPA weighting

The transcript parser must treat course rigor and GPA as related but separate data.

- Detect Honors, AP, IB, dual-enrollment, and other advanced levels from course titles, course codes, transcript legends, or explicit school labels.
- Preserve the exact reported designation and record where it was found.
- Do not infer that a course is Honors or AP solely because its title contains words such as `advanced`, `accelerated`, or `college prep`.
- Flag uncertain course-level mappings for user confirmation.
- Preserve every school-reported GPA value, its scale, and whether it is weighted, unweighted, or unspecified.
- Never add AP or Honors points to a school-reported GPA.
- Do not assume all high schools use the same AP, Honors, IB, or dual-enrollment weight.
- If the app calculates an internal comparison GPA, label it clearly as app-calculated, publish the conversion rule, and retain the original GPA alongside it.
- Compare weighted GPA only with a compatible weighted school benchmark and unweighted GPA only with an unweighted benchmark.
- When the student's GPA type or the college benchmark type is unknown or incompatible, avoid a direct GPA-gap claim and reduce classification confidence.
- Evaluate course rigor separately using the number, level, subject relevance, progression, and—when known—the advanced courses available at the student's school.

### 7.4 Verification requirements

- Show a review screen before extracted data can be used.
- Let the user edit every extracted field.
- Associate extraction confidence with ambiguous fields.
- Display the transcript page or region supporting a value when practical.
- Flag unreadable, contradictory, or missing fields rather than guessing.
- Fall back to manual entry when extraction fails.
- Explain that colleges may recalculate GPA differently.

### 7.5 Privacy requirements

- Do not retain student ID, address, birth date, counselor information, or other identifiers that are unnecessary for analysis.
- Redact detected unnecessary identifiers from stored derived data.
- Encrypt uploads in transit and at rest.
- Permit immediate deletion of the original file, profile, and derived data.
- Define and publish a short default retention period.
- Do not use transcript contents for model training or unrelated analytics.

## 8. Résumé upload and extraction

### 8.1 Accepted inputs

- PDF only, including text-based and scanned PDFs.
- Maximum 6 pages and 10 MB per résumé.
- Reject encrypted or password-protected PDFs with a clear error.
- State the accepted format and limits before upload.

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
- Parse résumé evidence into structured activities and themes with a `needs_review` status; never leave uploaded résumé evidence only in free-form notes.
- Require user confirmation before changing résumé review status to `confirmed` and before résumé evidence can affect holistic alignment.
- Show an explicit profile warning when résumé-derived evidence is pending review; unconfirmed evidence must be exported for review but excluded from scoring.

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

The initial college universe consists of accredited, US, bachelor’s-granting institutions that admit first-year undergraduates. A school must report positive undergraduate enrollment; offering graduate degrees alone does not make it eligible.

The system must:

- use IPEDS `UNITID` as the canonical institution identifier;
- map majors to reviewed six-digit Classification of Instructional Programs (CIP) codes, roll them up to four-digit Scorecard outcome fields, and retain two-digit families only as a labeled fallback;
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
4. Recommendation rank within the admissions category after the fit floor and program-strength ordering.
5. Applied student-fit threshold for that major and admissions category.
6. Whether the category threshold was relaxed below its configured initial value.
7. City and state.
8. Intended-major availability.
9. Overall acceptance rate.
10. National student-major fit position and comparison population.
11. National program-strength rank, score, confidence, and comparison population.
12. Normalized top-percent positions for student-major fit and program strength.
13. Published GPA and test-score profile, clearly labeling unavailable benchmarks.
14. Tuition, total cost of attendance, and net price.
15. Application deadlines.

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
- Class rank and course rigor when comparable data exist, with AP/Honors rigor evaluated separately from GPA weighting.
- Residency advantage for public institutions when documented.
- Test policy and the student's test-submission choice.
- Major-specific selectivity when published by the institution.
- Direct or automatic admission criteria.
- Data completeness, age, and conflicts.

Race, ethnicity, gender, disability, religion, and other protected traits must not be used to estimate admission likelihood.

SAT and ACT are optional. Either test may support a classification when the student plans to submit it and a compatible institution range exists. If both are provided, use the stronger comparison and disclose that the weaker test was excluded; never require both tests.

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

The end-user result must include a visible **Missing data** section. It lists unavailable student inputs and school benchmarks that reduced confidence or prevented classification. Incompatible or intentionally excluded evidence, such as a weighted GPA against an unweighted benchmark or scores the student will not submit, must appear separately and must not be described as missing.

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

1. **Student-Supplied Colleges** — user-entered schools ranked separately by major and category, including unresolved names.
2. **College List** — all selected and user-entered schools, classification, confidence, fit rank, admissions, cost, outcomes, deadlines, and links.
3. **Major Rankings** — national program-strength and student-major fit positions, comparison populations, within-category recommendation rank, component scores, and confidence.
4. **Gap Analysis** — student-versus-school measures, gaps, statuses, and sources.
5. **Student Profile** — confirmed manual inputs, transcript-derived academic summary, and résumé-derived activity summary.
6. **Application Tracker** — school, plan, deadline, status, fee, supplements, and notes.
7. **Sources & Methodology** — source URLs, data years, verification dates, classification rules, and methodology version.
8. **Adaptive Thresholds** — the initial, floor, and applied threshold plus candidate counts for every major and admissions category.
9. **Additional Qualified Colleges** — exact-program matches meeting the category's applied threshold that were not among the strongest programs selected for its main table.

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

1. A user can choose transcript upload or manual academic entry; neither path requires the other.
2. The user can review and correct all extracted or manually entered academic and activity data before analysis.
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
13. Excel output contains all seven core sheets plus the qualified-college addendum when applicable and matches the UI and PDF.
14. Re-running against the same data and methodology produces the same classifications.
15. The product never describes admission or affordability as guaranteed.
16. Résumé evidence is shown as holistic context and cannot silently override the deterministic academic/selectivity classification.
17. Manual entry supports multiple courses and subjects, partial records, edits, and unknown values without fabricating missing data.
18. Transcript parsing preserves AP/Honors designations and reported GPA types, and the classifier never compares incompatible weighted and unweighted GPA values as if they were equivalent.
19. Transcript and résumé uploads accept PDF only; transcripts enforce 15 pages/15 MB and résumés enforce 6 pages/10 MB.

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
