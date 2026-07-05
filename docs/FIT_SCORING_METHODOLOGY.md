# Student-major fit scoring methodology

**Current fit methodology version:** 1.3

## 1. Purpose and boundaries

The fit score estimates how well one college and one intended major align with a confirmed student profile. It is used to order recommendations after the application has independently assigned the institution a Safety / Likely, Target, Reach, or Insufficient Data category.

The fit score is not:

- an admission probability;
- a guarantee of admission, affordability, or program entry;
- a published university or program ranking; or
- a comparison against an unpublished admitted-student résumé profile.

Admissions classification and recommendation ranking remain separate. Résumé evidence cannot change the admissions category.

## 2. Ranking unit

The application calculates a separate result for every:

```text
student x institution x intended major
```

The same institution can therefore receive different scores for different majors or students.

## 3. Overall fit formula

| Component | Default weight |
|---|---:|
| Academic fit | 30% |
| Major fit | 25% |
| Student preferences | 15% |
| Outcomes | 20% |
| Holistic alignment | 10% |

The overall score is the weighted mean of the components that have usable evidence:

```text
overall fit = sum(component score x component weight)
              ---------------------------------------
                    sum(available weights)
```

Each component is scored from 0 to 100. The final result is rounded to one decimal place.

### Missing evidence

A missing component is excluded rather than silently scored as zero. Its weight is redistributed proportionally across the available components because the denominator contains only available weights.

This makes confidence essential: two identical numeric scores may not have equal evidentiary support. Every result includes component values, missing inputs, and a confidence label.

## 4. Academic fit - 30%

Academic fit uses only compatible comparisons produced by the admissions classifier:

| Student position | Score |
|---|---:|
| Above the published range | 100 |
| Within the published range | 70 |
| Below the published range | 25 |

When multiple compatible signals exist, their scores are averaged. Supported signals currently include:

- unweighted GPA against a compatible unweighted GPA range;
- weighted GPA against a compatible weighted GPA range;
- SAT total against the institution's published SAT range; and
- ACT composite against the institution's published ACT range.

Weighted and unweighted GPAs are never compared as though they were equivalent. A test score the student does not plan to submit is excluded. If no compatible academic comparison exists, this component is missing.

## 5. Major fit - 25%

Major matching uses reviewed Classification of Instructional Programs (CIP) mappings.

### Exact six-digit program match

Six-digit IPEDS completion data confirms exact bachelor-program availability. The score is:

```text
70
+ min(15, bachelor's completions / 5)
+ up to 15 points from four-digit field earnings
```

The result is capped at 100. The earnings bonus normalizes one-year median field earnings from $20,000 to $100,000:

```text
earnings bonus = clamp((earnings - 20,000) / 80,000, 0, 1) x 15
```

### Four-digit field fallback

When a four-digit College Scorecard field is available but exact six-digit availability is unavailable:

```text
55 + up to 25 normalized field-earnings points
```

The result is capped at 80 and cannot prove that the exact intended major is offered.

### Two-digit family fallback

When only a broad two-digit CIP family is available:

```text
35 + min(20, reported family share x 100)
```

The result is capped at 55, program availability remains unknown, and fit confidence is Low.

If detailed six-digit institutional records exist and the mapped exact program is absent, major fit is zero and the program is marked not offered.

## 6. Student preferences - 15%

### Geography

| Condition | Score |
|---|---:|
| State is explicitly excluded | 0 |
| State is preferred | 100 |
| Preferred states exist but this state is outside them | 35 |
| No state preference was supplied | 60 |

### Budget

When a comparable budget and institutional cost are both available:

| Condition | Score |
|---|---:|
| Published comparable cost is within budget | 100 |
| Published comparable cost exceeds budget | 20 |

Geography and budget signals are averaged when both are available. Missing optional budget information does not block analysis.

## 7. Outcomes - 20%

The outcomes component averages the available institution-level measures:

- graduation rate multiplied by 100;
- retention rate multiplied by 100; and
- ten-year median earnings normalized from $20,000 to $100,000:

```text
earnings score = clamp((earnings - 20,000) / 800, 0, 100)
```

If none of these measures is available, the outcomes component is missing.

## 8. Holistic alignment - 10%

Holistic alignment uses only confirmed, structured themes from the profile's holistic section and activity records. Free-form notes do not automatically become scored evidence.

Résumé parsing must produce structured activities and themes with `review_status: "needs_review"`. The profile assessment displays a review warning, and ranking ignores that evidence until the user reviews it and changes the status to `confirmed`. This prevents extracted or free-form résumé content from silently affecting a score.

- If at least one structured theme aligns with the mapped CIP family:

  ```text
  min(100, 20 + major fit x 0.8)
  ```

- If structured themes exist but none align, the score is 35.
- If the mapped program is confirmed absent, the score is zero.
- If structured themes or usable program evidence are missing, the component is missing.

Holistic alignment describes program and opportunity alignment. It does not estimate how an admissions office will value an activity.

## 9. Fit confidence

Initial confidence is based on the share of component weight supported by evidence:

| Available weight | Confidence |
|---|---|
| At least 80% | High |
| At least 50% but below 80% | Medium |
| Below 50% | Low |

Program-data limitations can cap confidence:

- missing or two-digit-only program evidence caps confidence at Low;
- four-digit-only program evidence caps confidence at Medium; and
- exact six-digit availability without four-digit outcomes caps otherwise High confidence at Medium.

## 10. Program-strength score

Program strength is intentionally separate from personalized fit. It excludes academic compatibility, geography, budget, and résumé evidence.

| Component | Weight |
|---|---:|
| Major fit | 60% |
| Outcomes | 40% |

```text
program strength = major fit x 60% + outcomes x 40%
```

If only one component is available, its weight is redistributed and program-strength confidence is Medium. When both are available, confidence is High.

This is an internal evidence-based measure, not a commercial or editorial prestige ranking.

## 11. National ranks

National ranks are assigned only when exact six-digit bachelor-program availability is confirmed.

### National student-major fit rank

Exact programs are ordered by:

1. fit confidence;
2. overall fit score; and
3. stable institution identifier.

### National program-strength rank

Exact programs are ordered by:

1. program-strength confidence;
2. program-strength score; and
3. stable institution identifier.

Every ordinal is accompanied by its comparison population, for example `25 of 600`.

## 12. Main recommendations and addendum

The current qualified-pool rules are:

- overall student-major fit must be at least 80/100;
- exact six-digit program availability must be confirmed; and
- student-supplied colleges are retained separately regardless of these recommendation gates.

Within every intended-major and admissions-category group, qualified colleges are ordered by national program-strength rank before student fit. Up to the requested category cap, normally ten, appear in the main recommendations. Remaining qualified colleges appear in the JSON, PDF, and Excel addendum.

Categories are never padded with colleges that fail the qualification rules.

## 13. Reproducibility and interpretation

The methodology version, source dataset version, component scores, missing inputs, confidence, CIP codes, and explanations are included in the canonical report. The same confirmed profile, dataset, and methodology version must produce the same ordering.

Users should interpret the output as a planning aid. They should verify current admissions requirements, costs, deadlines, program availability, and program-specific restrictions with each institution.
