"""Regression tests for robust centroid-to-basin assignment."""

from __future__ import annotations

import pytest

from pyromb import Builder, VectorLayer


class MemoryLayer(VectorLayer):
    def __init__(self, features: list[tuple[list[tuple[float, float]], dict[str, object]]]) -> None:
        self.features = features

    def geometry(self, i: int) -> list[tuple[float, float]]:
        return self.features[i][0]

    def record(self, i: int) -> dict[str, object]:
        return self.features[i][1]

    def __len__(self) -> int:
        return len(self.features)


def rectangle(x0: float, x1: float) -> list[tuple[float, float]]:
    return [(x0, 0), (x1, 0), (x1, 10), (x0, 10), (x0, 0)]


@pytest.fixture
def ogr_backend():
    # Production uses OGR packaged with QGIS. Plain Python test environments
    # without GDAL can still execute the other Builder validation tests.
    return pytest.importorskip("osgeo.ogr")


def test_containment_not_nearest_polygon_centroid(ogr_backend):
    # A centroid near the end of a long basin is far closer to the small
    # neighbouring polygon's centre. Nearest-centre matching repeated B.
    basins = MemoryLayer([
        (rectangle(0, 1000), {}),
        (rectangle(1000, 1010), {}),
    ])
    centroids = MemoryLayer([
        ([(999, 5)], {"id": "A", "fi": 0.1}),
        ([(1005, 5)], {"id": "B", "fi": 0.2}),
    ])
    result = Builder().basin(centroids, basins)
    assert [b.name for b in result] == ["A", "B"]
    assert [b.area for b in result] == pytest.approx([0.01, 0.0001])
    assert [b.fi for b in result] == pytest.approx([0.1, 0.2])


def test_centroid_outside_all_polygons_is_error(ogr_backend):
    basins = MemoryLayer([(rectangle(0, 10), {})])
    centroids = MemoryLayer([([(20, 5)], {"id": "outside", "fi": 0.0})])
    with pytest.raises(ValueError, match="exactly one basin"):
        Builder().basin(centroids, basins)


def test_overlapping_basin_polygons_are_ambiguous(ogr_backend):
    basins = MemoryLayer([
        (rectangle(0, 10), {}),
        (rectangle(5, 15), {}),
    ])
    centroids = MemoryLayer([([(7, 5)], {"id": "overlap", "fi": 0.0})])
    with pytest.raises(ValueError, match="exactly one basin"):
        Builder().basin(centroids, basins)


def test_two_centroids_in_one_basin_is_error(ogr_backend):
    basins = MemoryLayer([(rectangle(0, 10), {})])
    centroids = MemoryLayer([
        ([(2, 5)], {"id": "A", "fi": 0.0}),
        ([(8, 5)], {"id": "B", "fi": 0.0}),
    ])
    with pytest.raises(ValueError, match="multiple centroids"):
        Builder().basin(centroids, basins)


def test_basin_without_a_centroid_is_error(ogr_backend):
    basins = MemoryLayer([
        (rectangle(0, 10), {}),
        (rectangle(20, 30), {}),
    ])
    centroids = MemoryLayer([([(2, 5)], {"id": "A", "fi": 0.0})])
    with pytest.raises(ValueError, match="without centroids"):
        Builder().basin(centroids, basins)


def test_invalid_polygon_is_error(ogr_backend):
    crossed = [(0, 0), (10, 10), (0, 10), (10, 0), (0, 0)]
    basins = MemoryLayer([(crossed, {})])
    centroids = MemoryLayer([([(2, 5)], {"id": "A", "fi": 0.0})])
    with pytest.raises(ValueError, match="invalid"):
        Builder().basin(centroids, basins)


def test_missing_reach_field_is_reported_without_ogr():
    reach = MemoryLayer([([(0, 0), (1, 1)], {"id": "R", "t": 1})])
    with pytest.raises(ValueError, match="missing required field 's'"):
        Builder().reach(reach)


def test_invalid_confluence_geometry_is_reported_without_ogr():
    confluence = MemoryLayer([
        ([(0, 0), (1, 1)], {"id": "C", "out": True}),
    ])
    with pytest.raises(ValueError, match="exactly one point"):
        Builder().confluence(confluence)


def test_boundary_centroid_is_error(ogr_backend):
    with pytest.raises(ValueError, match="exactly one basin"):
        Builder().basin(
            MemoryLayer([([(0, 5)], {"id": "boundary", "fi": 0.0})]),
            MemoryLayer([(rectangle(0, 10), {})]),
        )


def test_missing_centroid_attribute_is_error(ogr_backend):
    with pytest.raises(ValueError, match="missing required field 'fi'"):
        Builder().basin(
            MemoryLayer([([(5, 5)], {"id": "A"})]),
            MemoryLayer([(rectangle(0, 10), {})]),
        )


def test_zero_length_reach_is_error():
    with pytest.raises(ValueError, match="non-zero-length"):
        Builder().reach(MemoryLayer([
            ([(0, 0), (0, 0)], {"id": "R", "t": 1, "s": 0.01}),
        ]))


@pytest.mark.parametrize("point", [
    (float("nan"), 0), (float("inf"), 0), ("invalid", 0), (0,),
])
def test_invalid_reach_coordinates_are_rejected_by_builder(point):
    with pytest.raises(ValueError, match="Reach feature 0.*coordinates"):
        Builder().reach(MemoryLayer([
            ([(0, 0), point, (10, 0)], {"id": "R", "t": 1, "s": 0.01}),
        ]))


def test_duplicate_catchment_ids_are_error(ogr_backend):
    with pytest.raises(ValueError, match="duplicate.*id"):
        Builder().basin(
            MemoryLayer([
                ([(5, 5)], {"id": "A", "fi": 0.0}),
                ([(25, 5)], {"id": "A", "fi": 0.0}),
            ]),
            MemoryLayer([(rectangle(0, 10), {}), (rectangle(20, 30), {})]),
        )
