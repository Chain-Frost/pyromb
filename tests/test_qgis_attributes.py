"""Exercise real QgsFeature values through the pinned upstream QVectorLayer.

Set PYROMB_QGIS_ADAPTER to the QGIS plugin's original QVectorLayer file.
The same cases also run through an OGR shapefile, including field coercion/nulls.
"""

import importlib.util
import os
from pathlib import Path

import pytest
from conftest import Vector

from pyromb import RORB, URBS, Builder, Catchment, Traveller


@pytest.fixture(scope="session")
def qgis_adapter():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    core = pytest.importorskip("qgis.core")
    adapter_path = os.environ.get("PYROMB_QGIS_ADAPTER")
    if not adapter_path:
        pytest.skip("Set PYROMB_QGIS_ADAPTER to test the pinned upstream adapter")
    app = core.QgsApplication.instance()
    owns_app = app is None
    if owns_app:
        app = core.QgsApplication([], False)
        app.initQgis()
    spec = importlib.util.spec_from_file_location("upstream_adapter", adapter_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield core, module.QVectorLayer
    if owns_app:
        app.exitQgis()


@pytest.fixture(params=["ogr", "qgis"])
def layer_factory(request, tmp_path):
    from osgeo import ogr

    def make(geometry, fields, records):
        # Both adapters read the very same shapefile storage representations.
        path = tmp_path / f"layer-{len(list(tmp_path.glob('*.shp')))}.shp"
        dataset = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(str(path))
        layer = dataset.CreateLayer("layer", geom_type=ogr.wkbUnknown)
        for name, kind in fields:
            layer.CreateField(ogr.FieldDefn(name, getattr(ogr, kind)))
        for values in records:
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(ogr.CreateGeometryFromWkt(geometry))
            for name, value in values.items():
                if value is not None:
                    feature.SetField(name, value)
            assert layer.CreateFeature(feature) == 0
        dataset = None
        if request.param == "ogr":
            return Vector(str(path))
        core, adapter = request.getfixturevalue("qgis_adapter")
        source = core.QgsVectorLayer(str(path), "test", "ogr")
        assert source.isValid()
        return adapter(source)

    return make


@pytest.mark.parametrize("field,value,error", [
    ("t", 1.5, "integer"), ("t", 7, "unsupported"), ("t", None, "empty"),
    ("s", -0.01, "negative"), ("s", None, "empty"),
    ("s", float("inf"), "finite"), ("s", float("nan"), "finite"),
    ("id", "   ", "empty"), ("id", None, "empty"),
])
def test_reach_fields(layer_factory, field, value, error):
    values = {"id": "R1", "t": 1, "s": 0.001, field: value}
    layer = layer_factory("LINESTRING (0 0,10 0)", [
        ("id", "OFTString"), ("t", "OFTReal"), ("s", "OFTReal"),
    ], [values])
    with pytest.raises(ValueError, match=error):
        Builder().reach(layer)


def test_missing_field(layer_factory):
    layer = layer_factory("POINT (0 0)", [("id", "OFTString")], [{"id": "OUT"}])
    with pytest.raises(ValueError, match="missing required field 'out'"):
        Builder().confluence(layer)


@pytest.mark.parametrize("values,error", [
    ([0, 1], None), ([0, 0], "exactly one"), ([1, 1], "exactly one"),
    ([2], "0 or 1"), ([0.5], "0 or 1"), ([None], "empty"),
])
def test_outlets(layer_factory, values, error):
    layer = layer_factory("POINT (0 0)", [("id", "OFTString"), ("out", "OFTReal")], [
        {"id": f"C{i}", "out": value} for i, value in enumerate(values)
    ])
    if error:
        with pytest.raises(ValueError, match=error):
            Builder().confluence(layer)
    else:
        assert sum(c.isOut for c in Builder().confluence(layer)) == 1


@pytest.mark.parametrize("fraction", [-0.1, 1.1, None, float("inf"), float("nan"), 0, 0.5, 1])
def test_impervious_fraction(layer_factory, fraction):
    centroid = layer_factory("POINT (5 5)", [("id", "OFTString"), ("fi", "OFTReal")], [
        {"id": "B1", "fi": fraction},
    ])
    polygon = layer_factory("POLYGON ((0 0,10 0,10 10,0 10,0 0))", [], [{}])
    if fraction is None or not 0 <= fraction <= 1:
        with pytest.raises(ValueError, match="fi"):
            Builder().basin(centroid, polygon)
    else:
        assert Builder().basin(centroid, polygon)[0].fi == fraction


def test_global_collision(layer_factory):
    reaches = layer_factory("LINESTRING (5 5,10 0)", [
        ("id", "OFTString"), ("t", "OFTInteger64"), ("s", "OFTReal"),
    ], [{"id": "OUT", "t": 1, "s": 0.001}])
    confluences = layer_factory("POINT (10 0)", [("id", "OFTString"), ("out", "OFTInteger")], [
        {"id": "OUT", "out": 1},
    ])
    with pytest.raises(ValueError, match="Duplicate model identifier"):
        Catchment(Builder().confluence(confluences), [], Builder().reach(reaches))


@pytest.mark.parametrize("model,expected", [
    (RORB, "67ae955b515a0594298fa1b0e48005d4d12db520e0a7dc582f37e6e06d6ad815"),
    (URBS, "f162ca1ee5f1b1cffa3eee30f910e9632d4a3d783fe0411cbf579428db5ad025"),
])
def test_qgis_public_output(qgis_adapter, model, expected):
    import hashlib

    core, adapter = qgis_adapter
    sources = {}
    for name in ("centroids", "basins", "reaches", "confluences"):
        source = core.QgsVectorLayer(str(Path(__file__).parent / "data" / f"{name}.shp"), name, "ogr")
        assert source.isValid()
        sources[name] = adapter(source)
    builder = Builder()
    catchment = Catchment(
        builder.confluence(sources["confluences"]),
        builder.basin(sources["centroids"], sources["basins"]),
        builder.reach(sources["reaches"]),
    )
    catchment.connect()
    output = Traveller(catchment).getVector(model())
    assert hashlib.sha256(output.encode()).hexdigest() == expected


def test_adapter_coordinates_do_not_identify_source_type_or_crs(qgis_adapter):
    core, adapter = qgis_adapter
    ring = "(0 0,10 0,10 10,0 10,0 0)"
    sources = []
    for kind, crs, wkt in [
        ("Polygon", "EPSG:28350", f"POLYGON ({ring})"),
        ("LineString", "EPSG:28350", f"LINESTRING {ring}"),
        ("Polygon", "EPSG:4326", f"POLYGON ({ring})"),
    ]:
        source = core.QgsVectorLayer(f"{kind}?crs={crs}", "source", "memory")
        feature = core.QgsFeature()
        feature.setGeometry(core.QgsGeometry.fromWkt(wkt))
        assert source.dataProvider().addFeatures([feature])[0]
        sources.append(source)
    coordinates = [adapter(source).geometry(0) for source in sources]
    assert coordinates[0] == coordinates[1] == coordinates[2]
    assert sources[0].wkbType() != sources[1].wkbType()
    assert sources[0].crs() != sources[2].crs()


@pytest.mark.parametrize("kind,wkt,area", [
    ("Polygon", "POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))", 64),
    ("MultiPolygon", "MULTIPOLYGON (((0 0,10 0,10 10,0 10,0 0)),((20 0,30 0,30 10,20 10,20 0)))", 200),
])
def test_flattened_hole_and_multipart_examples_are_rejected(qgis_adapter, kind, wkt, area):
    from pyromb.math import geometry

    core, adapter = qgis_adapter
    source = core.QgsVectorLayer(f"{kind}?crs=EPSG:28350", "source", "memory")
    feature = core.QgsFeature()
    feature.setGeometry(core.QgsGeometry.fromWkt(wkt))
    assert feature.geometry().area() == area
    assert source.dataProvider().addFeatures([feature])[0]
    # Additional flattened rings/parts must not produce an incorrect basin area.
    with pytest.raises(ValueError, match=r"rings.*holes.*QGIS"):
        geometry.ogr_polygon(adapter(source).geometry(0))
