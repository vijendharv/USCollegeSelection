from __future__ import annotations

from app.models import (
    AcademicStanding,
    AdmissionCategory,
    HolisticProfile,
    HolisticReviewStatus,
    ProgramOffering,
    SchoolReport,
    StudentPreferences,
    StudentProfile,
)
from app.ranking import FIT_METHODOLOGY_VERSION, rank_major_fits
from tests.test_reporting import sample_report, student


def _schools() -> list[SchoolReport]:
    base = sample_report().schools[1]
    first_institution = base.institution.model_copy(
        update={"unit_id": 9001, "name": "Alpha University"}
    )
    second_institution = base.institution.model_copy(
        update={"unit_id": 9002, "name": "Zulu University"}
    )
    first = base.model_copy(
        update={
            "institution": first_institution,
            "classification": base.classification.model_copy(
                update={
                    "unit_id": 9001,
                    "institution_name": "Alpha University",
                    "category": AdmissionCategory.TARGET,
                }
            ),
        }
    )
    second = base.model_copy(
        update={
            "institution": second_institution,
            "classification": base.classification.model_copy(
                update={
                    "unit_id": 9002,
                    "institution_name": "Zulu University",
                    "category": AdmissionCategory.TARGET,
                }
            ),
        }
    )
    return [first, second]


def _profile() -> StudentProfile:
    return student().model_copy(
        update={
            "preferences": StudentPreferences(
                residence_state="CA",
                intended_majors=["Biology", "Biomedical Engineering"],
            ),
            "holistic": HolisticProfile(themes=["healthcare", "research"]),
        }
    )


def _offerings() -> list[ProgramOffering]:
    return [
        ProgramOffering(
            unit_id=9001,
            cip_code="26",
            cip_title="Biological and Biomedical Sciences",
            cip_level=2,
            share_of_awards=0.25,
            source_name="fixture",
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9001,
            cip_code="14",
            cip_title="Engineering",
            cip_level=2,
            share_of_awards=0.01,
            source_name="fixture",
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9002,
            cip_code="26",
            cip_title="Biological and Biomedical Sciences",
            cip_level=2,
            share_of_awards=0.01,
            source_name="fixture",
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9002,
            cip_code="14",
            cip_title="Engineering",
            cip_level=2,
            share_of_awards=0.25,
            source_name="fixture",
            dataset_version_id="test",
        ),
    ]


def test_per_major_rank_changes_with_program_evidence() -> None:
    ranked, consolidated = rank_major_fits(_profile(), _schools(), _offerings())

    biology = [item for item in ranked if item.intended_major == "Biology"]
    engineering = [item for item in ranked if item.intended_major == "Biomedical Engineering"]
    assert biology[0].institution_name == "Alpha University"
    assert engineering[0].institution_name == "Zulu University"
    assert all(item.methodology_version == FIT_METHODOLOGY_VERSION for item in ranked)
    assert consolidated


def test_ranking_is_independent_of_candidate_input_order() -> None:
    forward, _ = rank_major_fits(_profile(), _schools(), _offerings())
    reverse, _ = rank_major_fits(_profile(), list(reversed(_schools())), _offerings())

    assert [item.model_dump() for item in forward] == [item.model_dump() for item in reverse]


def test_resume_context_does_not_change_admissions_categories() -> None:
    schools = _schools()
    without_resume = _profile().model_copy(update={"holistic": HolisticProfile()})

    ranked_with, _ = rank_major_fits(_profile(), schools, _offerings())
    ranked_without, _ = rank_major_fits(without_resume, schools, _offerings())

    assert [item.category for item in ranked_with] == [item.category for item in ranked_without]
    assert [item.overall_score for item in ranked_with] != [
        item.overall_score for item in ranked_without
    ]
    assert [school.classification.category for school in schools] == [
        AdmissionCategory.TARGET,
        AdmissionCategory.TARGET,
    ]


