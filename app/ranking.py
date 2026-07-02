"""Deterministic, explainable fit ranking kept separate from admissions classification."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models import (
    AcademicStanding,
    AdmissionCategory,
    BudgetType,
    ConsolidatedFitResult,
    FitComponent,
    FitConfidence,
    MajorFitResult,
    ProgramOffering,
    SchoolReport,
    StudentProfile,
)

FIT_METHODOLOGY_VERSION = "1.1"

_WEIGHTS = {
    "Academic fit": Decimal("30"),
    "Major fit": Decimal("25"),
    "Student preferences": Decimal("15"),
    "Outcomes": Decimal("20"),
    "Holistic alignment": Decimal("10"),
}


@dataclass(frozen=True)
class _MajorMapping:
    cip6: tuple[str, ...]
    cip4: tuple[str, ...]
    cip2: tuple[str, ...]


@dataclass(frozen=True)
class _MajorEvidence:
    component: FitComponent
    offered: bool | None
    match_granularity: int | None
    availability_cip_code: str | None
    ranking_cip_code: str | None


_MAJOR_CIP: dict[str, _MajorMapping] = {
    "biology": _MajorMapping(("260101",), ("2601",), ("26",)),
    "biochemistry": _MajorMapping(("260202",), ("2602",), ("26",)),
    "chemistry": _MajorMapping(("400501",), ("4005",), ("40",)),
    "molecular biology": _MajorMapping(("260204",), ("2602",), ("26",)),
    "neuroscience": _MajorMapping(("261501",), ("2615",), ("26",)),
    "physiology": _MajorMapping(("260901",), ("2609",), ("26",)),
    "genetics": _MajorMapping(("260801", "260806"), ("2608",), ("26",)),
    "microbiology": _MajorMapping(("260502",), ("2605",), ("26",)),
    "biomedical engineering": _MajorMapping(("140501",), ("1405",), ("14",)),
    "human physiology": _MajorMapping(("260901",), ("2609",), ("26",)),
    "pre medicine pre medical studies": _MajorMapping(("511102",), ("5111",), ("51",)),
    "computer science": _MajorMapping(("110701",), ("1107",), ("11",)),
    "mathematics": _MajorMapping(("270101",), ("2701",), ("27",)),
    "engineering": _MajorMapping((), ("1401",), ("14",)),
    "psychology": _MajorMapping(("420101",), ("4201",), ("42",)),
    "business": _MajorMapping((), ("5201",), ("52",)),
    "history": _MajorMapping(("540101",), ("5401",), ("54",)),
    "english": _MajorMapping(("230101",), ("2301",), ("23",)),
}

_CIP_THEMES: dict[str, set[str]] = {
    "11": {"computing", "computer", "technology", "research"},
    "14": {"engineering", "technology", "design", "research"},
    "26": {"biology", "biomedical", "healthcare", "medicine", "research", "science"},
    "27": {"mathematics", "analytics", "research"},
    "40": {"chemistry", "physics", "research", "science"},
    "42": {"psychology", "mental health", "research", "service"},
    "51": {"healthcare", "medicine", "public health", "service"},
}


def rank_major_fits(
    student: StudentProfile,
    schools: list[SchoolReport],
    offerings: list[ProgramOffering],
) -> tuple[list[MajorFitResult], list[ConsolidatedFitResult]]:
    """Rank every institution separately for each intended major and category."""
    by_unit: dict[int, list[ProgramOffering]] = defaultdict(list)
    for offering in offerings:
        by_unit[offering.unit_id].append(offering)

    unranked: list[MajorFitResult] = []
    for major in student.preferences.intended_majors:
        for school in schools:
            unranked.append(
                _score_fit(student, school, major, by_unit.get(school.institution.unit_id))
            )

    ranked: list[MajorFitResult] = []
    groups: dict[tuple[str, AdmissionCategory], list[MajorFitResult]] = defaultdict(list)
    for result in unranked:
        groups[(result.intended_major, result.category)].append(result)
    major_order = {major: index for index, major in enumerate(student.preferences.intended_majors)}
    category_order = {category: index for index, category in enumerate(AdmissionCategory)}
    for key in sorted(groups, key=lambda item: (major_order[item[0]], category_order[item[1]])):
        ordered = sorted(
            groups[key],
            key=lambda item: (
                item.program_offered is not True,
                item.program_offered is False,
                -item.overall_score,
                item.unit_id,
            ),
        )
        ranked.extend(
            item.model_copy(update={"rank": index}) for index, item in enumerate(ordered, 1)
        )
    return ranked, _consolidate(student, ranked)


def _score_fit(
    student: StudentProfile,
    school: SchoolReport,
    major: str,
    offerings: list[ProgramOffering] | None,
) -> MajorFitResult:
    major_evidence = _major_component(major, offerings)
    components = [
        _academic_component(school),
        major_evidence.component,
        _preference_component(student, school),
        _outcomes_component(school),
        _holistic_component(student, major, major_evidence),
    ]
    available = [component for component in components if component.score is not None]
    available_weight = sum((component.weight for component in available), Decimal(0))
    weighted = sum(
        (
            component.score * component.weight
            for component in available
            if component.score is not None
        ),
        Decimal(0),
    )
    score = _round(weighted / available_weight if available_weight else Decimal(0))
    coverage = available_weight / Decimal(100)
    confidence = (
        FitConfidence.HIGH
        if coverage >= Decimal("0.8")
        else FitConfidence.MEDIUM
        if coverage >= Decimal("0.5")
        else FitConfidence.LOW
    )
    if major_evidence.match_granularity in {None, 2}:
        confidence = FitConfidence.LOW
    elif (
        major_evidence.match_granularity == 4 or major_evidence.ranking_cip_code is None
    ) and confidence is FitConfidence.HIGH:
        confidence = FitConfidence.MEDIUM
    missing = [value for component in components for value in component.missing_inputs]
    top = max(available, key=lambda item: item.score or Decimal(0), default=None)
    explanation = (
        f"Fit score {score}/100 for {major}; strongest available component: "
        f"{top.name if top else 'none'}. Missing evidence is excluded and weights are "
        "redistributed."
    )
    return MajorFitResult(
        unit_id=school.institution.unit_id,
        institution_name=school.institution.name,
        intended_major=major,
        category=school.classification.category,
        rank=1,
        overall_score=score,
        confidence=confidence,
        methodology_version=FIT_METHODOLOGY_VERSION,
        cip_codes=_cip_codes(major),
        availability_cip_code=major_evidence.availability_cip_code,
        ranking_cip_code=major_evidence.ranking_cip_code,
        match_granularity=major_evidence.match_granularity,
        program_offered=major_evidence.offered,
        components=components,
        missing_inputs=list(dict.fromkeys(missing)),
        explanation=explanation,
    )


def _academic_component(school: SchoolReport) -> FitComponent:
    standings = [
        rule.standing for rule in school.classification.triggered_rules if rule.standing is not None
    ]
    values = {
        AcademicStanding.ABOVE: Decimal(100),
        AcademicStanding.WITHIN: Decimal(70),
        AcademicStanding.BELOW: Decimal(25),
    }
    if not standings:
        return _missing("Academic fit", "compatible institutional academic range")
    score = sum((values[value] for value in standings), Decimal(0)) / len(standings)
    return FitComponent(
        name="Academic fit",
        weight=_WEIGHTS["Academic fit"],
        score=_round(score),
        evidence=f"{len(standings)} compatible admissions comparison(s)",
    )


def _major_component(major: str, offerings: list[ProgramOffering] | None) -> _MajorEvidence:
    mapping = _cip_mapping(major)
    if mapping is None:
        return _MajorEvidence(
            _missing("Major fit", f"reviewed CIP mapping for {major}"),
            None,
            None,
            None,
            None,
        )
    if not offerings:
        return _MajorEvidence(
            _missing("Major fit", "institution program data"),
            None,
            None,
            None,
            None,
        )
    six = [item for item in offerings if item.cip_level == 6 and item.cip_code in mapping.cip6]
    four = [item for item in offerings if item.cip_level == 4 and item.cip_code in mapping.cip4]
    two = [item for item in offerings if item.cip_level == 2 and item.cip_code in mapping.cip2]
    if six:
        completions = sum(item.completion_count or 0 for item in six)
        four_outcome = max(four, key=_program_outcome_sort, default=None)
        score = Decimal(70) + min(Decimal(15), Decimal(completions) / Decimal(5))
        if four_outcome and four_outcome.median_earnings_1yr is not None:
            score += _earnings_score(four_outcome.median_earnings_1yr, maximum=Decimal(15))
        component = FitComponent(
            name="Major fit",
            weight=_WEIGHTS["Major fit"],
            score=_round(min(Decimal(100), score)),
            evidence=(
                "Exact six-digit IPEDS CIP availability with "
                f"{completions} bachelor's completion(s); "
                + (
                    "four-digit Scorecard outcomes included"
                    if four_outcome
                    else "four-digit outcomes unavailable"
                )
            ),
            missing_inputs=[] if four_outcome else ["four-digit Scorecard program outcomes"],
        )
        return _MajorEvidence(
            component,
            True,
            6,
            six[0].cip_code,
            four_outcome.cip_code if four_outcome else None,
        )
    if four:
        best = max(four, key=_program_outcome_sort)
        score = Decimal(55)
        if best.median_earnings_1yr is not None:
            score += _earnings_score(best.median_earnings_1yr, maximum=Decimal(25))
        component = FitComponent(
            name="Major fit",
            weight=_WEIGHTS["Major fit"],
            score=_round(min(Decimal(80), score)),
            evidence="Four-digit Scorecard field match; exact six-digit availability unavailable",
            missing_inputs=["exact six-digit IPEDS program availability"],
        )
        return _MajorEvidence(component, True, 4, None, best.cip_code)
    if two:
        share = sum((Decimal(str(item.share_of_awards or 0)) for item in two), Decimal(0))
        component = FitComponent(
            name="Major fit",
            weight=_WEIGHTS["Major fit"],
            score=_round(min(Decimal(55), Decimal(35) + share * Decimal(100))),
            evidence="Broad two-digit CIP fallback; exact program availability is unconfirmed",
            missing_inputs=["four- and six-digit program evidence"],
        )
        return _MajorEvidence(component, None, 2, None, None)
    has_six_digit_data = any(item.cip_level == 6 for item in offerings)
    return _MajorEvidence(
        FitComponent(
            name="Major fit",
            weight=_WEIGHTS["Major fit"],
            score=Decimal(0) if has_six_digit_data else None,
            evidence="Mapped program was not found in available institutional program data",
            missing_inputs=[] if has_six_digit_data else ["six-digit IPEDS program availability"],
        ),
        False if has_six_digit_data else None,
        None,
        None,
        None,
    )


def _preference_component(student: StudentProfile, school: SchoolReport) -> FitComponent:
    preferences = student.preferences
    scores: list[Decimal] = []
    evidence: list[str] = []
    if school.institution.state in preferences.excluded_states:
        scores.append(Decimal(0))
        evidence.append("excluded state")
    elif preferences.preferred_states:
        preferred = school.institution.state in preferences.preferred_states
        scores.append(Decimal(100 if preferred else 35))
        evidence.append("preferred state" if preferred else "outside preferred states")
    else:
        scores.append(Decimal(60))
        evidence.append("no state preference")

    if preferences.annual_budget is not None:
        cost = _comparable_cost(student, school)
        if cost is not None:
            scores.append(Decimal(100 if Decimal(cost) <= preferences.annual_budget else 20))
            evidence.append("published cost compared with stated budget")
    return FitComponent(
        name="Student preferences",
        weight=_WEIGHTS["Student preferences"],
        score=_round(sum(scores, Decimal(0)) / len(scores)),
        evidence="; ".join(evidence),
    )


def _outcomes_component(school: SchoolReport) -> FitComponent:
    institution = school.institution
    scores: list[Decimal] = []
    labels: list[str] = []
    if institution.graduation_rate is not None:
        scores.append(Decimal(str(institution.graduation_rate)) * 100)
        labels.append("graduation rate")
    if institution.retention_rate is not None:
        scores.append(Decimal(str(institution.retention_rate)) * 100)
        labels.append("retention rate")
    if institution.median_earnings_10_years is not None:
        earnings = Decimal(institution.median_earnings_10_years)
        scores.append(max(Decimal(0), min(Decimal(100), (earnings - 20000) / 800)))
        labels.append("institution-level earnings")
    if not scores:
        return _missing("Outcomes", "graduation, retention, or earnings data")
    return FitComponent(
        name="Outcomes",
        weight=_WEIGHTS["Outcomes"],
        score=_round(sum(scores, Decimal(0)) / len(scores)),
        evidence=", ".join(labels),
    )


def _holistic_component(
    student: StudentProfile,
    major: str,
    major_evidence: _MajorEvidence,
) -> FitComponent:
    themes = {theme.casefold() for theme in student.holistic.themes}
    for activity in student.holistic.activities:
        themes.update(theme.casefold() for theme in activity.themes)
    if not themes:
        return _missing("Holistic alignment", "confirmed résumé/activity themes")
    mapping = _cip_mapping(major)
    if mapping is None or major_evidence.component.score is None:
        return _missing("Holistic alignment", "school program evidence for résumé alignment")
    aligned = set().union(*(_CIP_THEMES.get(code, set()) for code in mapping.cip2))
    matches = sorted(
        theme for theme in themes if any(token in theme or theme in token for token in aligned)
    )
    if major_evidence.component.score == 0:
        score = Decimal(0)
    elif matches:
        score = min(Decimal(100), Decimal(20) + major_evidence.component.score * Decimal("0.8"))
    else:
        score = Decimal(35)
    return FitComponent(
        name="Holistic alignment",
        weight=_WEIGHTS["Holistic alignment"],
        score=_round(score),
        evidence=(
            f"Aligned themes: {', '.join(matches)}; supported by "
            f"{major_evidence.match_granularity or 'unknown'}-digit program evidence"
            if matches
            else "No confirmed theme aligned with the mapped program family"
        ),
    )


def _consolidate(
    student: StudentProfile, results: list[MajorFitResult]
) -> list[ConsolidatedFitResult]:
    if len(student.preferences.intended_majors) < 2:
        return []
    priorities = {
        major: Decimal(len(student.preferences.intended_majors) - index)
        for index, major in enumerate(student.preferences.intended_majors)
    }
    grouped: dict[int, list[MajorFitResult]] = defaultdict(list)
    for result in results:
        if result.program_offered is not False:
            grouped[result.unit_id].append(result)
    unranked: list[tuple[int, str, Decimal, list[str]]] = []
    for unit_id, items in grouped.items():
        weight = sum((priorities[item.intended_major] for item in items), Decimal(0))
        score = (
            sum(
                (item.overall_score * priorities[item.intended_major] for item in items),
                Decimal(0),
            )
            / weight
        )
        unranked.append(
            (unit_id, items[0].institution_name, _round(score), [i.intended_major for i in items])
        )
    ordered = sorted(unranked, key=lambda item: (-len(item[3]), -item[2], item[0]))
    return [
        ConsolidatedFitResult(
            unit_id=unit_id,
            institution_name=name,
            rank=index,
            score=score,
            supported_majors=majors,
            explanation=f"Priority-weighted fit across {len(majors)} intended major(s).",
        )
        for index, (unit_id, name, score, majors) in enumerate(ordered, 1)
    ]


def _cip_codes(major: str) -> list[str]:
    mapping = _cip_mapping(major)
    if mapping is None:
        return []
    return list(dict.fromkeys((*mapping.cip6, *mapping.cip4, *mapping.cip2)))


def _cip_mapping(major: str) -> _MajorMapping | None:
    normalized = " ".join(major.casefold().replace("/", " ").replace("-", " ").split())
    if normalized in _MAJOR_CIP:
        return _MAJOR_CIP[normalized]
    matches = [
        mapping for name, mapping in _MAJOR_CIP.items() if name in normalized or normalized in name
    ]
    return matches[0] if len(matches) == 1 else None


def _program_outcome_sort(offering: ProgramOffering) -> tuple[int, int, int]:
    return (
        offering.median_earnings_1yr or 0,
        offering.median_earnings_5yr or 0,
        offering.completion_count or 0,
    )


def _earnings_score(value: int, *, maximum: Decimal) -> Decimal:
    normalized = max(Decimal(0), min(Decimal(1), (Decimal(value) - 20000) / 80000))
    return normalized * maximum


def _comparable_cost(student: StudentProfile, school: SchoolReport) -> int | None:
    institution = school.institution
    budget_type = student.preferences.budget_type
    if budget_type is BudgetType.NET_PRICE:
        return institution.average_net_price
    if budget_type is BudgetType.PUBLISHED_COST:
        return institution.cost_of_attendance or institution.tuition_out_of_state
    return None


def _missing(name: str, value: str) -> FitComponent:
    return FitComponent(
        name=name,
        weight=_WEIGHTS[name],
        score=None,
        evidence="Not scored",
        missing_inputs=[value],
    )


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
