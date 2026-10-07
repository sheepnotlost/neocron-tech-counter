import pytest

from ntc.slots import parse_qty


@pytest.mark.parametrize("text,expected", [
    ("", None), ("x2", 2), ("x5", 5), ("x14", 14), (" x 3 ", 3), ("x2 4", 2),     # trailing junk is ignored
    ("2", None), ("14", None),        # without the "x" it is not a stack number (icon edges read as digits)
    ("xx", None), ("x1234", None),
])
def test_parse_qty(text, expected):
    assert parse_qty(text) == expected
