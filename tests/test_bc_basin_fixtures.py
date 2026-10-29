"""Regression coverage for upstream PR #16's original and corrected basins."""

import hashlib
import json
import math
import warnings
from pathlib import Path

import pytest
from conftest import Vector
from test_qgis_attributes import qgis_adapter as qgis_adapter

from pyromb import Builder

ogr = pytest.importorskip("osgeo.ogr")
DATA = Path(__file__).parent / "data" / "bc_basins"
EXPECTED = json.loads((DATA / "expected_areas.json").read_text())
# Absolute tolerances: 0.0001 m² per polygon, 0.001 m² for catchment totals.
AREA_TOL = EXPECTED["area_absolute_tolerance_m2"]
TOTAL_TOL = EXPECTED["total_absolute_tolerance_m2"]


class GeoPackageVector(Vector):
    """Use the existing OGR test adapter with an explicitly named layer."""

    def __init__(self, path, name):
        self.dataset = ogr.Open(str(path))
        assert self.dataset is not None
        layer = self.dataset.GetLayerByName(name)
        assert layer is not None
        self.features = list(layer)


def native_snapshot(path):
    """Read all native fields, coordinates and CRS without using Pyromb."""
    dataset = ogr.Open(str(path))
    assert dataset is not None
    result = {}
    for layer in dataset:
        result[layer.GetName()] = {
            "crs": layer.GetSpatialRef().ExportToWkt(),
            "type": layer.GetGeomType(),
            "fields": [(field.GetName(), field.GetType()) for field in layer.schema],
            "features": [
                (feature.GetFID(), feature.items(), bytes(feature.GetGeometryRef().ExportToWkb()))
                for feature in layer
            ],
        }
    return result


@pytest.fixture(params=["ogr", "qgis"])
def bc_layers(request):
    """Load real adapters and check disk and in-memory inputs after each test."""
    loaded = []

    def load(variant):
        path = DATA / f"{variant}.gpkg"
        disk_hash = hashlib.sha256(path.read_bytes()).digest()
        native = native_snapshot(path)
        owners = []
        layers = {}
        for name in ("basins", "centroids"):
            if request.param == "ogr":
                layer = GeoPackageVector(path, name)
            else:
                core, adapter = request.getfixturevalue("qgis_adapter")
                source = core.QgsVectorLayer(f"{path}|layername={name}", name, "ogr")
                assert source.isValid()
                assert source.crs().authid() == EXPECTED["crs"]
                owners.append(source)
                layer = adapter(source)
            layers[name] = layer

        def adapter_snapshot():
            return {
                name: [
                    (tuple(layer.geometry(i)), tuple(layer.record(i)[field] for field, _ in native[name]["fields"]))
                    for i in range(len(layer))
                ]
                for name, layer in layers.items()
            }

        loaded.append((path, disk_hash, native, adapter_snapshot, adapter_snapshot(), owners))
        return layers

    yield load
    for path, disk_hash, native, snapshot, before, owners in loaded:
        assert snapshot() == before, "Builder mutated adapter geometry or attributes"
        assert native_snapshot(path) == native, "Builder mutated native fixture data"
        assert hashlib.sha256(path.read_bytes()).digest() == disk_hash, "Fixture file was modified"


def test_original_hole_has_actionable_validation_error(bc_layers):
    layers = bc_layers("original")
    with pytest.raises(ValueError, match=r"Basin polygon feature 6:.*rings.*holes.*QGIS"):
        Builder().basin(layers["centroids"], layers["basins"])


def test_corrected_assignments_and_areas_without_warnings(bc_layers):
    layers = bc_layers("corrected")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        basins = Builder().basin(layers["centroids"], layers["basins"])
    assert not caught, [str(warning.message) for warning in caught]
    reference = {row["centroid_id"]: row for row in EXPECTED["datasets"]["corrected"]["basins"]}
    assert len(basins) == len(reference) == 15
    assert len({basin.name for basin in basins}) == 15
    assert {basin.name for basin in basins} == set(reference)
    records = {layers["centroids"].record(i)["id"]: layers["centroids"].record(i) for i in range(15)}
    for basin in basins:
        row = reference[basin.name]
        assert basin.coordinates() == tuple(row["centroid_xy"])
        assert basin.fi == records[basin.name]["fi"]
        assert basin.area == pytest.approx(row["area_km2"], rel=0, abs=AREA_TOL / 1e6)
    assert math.fsum(basin.area for basin in basins) == pytest.approx(
        EXPECTED["datasets"]["corrected"]["total_area_km2"], rel=0, abs=TOTAL_TOL / 1e6,
    )


