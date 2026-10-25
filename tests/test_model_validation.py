"""Validate model fields, globally unique identifiers and outlet selection."""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pytest

from pyromb import Builder, Catchment, VectorLayer
from pyromb.core.attributes.basin import Basin
from pyromb.core.attributes.confluence import Confluence
from pyromb.core.attributes.reach import Reach


class MemoryLayer(VectorLayer):
    def __init__(self, features: list[tuple[list[tuple[float, float]], dict[str, object]]]) -> None:
        self.features = features

    def geometry(self, i: int) -> list[tuple[float, float]]:
        return self.features[i][0]

    def record(self, i: int) -> dict[str, object]:
        return self.features[i][1]

    def __len__(self) -> int:
        return len(self.features)


def confluences(*outs):
    return MemoryLayer([
        ([(i * 10, 0)], {"id": f"C{i}", "out": value})
        for i, value in enumerate(outs)
    ])


def reaches(**overrides):
    attrs = {"id": "R1", "t": 1, "s": 0.001}
    attrs.update(overrides)
    return MemoryLayer([([(0, 0), (10, 0)], attrs)])


def test_one_outlet_accepted():
    result = Builder().confluence(confluences(0, 1, 0))
    assert [c.isOut for c in result] == [False, True, False]


@pytest.mark.parametrize("values", [(0, 0), (1, 1), ()])
def test_zero_or_multiple_outlets_rejected(values):
    with pytest.raises(ValueError, match="exactly one outlet"):
        Builder().confluence(confluences(*values))


@pytest.mark.parametrize("bad_value", [2, -1, "1", "True", None])
def test_invalid_outlet_flag_rejected(bad_value):
    with pytest.raises(ValueError, match="out"):
        Builder().confluence(confluences(bad_value))


@pytest.mark.parametrize("field,bad_value", [
    ("t", 1.5), ("t", 7), ("t", "abc"),
    ("s", -0.01), ("s", float("nan")), ("s", float("inf")),
    ("s", True), ("s", "wrong"),
])
def test_invalid_reach_attributes_rejected(field, bad_value):
    with pytest.raises(ValueError, match=field):
        Builder().reach(reaches(**{field: bad_value}))


def test_legacy_valid_reach_attributes_accepted():
    result = Builder().reach(reaches())
    assert len(result) == 1 and result[0].slope == pytest.approx(0.001)


@pytest.mark.parametrize("bad_value", [
    None, "", "  ", float("nan"), float("inf"),
    np.float32("nan"), np.float32("inf"), Decimal("NaN"), Decimal("Infinity"),
])
def test_empty_or_invalid_identifier_rejected(bad_value):
    # One invalid identifier is rejected before any topology operation.
    basins = [Basin(bad_value, 10, 0, 1, 0)]
    with pytest.raises(ValueError, match="identifier|Duplicate"):
        Catchment([Confluence("OUT", 0, 0, True)], basins, [])


@pytest.mark.parametrize("names", [
    ("B", "C", "B"),  # Reach collides with basin.
    ("C", "C", "R"),  # Basin collides with confluence.
])
def test_duplicate_global_model_identifiers_rejected(names):
    basin_name, confluence_name, reach_name = names
    basin = Basin(basin_name, 0, 0, 1, 0)
    confluence = Confluence(confluence_name, 10, 0, True)
    reach = Reach(reach_name, [(0, 0), (10, 0)])
    with pytest.raises(ValueError, match="Duplicate model identifier"):
        Catchment([confluence], [basin], [reach])


def test_distinct_global_model_identifiers_accepted():
    catchment = Catchment(
        [Confluence("OUT", 10, 0, True)],
        [Basin("B1", 0, 0, 1, 0)],
        [Reach("R1", [(0, 0), (10, 0)])],
    )
    assert len(catchment._vertices) == 2 and len(catchment._edges) == 1


@pytest.mark.parametrize("category", ["confluences", "basins", "reaches"])
def test_duplicate_identifiers_within_each_category(category):
    constructors = {
        "confluences": lambda: Confluence("same", 0, 0, True),
        "basins": lambda: Basin("same", 0, 0, 1, 0),
        "reaches": lambda: Reach("same", [(0, 0), (10, 0)]),
    }
    with pytest.raises(ValueError, match="Duplicate model identifier"):
        Catchment(**{category: [constructors[category](), constructors[category]()]})


@pytest.mark.parametrize("reach_type", [1, 2, 3, 4, 1.0, "1"])
@pytest.mark.parametrize("slope", [0, 0.001, "0.001"])
def test_supported_reach_values(reach_type, slope):
    reach = Builder().reach(reaches(t=reach_type, s=slope))[0]
    assert reach.type.value == int(reach_type)
    assert reach.slope == float(slope)


@pytest.mark.parametrize("bad_fraction", [-0.1, 1.1, "invalid", float("nan")])
def test_invalid_impervious_fraction_rejected(bad_fraction):
    pytest.importorskip("osgeo.ogr")
    basin = MemoryLayer([(
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], {}
    )])
    centroid = MemoryLayer([(
        [(5, 5)], {"id": "B1", "fi": bad_fraction}
    )])
    with pytest.raises(ValueError, match="fi"):
        Builder().basin(centroid, basin)
