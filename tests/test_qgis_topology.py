"""Validate topology using real projected shapefiles through OGR and QGIS."""

import pytest
from conftest import Vector
from test_qgis_attributes import qgis_adapter as qgis_adapter

from pyromb import Builder, Catchment


@pytest.fixture(params=["ogr", "qgis"])
def topology_layers(request, tmp_path):
    from osgeo import ogr, osr

    def make(name, geometry_type, fields, features):
        path = tmp_path / f"{name}.shp"
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(28350)
        dataset = ogr.GetDriverByName("ESRI Shapefile").CreateDataSource(str(path))
        layer = dataset.CreateLayer(name, srs=reference, geom_type=geometry_type)
        for field, field_type in fields:
            layer.CreateField(ogr.FieldDefn(field, field_type))
        for wkt, values in features:
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetGeometry(ogr.CreateGeometryFromWkt(wkt))
            for field, value in values.items():
                feature.SetField(field, value)
            assert layer.CreateFeature(feature) == 0
        dataset = None
        if request.param == "ogr":
            return Vector(str(path))
        core, adapter = request.getfixturevalue("qgis_adapter")
        source = core.QgsVectorLayer(str(path), name, "ogr")
        assert source.isValid() and source.crs().authid() == "EPSG:28350"
        assert source.crs().mapUnits() == core.Qgis.DistanceUnit.Meters
        return adapter(source)

    def build(nodes, edges):
        builder = Builder()
        confluences = make("nodes", ogr.wkbPoint, [("id", ogr.OFTString), ("out", ogr.OFTInteger)], [
            (f"POINT ({x} {y})", {"id": name, "out": outlet}) for name, x, y, outlet in nodes
        ])
        reaches = make("reaches", ogr.wkbLineString, [
            ("id", ogr.OFTString), ("t", ogr.OFTInteger64), ("s", ogr.OFTReal),
        ], [(wkt, {"id": f"R{i}", "t": 1, "s": 0.001}) for i, wkt in enumerate(edges)])
        return Catchment(builder.confluence(confluences), [], builder.reach(reaches))

    return build


@pytest.mark.parametrize("edges,tolerance,error", [
    (["LINESTRING (0 0,10 0)"], 0, None),
    (["LINESTRING (10 0,0 0)"], 0, None),
    (["LINESTRING (0 0,10.001 0)"], 1e-6, "R0.*end.*not snapped.*OUT"),
    (["LINESTRING (0 0,10.001 0)"], 0.01, None),
    (["LINESTRING (0.0000001 0,10 0)"], 0, "R0.*start.*not snapped.*A"),
    (["LINESTRING (0.0000001 0,10 0)"], 1e-6, None),
    (["LINESTRING (0 0,0 5,0 0)"], 1e-6, "R0.*A.*itself"),
    (["LINESTRING (0 0,10 0)", "LINESTRING (10 0,0 0)"], 1e-6, "cycle or parallel.*R0.*R1"),
])
def test_projected_endpoints(topology_layers, edges, tolerance, error):
    model = topology_layers([("OUT", 10, 0, 1), ("A", 0, 0, 0)], edges)
    before = [[point.coordinates() for point in edge.toVector()] for edge in model._edges]
    if error:
        with pytest.raises(ValueError, match=error):
            model.connect(tolerance=tolerance)
    else:
        ds, us = model.connect(tolerance=tolerance)
        assert ds.tolist() == [[-1], [0]]
        assert us.tolist() == [[1], [-1]]
    assert [[point.coordinates() for point in edge.toVector()] for edge in model._edges] == before


@pytest.mark.parametrize("nodes,edges,tolerance,error", [
    ([("OUT", 10, 0, 1), ("A", 0, 0, 0), ("B", 0, 0, 0)],
     ["LINESTRING (0 0,10 0)"], 0, "R0.*start.*ambiguous.*A.*B"),
    ([("OUT", 10, 0, 1), ("A", 0, 0, 0), ("B", 0, 2, 0)],
     ["LINESTRING (0 1,10 0)"], 1, "R0.*start.*ambiguous.*A.*1.*B.*1"),
    ([("OUT", 10, 0, 1), ("A", 0, 0, 0), ("B", 20, 0, 0)],
     ["LINESTRING (0 0,10 0)"], 0, "Disconnected.*B"),
    ([("OUT", 10, 0, 1), ("A", 0, 0, 0), ("B", 20, 0, 0), ("C", 30, 0, 0)],
     ["LINESTRING (0 0,10 0)", "LINESTRING (20 0,30 0)"], 0, "Disconnected.*B.*C"),
    ([("OUT", 10, 0, 1), ("A", 0, 0, 0), ("B", 5, 10, 0)],
     ["LINESTRING (0 0,10 0)", "LINESTRING (0 0,5 10)", "LINESTRING (5 10,10 0)"],
     0, "cycle or parallel.*R0.*R1.*R2"),
    ([("OUT", 10, 0, 0), ("A", 0, 0, 0)], ["LINESTRING (0 0,10 0)"], 0, "exactly one outlet"),
    ([("OUT", 10, 0, 1), ("A", 0, 0, 1)], ["LINESTRING (0 0,10 0)"], 0, "exactly one outlet"),
    ([("OUT", 10, 0, 1), ("OUT", 0, 0, 0)], ["LINESTRING (0 0,10 0)"], 0, "Duplicate model identifier"),
])
def test_projected_invalid_network(topology_layers, nodes, edges, tolerance, error):
    with pytest.raises(ValueError, match=error):
        topology_layers(nodes, edges).connect(tolerance=tolerance)
