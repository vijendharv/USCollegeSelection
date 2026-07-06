"""Major-preparation and grade-trend signals that remain separate from admit categories."""

from __future__ import annotations

from statistics import mean

from app.academics.gpa import _points
from app.models.academic import Course, CourseLevel, PreparationSignal

_LIFE_SCIENCE = (
    "biology",
    "biochemistry",
    "chemistry",
    "molecular",
    "neuroscience",
    "physiology",
    "genetics",
    "microbiology",
    "biomedical",
    "pre-med",
)


def analyze_preparation(courses: list[Course], majors: list[str]) -> list[PreparationSignal]:
    signals: list[PreparationSignal] = []
    by_grade = {
        grade: [_points(c) for c in courses if c.grade_level == grade and _points(c) is not None]
        for grade in range(9, 13)
    }
    early = [float(v) for grade in (9, 10) for v in by_grade[grade]]
    late = [float(v) for grade in (11, 12) for v in by_grade[grade]]
    if early and late:
        delta = mean(late) - mean(early)
        level = "strength" if delta >= 0.2 else "attention" if delta <= -0.2 else "unknown"
        signals.append(
            PreparationSignal(
                code="grade_trend",
                level=level,
                message=(
                    f"Completed-course grade trend changed by {delta:+.2f} grade points "
                    "from grades 9-10 to 11-12."
                ),
            )
        )
    else:
        signals.append(
            PreparationSignal(
                code="grade_trend",
                level="unknown",
                message=(
                    "Grade trend is unavailable because grade levels or completed letter "
                    "grades are incomplete."
                ),
            )
        )
    if not any(any(token in major.casefold() for token in _LIFE_SCIENCE) for major in majors):
        return signals
    text = [f"{c.subject} {c.name or ''}".casefold() for c in courses]
    for subject in ("biology", "chemistry", "physics", "calculus"):
        if not any(subject in item for item in text):
            signals.append(
                PreparationSignal(
                    code=f"missing_{subject}",
                    level="attention",
                    message=(
                        f"No confirmed {subject} course was found for life-science "
                        "preparation review."
                    ),
                )
            )
    advanced = sum(
        c.level in {CourseLevel.AP, CourseLevel.IB, CourseLevel.DUAL_ENROLLMENT}
        and any(token in text_item for token in (*_LIFE_SCIENCE, "physics", "calculus"))
        for c, text_item in zip(courses, text, strict=True)
    )
    signals.append(
        PreparationSignal(
            code="advanced_life_science",
            level="strength" if advanced >= 2 else "attention",
            message=(
                f"Found {advanced} advanced life-science/STEM course(s); this is "
                "preparation context, not an admission prediction."
            ),
        )
    )
    return signals
