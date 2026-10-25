"""Validate catchment reach/node topology without changing the model writer."""

from __future__ import annotations

import itertools
import math

import numpy as np
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


@pytest.mark.parametrize("tolerance", [
    -1, float("nan"), float("inf"), "0.1", True, pytest.param(10**400, id="overflow"),
])
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


@pytest.mark.parametrize("offset,tolerance,accepted", [
    (0, 0, True), (1e-8, 0, False), (1e-7, 1e-6, True),
    (0.125, 0.125, True), (0.125, math.nextafter(0.125, 0), False),
])
def test_tolerance_boundary_and_unchanged_coordinates(offset, tolerance, accepted):
    model = catchment(edges=[Reach("R1", [(offset, 0), (10, 0)])])
    before = [p.coordinates() for p in model._edges[0].toVector()]
    if accepted:
        model.connect(tolerance=tolerance)
    else:
        with pytest.raises(ValueError, match="R1.*start.*not snapped.*B1"):
            model.connect(tolerance=tolerance)
    assert [p.coordinates() for p in model._edges[0].toVector()] == before


@pytest.mark.parametrize("distance", [999, 1000])
def test_large_explicit_tolerance_does_not_silently_lose_a_reach(distance):
    model = Catchment(
        [Confluence("OUT", 10000, 0, True)],
        [Basin("B1", 0, 0, 1, 0)],
        [Reach("R1", [(distance, 0), (10000 - distance, 0)])],
    )
    ds, us = model.connect(tolerance=distance)
    assert ds.tolist() == [[-1], [0]]
    assert us.tolist() == [[1], [-1]]


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_node_names_the_node(coordinate):
    model = catchment(extra_nodes=[Basin("BAD", coordinate, 0, 1, 0)])
    with pytest.raises(ValueError, match="Node 'BAD'.*non-finite"):
        model.connect()


@pytest.mark.parametrize("position", [0, 1, 2])
def test_non_finite_reach_vertices_name_the_reach(position):
    points = [(0, 0), (5, 0), (10, 0)]
    points[position] = (float("nan"), 0)
    model = catchment(edges=[Reach("BAD", points)])
    with pytest.raises(ValueError, match="Reach 'BAD'.*non-finite"):
        model.connect()


def test_equidistant_distinct_nodes_report_candidate_distances():
    model = catchment(
        extra_nodes=[Basin("B2", 0, 2, 1, 0)],
        edges=[Reach("R1", [(0, 1), (10, 0)])],
    )
    with pytest.raises(ValueError, match="R1.*start.*ambiguous.*B1.*1.*B2.*1"):
        model.connect(tolerance=1)


@pytest.mark.parametrize("reversed_edges", list(itertools.product([False, True], repeat=3)))
def test_digitising_direction_does_not_define_flow(reversed_edges):
    # The original traversal roots an undirected tree at OUT, irrespective of
    # line digitisation. Every non-outlet node must drain to that outlet.
    points = [[(0, 0), (10, 0)], [(0, 10), (10, 0)], [(10, 0), (20, 0)]]
    edges = [
        Reach(f"R{i}", list(reversed(vector)) if reverse else vector)
        for i, (vector, reverse) in enumerate(zip(points, reversed_edges))
    ]
    model = Catchment(
        [Confluence("OUT", 20, 0, True), Confluence("JOIN", 10, 0, False)],
        [Basin("A", 0, 0, 1, 0), Basin("B", 0, 10, 1, 0)],
        edges,
    )
    ds, us = model.connect()
    assert ds.tolist() == [[-1, -1, -1], [-1, -1, 0], [1, -1, -1], [-1, 1, -1]]
    assert us.tolist() == [[-1, -1, 1], [2, 3, -1], [-1, -1, -1], [-1, -1, -1]]
    assert np.count_nonzero(ds != -1) == np.count_nonzero(us != -1) == 3


def test_duplicate_identifiers_rejected_before_topology():
    with pytest.raises(ValueError, match="Duplicate model identifier 'OUT'"):
        catchment(edges=[Reach("OUT", [(0, 0), (10, 0)])])


def test_isolated_node_is_not_omitted():
    with pytest.raises(ValueError, match="Disconnected catchment.*B2"):
        catchment(extra_nodes=[Basin("B2", 30, 0, 1, 0)]).connect()
