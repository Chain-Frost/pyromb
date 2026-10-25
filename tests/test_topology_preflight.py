"""Validate catchment reach/node topology without changing the model writer."""

from __future__ import annotations

import pytest

from pyromb import Catchment
from pyromb.core.attributes.basin import Basin
from pyromb.core.attributes.confluence import Confluence
from pyromb.core.attributes.reach import Reach


def catchment(*, extra_nodes=(), edges=None, outlet=None):
    out = outlet if outlet is not None else Confluence("OUT", 10, 0, True)
    nodes = [Basin("B1", 0, 0, 1, 0), *extra_nodes]
    edges = (
        [Reach("R1", [(0, 0), (10, 0)])] if edges is None else edges
    )
    return Catchment([out], nodes, edges)


def test_valid_exactly_snapped_reach_passes():
    model = catchment()
    ds, us = model.connect()
    assert ds.shape == (2, 1)
    assert us.shape == (2, 1)


def test_unsnapped_endpoint_is_reported():
    model = catchment(edges=[
        Reach("R1", [(0, 0), (10.01, 0)])
    ])
    with pytest.raises(ValueError, match="R1.*end.*not snapped.*OUT"):
        model.connect()


def test_explicit_tolerance_allows_small_endpoint_offset():
    model = catchment(edges=[
        Reach("R1", [(0, 0), (10.01, 0)])
    ])
    ds, us = model.connect(tolerance=0.02)
    assert ds.shape == (2, 1) and us.shape == (2, 1)


@pytest.mark.parametrize("tolerance", [-1, float("nan"), float("inf"), "0.1"])
def test_invalid_tolerance_rejected(tolerance):
    with pytest.raises(ValueError, match="Connection tolerance"):
        catchment().connect(tolerance=tolerance)


def test_ambiguous_endpoint_multiple_nodes():
    model = Catchment(
        [
            Confluence("OUT", 10, 0, True),
            Confluence("C2", 10, 0, False),
        ],
        [Basin("B1", 0, 0, 1, 0)],
        [Reach("R1", [(0, 0), (10, 0)])],
    )
    with pytest.raises(ValueError, match="R1.*end.*ambiguous"):
        model.connect()


def test_reach_loop_to_same_node_is_rejected():
    model = catchment(edges=[
        Reach("R1", [(0, 0), (0, 0)])
    ])
    with pytest.raises(ValueError, match="connects node.*to itself"):
        model.connect()


def test_disconnected_subnetwork_rejected():
    model = catchment(
        extra_nodes=[Basin("B2", 20, 0, 1, 0), Basin("B3", 30, 0, 1, 0)],
        edges=[
            Reach("R1", [(0, 0), (10, 0)]),
            Reach("R2", [(20, 0), (30, 0)]),
        ],
    )
    with pytest.raises(ValueError, match="Disconnected catchment.*B2.*B3"):
        model.connect()


def test_parallel_reaches_are_rejected_as_cycle():
    model = catchment(edges=[
        Reach("R1", [(0, 0), (10, 0)]),
        Reach("R2", [(0, 0), (10, 0)]),
    ])
    with pytest.raises(ValueError, match="cycle or parallel reaches"):
        model.connect()


def test_triangle_cycle_rejected():
    model = catchment(
        extra_nodes=[Basin("B2", 5, 10, 1, 0)],
        edges=[
            Reach("R1", [(0, 0), (10, 0)]),
            Reach("R2", [(0, 0), (5, 10)]),
            Reach("R3", [(5, 10), (10, 0)]),
        ],
    )
    with pytest.raises(ValueError, match="cycle or parallel reaches"):
        model.connect()


@pytest.mark.parametrize("flags", [(False, False), (True, True)])
def test_catchment_direct_use_requires_exactly_one_outlet(flags):
    model = Catchment(
        [Confluence("C1", 10, 0, flags[0]), Confluence("C2", 20, 0, flags[1])],
        [Basin("B1", 0, 0, 1, 0)],
        [Reach("R1", [(0, 0), (10, 0)])],
    )
    with pytest.raises(ValueError, match="exactly one outlet"):
        model.connect()