def test_resume_evidence_needing_review_is_not_scored() -> None:
    pending = _profile().model_copy(
        update={
            "holistic": HolisticProfile(
                review_status=HolisticReviewStatus.NEEDS_REVIEW,
                themes=["healthcare", "research"],
            )
        }
    )
    empty = _profile().model_copy(update={"holistic": HolisticProfile()})

    pending_ranked, _ = rank_major_fits(pending, _schools(), _offerings())
    empty_ranked, _ = rank_major_fits(empty, _schools(), _offerings())

    assert [item.overall_score for item in pending_ranked] == [
        item.overall_score for item in empty_ranked
    ]
    assert all("confirmed résumé/activity review" in item.missing_inputs for item in pending_ranked)


def test_six_digit_availability_and_four_digit_outcomes_are_combined() -> None:
    offerings = [
        *_offerings(),
        ProgramOffering(
            unit_id=9001,
            cip_code="260101",
            cip_title="CIP 26.0101",
            cip_level=6,
            credential_level=3,
            completion_count=40,
            source_name="IPEDS Completions",
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9001,
            cip_code="2601",
            cip_title="Biology General",
            cip_level=4,
            credential_level=3,
            completion_count=45,
            median_earnings_1yr=65000,
            source_name="College Scorecard field of study",
            dataset_version_id="test",
        ),
    ]

    ranked, _ = rank_major_fits(_profile(), _schools(), offerings)
    biology = next(
        item for item in ranked if item.unit_id == 9001 and item.intended_major == "Biology"
    )

    assert biology.program_offered is True
    assert biology.match_granularity == 6
    assert biology.availability_cip_code == "260101"
    assert biology.ranking_cip_code == "2601"
    assert biology.national_rank == 1
    assert biology.national_rank_total == 1


def test_national_rank_covers_exact_programs_across_categories() -> None:
    offerings = [
        *_offerings(),
        *[
            ProgramOffering(
                unit_id=unit_id,
                cip_code="260101",
                cip_title="CIP 26.0101",
                cip_level=6,
                credential_level=3,
                completion_count=completions,
                source_name="IPEDS Completions",
                dataset_version_id="test",
            )
            for unit_id, completions in ((9001, 40), (9002, 10))
        ],
    ]

    ranked, _ = rank_major_fits(_profile(), _schools(), offerings)
    biology = [item for item in ranked if item.intended_major == "Biology"]

    assert {item.national_rank_total for item in biology} == {2}
    assert sorted(item.national_rank for item in biology) == [1, 2]
    assert {item.national_program_strength_rank_total for item in biology} == {2}


def test_program_strength_precedes_a_small_fit_advantage_within_category() -> None:
    schools = _schools()
    schools[0].institution.state = "NV"
    for school in schools:
        school.classification.triggered_rules = [
            rule.model_copy(update={"standing": AcademicStanding.ABOVE})
            if rule.standing is not None
            else rule
            for rule in school.classification.triggered_rules
        ]
    profile = _profile().model_copy(
        update={
            "preferences": StudentPreferences(
                residence_state="CA",
                intended_majors=["Biology"],
                preferred_states=["CA"],
            )
        }
    )
    offerings = [
        ProgramOffering(
            unit_id=unit_id,
            cip_code="260101",
            cip_title="Biology",
            cip_level=6,
            credential_level=3,
            completion_count=completions,
            source_name="IPEDS Completions",
            dataset_version_id="test",
        )
        for unit_id, completions in ((9001, 100), (9002, 1))
    ]
    offerings.append(
        ProgramOffering(
            unit_id=9001,
            cip_code="2601",
            cip_title="Biology, General",
            cip_level=4,
            credential_level=3,
            completion_count=100,
            median_earnings_1yr=95000,
            source_name="College Scorecard field of study",
            dataset_version_id="test",
        )
    )

    ranked, _ = rank_major_fits(profile, schools, offerings)

    assert all(item.overall_score >= 80 for item in ranked)
    assert ranked[0].program_strength_score > ranked[1].program_strength_score
    assert ranked[0].overall_score < ranked[1].overall_score
    assert ranked[0].rank == 1