@pytest.mark.parametrize("variant", ["original", "corrected"])
def test_independent_native_areas_and_containment(variant):
    dataset = ogr.Open(str(DATA / f"{variant}.gpkg"))
    assert dataset.GetLayerCount() == 2
    layer = dataset.GetLayerByName("basins")
    centroids = list(dataset.GetLayerByName("centroids"))
    reference = EXPECTED["datasets"][variant]
    assert layer.GetFeatureCount() == len(centroids) == len(reference["basins"]) == 15
    assert layer.GetSpatialRef().GetAuthorityCode(None) == "28350"
    assert dataset.GetLayerByName("centroids").GetSpatialRef().IsSame(layer.GetSpatialRef())
    assert layer.GetSpatialRef().IsProjected()
    assert layer.GetSpatialRef().GetLinearUnits() == 1
    assert all(c.GetGeometryRef().IsValid() and c.GetGeometryRef().GetGeometryName() == "POINT" for c in centroids)
    areas = []
    assigned = set()
    for index, (feature, row) in enumerate(zip(layer, reference["basins"])):
        polygon = feature.GetGeometryRef()
        assert polygon.IsValid() and polygon.GetGeometryName() == "POLYGON"
        assert polygon.GetGeometryCount() == 1 + row["interior_rings"]
        assert feature.GetFID() == row["source_fid"]
        assert index == row["feature_index"]
        assert feature.GetField("id") == row["basin_id"]
        # Native OGR retains the real rings: no Pyromb geometry function is used.
        matches = [centroid for centroid in centroids if polygon.Contains(centroid.GetGeometryRef())]
        assert len(matches) == 1
        assert matches[0].GetField("id") == row["centroid_id"]
        assert list(matches[0].GetGeometryRef().GetPoint_2D()) == row["centroid_xy"]
        assigned.add(matches[0].GetField("id"))
        area = polygon.GetArea()
        assert area == pytest.approx(row["area_m2"], rel=0, abs=AREA_TOL)
        assert area / 1e6 == pytest.approx(row["area_km2"], rel=0, abs=AREA_TOL / 1e6)
        areas.append(area)
    assert len(assigned) == 15
    assert math.fsum(areas) == pytest.approx(reference["total_area_m2"], rel=0, abs=TOTAL_TOL)
    assert math.fsum(row["area_m2"] for row in reference["basins"]) == pytest.approx(
        reference["total_area_m2"], rel=0, abs=TOTAL_TOL,
    )
    assert math.fsum(row["area_km2"] for row in reference["basins"]) == pytest.approx(
        reference["total_area_km2"], rel=0, abs=TOTAL_TOL / 1e6,
    )


def test_only_feature_6_interior_ring_was_removed():
    original = native_snapshot(DATA / "original.gpkg")
    corrected = native_snapshot(DATA / "corrected.gpkg")
    assert original["centroids"] == corrected["centroids"]
    for key in ("crs", "type", "fields"):
        assert original["basins"][key] == corrected["basins"][key]
    changed = []
    for index, (before, after) in enumerate(zip(original["basins"]["features"], corrected["basins"]["features"])):
        assert before[:2] == after[:2], "Feature IDs and every attribute must be unchanged"
        if before[2] != after[2]:
            changed.append(index)
            old = ogr.CreateGeometryFromWkb(before[2])
            new = ogr.CreateGeometryFromWkb(after[2])
            assert old.GetGeometryCount() == 2 and new.GetGeometryCount() == 1
            # Exact exterior WKB, not merely equal areas or topological equality.
            assert old.GetGeometryRef(0).ExportToWkb() == new.GetGeometryRef(0).ExportToWkb()
            hole = ogr.Geometry(ogr.wkbPolygon)
            hole.AddGeometry(old.GetGeometryRef(1))
            # Overlay can reverse ring winding; normalized WKB retains exact coordinates.
            assert new.Difference(old).Normalize().ExportToWkb() == hole.Normalize().ExportToWkb()
            assert hole.GetArea() == pytest.approx(EXPECTED["removed_hole_area_m2"], rel=0, abs=AREA_TOL)
    assert changed == [6]
    old_ref = EXPECTED["datasets"]["original"]
    new_ref = EXPECTED["datasets"]["corrected"]
    assert old_ref["total_area_km2"] == pytest.approx(1630.4140663031646, rel=0, abs=TOTAL_TOL / 1e6)
    for index, (before, after) in enumerate(zip(old_ref["basins"], new_ref["basins"])):
        delta = EXPECTED["removed_hole_area_m2"] if index == 6 else 0
        assert after["area_m2"] - before["area_m2"] == pytest.approx(delta, rel=0, abs=AREA_TOL)
    assert new_ref["total_area_m2"] - old_ref["total_area_m2"] == pytest.approx(
        EXPECTED["removed_hole_area_m2"], rel=0, abs=TOTAL_TOL,
    )
