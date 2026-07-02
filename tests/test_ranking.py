from __future__ import annotations

from app.models import (
    AdmissionCategory,
    HolisticProfile,
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
            share_of_awards=0.25,
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9001,
            cip_code="14",
            cip_title="Engineering",
            share_of_awards=0.01,
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9002,
            cip_code="26",
            cip_title="Biological and Biomedical Sciences",
            share_of_awards=0.01,
            dataset_version_id="test",
        ),
        ProgramOffering(
            unit_id=9002,
            cip_code="14",
            cip_title="Engineering",
            share_of_awards=0.25,
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
