from datetime import timedelta
from unittest.mock import Mock

import pytest

from devOS.use_cases.run_agents import RunAgentsUseCase, _parse_schedule_args


def test_parse_schedule_args_with_minutes() -> None:
    assert _parse_schedule_args(["5", "minutes"]) == timedelta(minutes=5)


def test_parse_schedule_args_with_multiple_units() -> None:
    assert _parse_schedule_args(["1", "hour", "30", "minutes"]) == timedelta(
        hours=1, minutes=30
    )


def test_parse_schedule_args_rejects_invalid_pairs() -> None:
    with pytest.raises(ValueError):
        _parse_schedule_args(["5", "minutes", "oops"])


def test_run_every_triggers_run_on_schedule() -> None:
    use_case = RunAgentsUseCase()
    use_case.run_on_schedule = Mock() # type: ignore

    use_case.run_every("2", "hours")

    use_case.run_on_schedule.assert_called_once_with(timedelta(hours=2))
