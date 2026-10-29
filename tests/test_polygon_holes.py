"""Preserve closed interior rings supplied by the unchanged flat adapter."""

import copy

import pytest
from test_basin_containment import MemoryLayer, rectangle
from test_qgis_attributes import layer_factory as layer_factory
from test_qgis_attributes import qgis_adapter as qgis_adapter

from pyromb import Builder
from pyromb.math import geometry


@pytest.mark.parametrize("reverse", [False, True])
def test_hole_warns_and_subtracts_area_without_mutation(reverse):
    outer = rectangle(0, 10)
    hole = [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
    if reverse:
        hole.reverse()
    points = outer + hole
    before = copy.deepcopy(points)
    with pytest.warns(UserWarning, match=r"Basin polygon feature 0.*1 interior ring.*4.*excluded"):
        basins = Builder().basin(
            MemoryLayer([([(8, 5)], {"id": "A", "fi": 0.0})]),
            MemoryLayer([(points, {})]),
        )
    assert basins[0].area == pytest.approx(96 / 1e6)
    assert points == before


def test_centroid_in_hole_is_unmatched():
    points = rectangle(0, 10) + [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
    with pytest.warns(UserWarning, match="interior ring"):
        with pytest.raises(ValueError, match="exactly one basin"):
            Builder().basin(
                MemoryLayer([([(3, 3)], {"id": "in-hole", "fi": 0.0})]),
                MemoryLayer([(points, {})]),
            )


def test_multiple_holes_are_preserved():
    points = rectangle(0, 10)
    points += [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)]
    points += [(5, 5), (7, 5), (7, 7), (5, 7), (5, 5)]
    with pytest.warns(UserWarning, match="2 interior rings"):
        polygon = geometry.ogr_polygon(points)
    assert geometry.ogr_area(polygon) == pytest.approx(95)
    assert geometry.contains(polygon, (9, 9))
    assert not geometry.contains(polygon, (1.5, 1.5))
    assert not geometry.contains(polygon, (6, 6))


@pytest.mark.parametrize("extra", [
    [(20, 2), (22, 2), (22, 4), (20, 4), (20, 2)],
    [(2, 2), (4, 4), (2, 4), (4, 2), (2, 2)],
    [(2, 2), (4, 2), (4, 4)],
    [(2, 2), (2, 2)],
    [(2, 2), (float("nan"), 2), (4, 4), (2, 2)],
])
def test_malformed_or_external_extra_rings_still_fail(extra):
    with pytest.raises(ValueError):
        geometry.ogr_polygon(rectangle(0, 10) + extra)


def test_nested_holes_are_not_silently_reinterpreted():
    points = rectangle(0, 10)
    points += [(1, 1), (8, 1), (8, 8), (1, 8), (1, 1)]
    points += [(2, 2), (3, 2), (3, 3), (2, 3), (2, 2)]
    with pytest.raises(ValueError, match="invalid"):
        geometry.ogr_polygon(points)


def test_qgis_hole_keeps_native_area_and_geometry(qgis_adapter):
    core, adapter = qgis_adapter
    source = core.QgsVectorLayer("Polygon?crs=EPSG:28350", "holed", "memory")
    feature = core.QgsFeature()
    feature.setGeometry(core.QgsGeometry.fromWkt(
        "POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))"
    ))
    assert source.dataProvider().addFeatures([feature])[0]
    original = next(source.getFeatures()).geometry().asWkb()
    with pytest.warns(UserWarning, match="36.*excluded"):
        polygon = geometry.ogr_polygon(adapter(source).geometry(0))
    assert geometry.ogr_area(polygon) == feature.geometry().area() == 64
    assert not geometry.contains(polygon, (5, 5))
    assert next(source.getFeatures()).geometry().asWkb() == original


def test_builder_hole_through_shapefile_adapters(layer_factory):
    basin = layer_factory(
        "POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))",
        [("id", "OFTString")], [{"id": "polygon"}],
    )
    centroid = layer_factory(
        "POINT (1 1)", [("id", "OFTString"), ("fi", "OFTReal")],
        [{"id": "A", "fi": 0.2}],
    )
    before = copy.deepcopy(basin.geometry(0))
    with pytest.warns(UserWarning, match=r"feature 0.*36.*excluded"):
        result = Builder().basin(centroid, basin)
    assert result[0].name == "A"
    assert result[0].area == pytest.approx(64 / 1e6)
    assert result[0].fi == 0.2
    assert basin.geometry(0) == before
