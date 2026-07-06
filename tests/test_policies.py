from app.models import Institution
from app.models import TestPolicy as InstitutionTestPolicy
from app.policies import apply_institution_policies


def test_default_policy_overrides_are_sourced_and_reviewable() -> None:
    school = Institution(
        unit_id=1,
        name="University of Washington-Seattle Campus",
        city="Seattle",
        state="WA",
        main_campus=True,
        highest_degree=4,
        dataset_version_id="test",
    )

    enriched = apply_institution_policies([school])[0]

    assert enriched.test_policy is InstitutionTestPolicy.NOT_VISIBLE_PRIMARY_REVIEW
    assert enriched.test_policy_source_url
