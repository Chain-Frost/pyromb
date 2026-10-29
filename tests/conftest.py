import os
from collections import namedtuple

import pytest

from pyromb import VectorLayer


class Vector(VectorLayer):
    """Read the tracked fixtures using QGIS's bundled OGR."""

    def __init__(self, path: str) -> None:
        from osgeo import ogr

        self.dataset = ogr.Open(path)
        if self.dataset is None:
            raise ValueError("Could not open test fixture")
        self.features = list(self.dataset.GetLayer())

    def geometry(self, i: int) -> list[tuple[float, float]]:
        from osgeo import ogr

        geometry = self.features[i].GetGeometryRef()
        if geometry.GetGeometryType() == ogr.wkbPolygon:
            # Match QVectorLayer.vertices(): retain each ring's closing vertex.
            return [
                (point[0], point[1])
                for index in range(geometry.GetGeometryCount())
                for point in geometry.GetGeometryRef(index).GetPoints()
            ]
        elif geometry.GetGeometryType() not in (ogr.wkbPoint, ogr.wkbLineString):
            raise ValueError("Unsupported test fixture geometry")
        return [(p[0], p[1]) for p in geometry.GetPoints()]

    def record(self, i: int) -> dict[str, object]:
        return self.features[i].items()

    def __len__(self) -> int:
        return len(self.features)


@pytest.fixture
def vectors() -> tuple[Vector,...]:
    """
    Returns:
        namedtuple['basin','centroid','confluence','reach']: The vectors to build the catchment.
    """
    root = os.path.dirname(os.path.abspath(__file__))
    basin_vector = Vector(os.path.join(root,'./data', 'basins.shp'))
    centroid_vector = Vector(os.path.join(root, './data', 'centroids.shp'))
    confluence_vector = Vector(os.path.join(root, './data', 'confluences.shp'))
    reach_vector = Vector(os.path.join(root, './data', 'reaches.shp'))

    nt = namedtuple('vectors', ['basins', 'centroids', 'confluences', 'reaches'])

    return nt(basin_vector, centroid_vector, confluence_vector, reach_vector)
