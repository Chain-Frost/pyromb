"""Reject unsupported basin rings without altering the input geometry."""

import copy

import pytest
from test_basin_containment import MemoryLayer, rectangle
from test_qgis_attributes import layer_factory as layer_factory
from test_qgis_attributes import qgis_adapter as qgis_adapter

from pyromb import Builder
from pyromb.math import geometry


@pytest.mark.parametrize(
    "vertices",
    [
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        [(0, 0), (0, 0), (10, 0), (10, 10), (0, 10), (0, 0)],
        [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0), (0, 0)],
        [(0, 0), (0, 0), (10, 0), (10, 10), (0, 10), (0, 0), (0, 0)],
    ],
)
def test_single_ring_accepts_duplicate_opening_and_closing_vertices(vertices):
    before = copy.deepcopy(vertices)
    polygon = geometry.ogr_polygon(vertices)
    assert geometry.ogr_area(polygon) == pytest.approx(100)
    assert vertices == before


@pytest.mark.parametrize("extra", [
    [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],
    [(2, 2), (2, 4), (4, 4), (4, 2), (2, 2)],
    [(20, 2), (22, 2), (22, 4), (20, 4), (20, 2)],
    [(2, 2), (4, 2), (4, 4)],
    [(2, 2), (2, 2)],
])
def test_additional_ring_or_part_raises_valueerror_without_mutating_input(extra):
    vertices = rectangle(0, 10) + extra
    before = copy.deepcopy(vertices)
    with pytest.raises(ValueError, match=r"rings.*holes.*QGIS"):
        geometry.ogr_polygon(vertices)
    assert vertices == before


def test_builder_identifies_unsupported_basin_feature():
    vertices = rectangle(0, 10) + [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)]
    with pytest.raises(ValueError, match=r"Basin polygon feature 0:.*holes.*QGIS"):
        Builder().basin(
            MemoryLayer([([(8, 5)], {"id": "A", "fi": 0.0})]),
            MemoryLayer([(vertices, {})]),
        )


def test_genuine_qgis_adapter_rejects_hole_without_modifying_geometry(qgis_adapter):
    core, adapter = qgis_adapter
    source = core.QgsVectorLayer("Polygon?crs=EPSG:28350", "holed", "memory")
    feature = core.QgsFeature()
    feature.setGeometry(core.QgsGeometry.fromWkt(
        "POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))"
    ))
    assert source.dataProvider().addFeatures([feature])[0]
    original = next(source.getFeatures()).geometry().asWkb()
    with pytest.raises(ValueError, match=r"rings.*holes.*QGIS"):
        geometry.ogr_polygon(adapter(source).geometry(0))
    assert next(source.getFeatures()).geometry().asWkb() == original


def test_shapefile_adapter_reports_unsupported_basin_feature(layer_factory):
    basin = layer_factory(
        "POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))",
        [("id", "OFTString")], [{"id": "polygon"}],
    )
    centroid = layer_factory(
        "POINT (1 1)", [("id", "OFTString"), ("fi", "OFTReal")],
        [{"id": "A", "fi": 0.2}],
    )
    before = copy.deepcopy(basin.geometry(0))
    with pytest.raises(ValueError, match=r"Basin polygon feature 0:.*holes.*QGIS"):
        Builder().basin(centroid, basin)
    assert basin.geometry(0) == before
