from app.services.movement_service import MovementService


# Use the service method
normalize_name = MovementService.normalize_movement_name


def test_normalize_name_lemmatizes_pull_ups():
    assert normalize_name("Pull-Ups") == "pull-up"


def test_normalize_name_handles_case_variations():
    assert normalize_name("PULL UPS") == "pull-up"
    assert normalize_name("pull ups") == "pull-up"


def test_normalize_name_handles_hyphenation_variations():
    assert normalize_name("Pull-Ups") == normalize_name("Pull Ups")
