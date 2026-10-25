"""Validate public fixtures through OGR and the upstream QGIS adapter.

Run using python-qgis.bat; arguments: source root, output JSON, adapter .py,
and optional directory in which to retain model output bytes for comparison.
Download the adapter from the pinned revision documented in the validation note.
This creates a standalone, headless QGIS application, leaving open projects alone.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / 'src'))
sys.path.insert(0, str(root / 'tests'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from qgis.core import QgsApplication, QgsVectorLayer, QgsFeature, QgsGeometry
import pyromb
from conftest import Vector

app = QgsApplication([], False)
app.initQgis()
spec = importlib.util.spec_from_file_location('upstream_adapter', sys.argv[3])
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

layers = {}
owners = []
for name in ('basins', 'centroids', 'confluences', 'reaches'):
    layer = QgsVectorLayer(str(root / 'tests/data' / (name + '.shp')), name, 'ogr')
    assert layer.isValid()
    owners.append(layer)
    layers[name] = adapter.QVectorLayer(layer)

result = {}
for backend in ('ogr', 'qgis'):
    sources = layers if backend == 'qgis' else {
        name: Vector(str(root / 'tests/data' / (name + '.shp'))) for name in layers
    }
    builder = pyromb.Builder()
    basins = builder.basin(sources['centroids'], sources['basins'])
    assert len({b.name for b in basins}) == len(basins) == len(sources['basins'])
    result[backend] = {'basins': [(b.name, b.area, b.fi) for b in basins], 'outputs': {}}
    for model in (pyromb.RORB, pyromb.URBS, pyromb.WBNM):
        catchment = pyromb.Catchment(builder.confluence(sources['confluences']), basins, builder.reach(sources['reaches']))
        catchment.connect()
        try:
            output = pyromb.Traveller(catchment).getVector(model())
        except AttributeError as exc:
            if model is not pyromb.WBNM or str(exc) != "'Basin' object has no attribute '_type'":
                raise
            result[backend]['outputs'][model.__name__] = {'error': str(exc)}
            continue
        assert output
        if len(sys.argv) > 4:
            destination = Path(sys.argv[4])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / f'{backend}-{model.__name__}.txt').write_bytes(output.encode())
        result[backend]['outputs'][model.__name__] = {'sha256': hashlib.sha256(output.encode()).hexdigest(), 'length': len(output)}

result['flattened_geometry'] = {}
for name, wkt in {
    'hole': 'POLYGON ((0 0,10 0,10 10,0 10,0 0),(2 2,2 8,8 8,8 2,2 2))',
    'multipart': 'MULTIPOLYGON (((0 0,10 0,10 10,0 10,0 0)),((20 0,30 0,30 10,20 10,20 0)))',
}.items():
    layer = QgsVectorLayer(('MultiPolygon' if name == 'multipart' else 'Polygon') + '?crs=EPSG:28350', name, 'memory')
    feature = QgsFeature()
    feature.setGeometry(QgsGeometry.fromWkt(wkt))
    assert layer.dataProvider().addFeatures([feature])[0]
    points = adapter.QVectorLayer(layer).geometry(0)
    try:
        polygon = pyromb.math.geometry.ogr_polygon(points)
        outcome = {'accepted_area': polygon.GetArea()}
    except (AttributeError, ValueError) as exc:
        outcome = {'error': str(exc)}
    result['flattened_geometry'][name] = {'native_area': feature.geometry().area(), 'vertices': len(points), **outcome}

assert result['ogr'] == result['qgis'], 'OGR and QVectorLayer results differ'
Path(sys.argv[2]).write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
