"""Deterministic, explainable fit ranking kept separate from admissions classification."""

from __future__ import annotations

from collections import defaultdict
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

FIT_METHODOLOGY_VERSION = "1.0"

_WEIGHTS = {
    "Academic fit": Decimal("30"),
    "Major fit": Decimal("25"),
    "Student preferences": Decimal("15"),
    "Outcomes": Decimal("20"),
    "Holistic alignment": Decimal("10"),
}

_MAJOR_CIP: dict[str, tuple[str, ...]] = {
    "biology": ("26",),
    "biochemistry": ("26", "40"),
    "chemistry": ("40",),
    "molecular biology": ("26",),
    "neuroscience": ("26",),
    "physiology": ("26",),
    "genetics": ("26",),
    "microbiology": ("26",),
    "biomedical engineering": ("14",),
    "human physiology": ("26",),
    "computer science": ("11",),
    "mathematics": ("27",),
    "engineering": ("14",),
    "psychology": ("42",),
    "business": ("52",),
    "history": ("54",),
    "english": ("23",),
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
    components = [
        _academic_component(school),
        _major_component(major, offerings),
        _preference_component(student, school),
        _outcomes_component(school),
        _holistic_component(student, major, offerings),
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
    missing = [value for component in components for value in component.missing_inputs]
    major_component = components[1]
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
        program_offered=(
            None if major_component.score is None else major_component.score > Decimal(0)
        ),
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


def _major_component(major: str, offerings: list[ProgramOffering] | None) -> FitComponent:
    codes = _cip_codes(major)
    if not codes:
        return _missing("Major fit", f"reviewed CIP mapping for {major}")
    if not offerings:
        return _missing("Major fit", "institution program-family data")
    matches = [offering for offering in offerings if offering.cip_code in codes]
    if not matches:
        return FitComponent(
            name="Major fit",
            weight=_WEIGHTS["Major fit"],
            score=Decimal(0),
            evidence=f"No reported awards in mapped CIP families {', '.join(codes)}",
        )
    share = sum((Decimal(str(item.share_of_awards)) for item in matches), Decimal(0))
    score = min(Decimal(100), Decimal(70) + share * Decimal(300))
    return FitComponent(
        name="Major fit",
        weight=_WEIGHTS["Major fit"],
        score=_round(score),
        evidence=f"Reported CIP family share {share:.1%} ({', '.join(codes)})",
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
    offerings: list[ProgramOffering] | None,
) -> FitComponent:
    themes = {theme.casefold() for theme in student.holistic.themes}
    for activity in student.holistic.activities:
        themes.update(theme.casefold() for theme in activity.themes)
    if not themes:
        return _missing("Holistic alignment", "confirmed résumé/activity themes")
    codes = _cip_codes(major)
    if not codes or not offerings:
        return _missing("Holistic alignment", "school program evidence for résumé alignment")
    aligned = set().union(*(_CIP_THEMES.get(code, set()) for code in codes))
    matches = sorted(
        theme for theme in themes if any(token in theme or theme in token for token in aligned)
    )
    program_share = sum(
        (
            Decimal(str(offering.share_of_awards))
            for offering in offerings
            if offering.cip_code in codes
        ),
        Decimal(0),
    )
    if program_share == 0:
        score = Decimal(0)
    elif matches:
        score = min(Decimal(100), Decimal(65) + program_share * Decimal(350))
    else:
        score = Decimal(35)
    return FitComponent(
        name="Holistic alignment",
        weight=_WEIGHTS["Holistic alignment"],
        score=_round(score),
        evidence=(
            f"Aligned themes: {', '.join(matches)}; mapped program share {program_share:.1%}"
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
    normalized = " ".join(major.casefold().replace("/", " ").replace("-", " ").split())
    if normalized in _MAJOR_CIP:
        return list(_MAJOR_CIP[normalized])
    matches = [
        codes for name, codes in _MAJOR_CIP.items() if name in normalized or normalized in name
    ]
    return list(dict.fromkeys(code for codes in matches for code in codes))


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
