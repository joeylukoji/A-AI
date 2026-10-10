"""Interval coverage edge cases complement the shared document fixtures."""

import pytest
from app.perimeter_validation import _covers_side


@pytest.mark.parametrize(
    "intervals,expected",
    [
        ([], False),
        ([(0, 10)], True),
        ([(5, 10), (0, 6), (2, 3)], True),
        ([(0, 4), (4.0000005, 10)], True),
        ([(0, 4), (4.0000015, 10)], False),
        ([(0, 3), (3.00000075, 6), (6.00000075, 10)], True),
        ([(0, 10), (2, 3)], True),
    ],
)
def test_side_coverage(intervals, expected):
    before = list(intervals)
    assert _covers_side(intervals, 10) is expected
    assert intervals == before
