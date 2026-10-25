"""Build catchment entities from the public VectorLayer interface."""

import math

from ...math import geometry
from ..attributes.basin import Basin
from ..attributes.confluence import Confluence
from ..attributes.reach import Reach, ReachType
from ..gis.vector_layer import VectorLayer


class Builder:
    """Build and validate the entities consumed by Catchment.

    A calling application (including the QGIS plugin) only needs to implement
    VectorLayer.geometry(), record(), and __len__().
    """

    @staticmethod
    def _record(layer: VectorLayer, index: int, fields: tuple[str, ...], kind: str):
        record = layer.record(index)
        for field in fields:
            try:
                value = record[field]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError(
                    f"{kind} feature {index} is missing required field {field!r}"
                ) from exc
            if value is None or value == "":
                raise ValueError(
                    f"{kind} feature {index} has an empty required field {field!r}"
                )
        return record

    @staticmethod
    def _point(layer: VectorLayer, index: int, kind: str) -> tuple[float, float]:
        coordinates = layer.geometry(index)
        if not coordinates or len(coordinates) != 1 or len(coordinates[0]) < 2:
            raise ValueError(f"{kind} feature {index} must have exactly one point")
        try:
            x, y = float(coordinates[0][0]), float(coordinates[0][1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{kind} feature {index} has invalid coordinates") from exc
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError(f"{kind} feature {index} has non-finite coordinates")
        return x, y

    def reach(self, reach: VectorLayer) -> list[Reach]:
        """Build reaches, rejecting missing attributes and degenerate lines."""
        reaches = []
        for i in range(len(reach)):
            record = self._record(reach, i, ("id", "t", "s"), "Reach")
            points = reach.geometry(i)
            if len(points) < 2 or all(point == points[0] for point in points[1:]):
                raise ValueError(f"Reach feature {i} requires a non-zero-length line")
            reaches.append(Reach(record["id"], points, ReachType(record["t"]), record["s"]))
        return reaches

    def basin(self, centroid: VectorLayer, basin: VectorLayer) -> list[Basin]:
        """Assign each centroid to its containing basin polygon, not the nearest centre.

        Every centroid must lie in exactly one polygon and each polygon must
        belong to exactly one centroid. Ambiguous or incomplete GIS inputs
        raise instead of silently writing wrong catchment areas.

        Polygon coordinates must use a projected CRS in metres. The current
        VectorLayer interface represents a single exterior ring; multipart
        polygons and holes need an extended geometry interface in a later PR.
        """
        if not len(centroid) or not len(basin):
            raise ValueError("Centroid and basin layers must both contain features")

        # The OGR geometries are created just once; the geometry backend remains
        # in pyromb.math.geometry rather than leaking into the calling app.
        polygons = []
        for i in range(len(basin)):
            vertices = basin.geometry(i)
            try:
                polygon = geometry.ogr_polygon(vertices)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Basin polygon feature {i}: {exc}") from exc
            polygons.append(polygon)

        basins = []
        assigned: set[int] = set()
        for i in range(len(centroid)):
            record = self._record(centroid, i, ("id", "fi"), "Centroid")
            point = self._point(centroid, i, "Centroid")
            matches = [
                j for j, polygon in enumerate(polygons)
                if geometry.contains(polygon, point)
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"Centroid {record['id']!r} at {point} must be inside exactly "
                    f"one basin polygon; matched {matches}"
                )

            polygon_index = matches[0]
            if polygon_index in assigned:
                raise ValueError(
                    f"Basin polygon {polygon_index} contains multiple centroids "
                    f"(including {record['id']!r})"
                )
            assigned.add(polygon_index)

            # Existing Pyromb units: projected coordinates in metres, area in km2.
            area = geometry.ogr_area(polygons[polygon_index]) / 1e6
            basins.append(Basin(record["id"], point[0], point[1], area, record["fi"]))

        unassigned = sorted(set(range(len(polygons))) - assigned)
        if unassigned:
            raise ValueError(f"Basin polygons without centroids: {unassigned}")
        return basins

    def confluence(self, confluence: VectorLayer) -> list[Confluence]:
        """Build confluences, checking their required attributes and point geometry."""
        confluences = []
        for i in range(len(confluence)):
            record = self._record(confluence, i, ("id", "out"), "Confluence")
            x, y = self._point(confluence, i, "Confluence")
            confluences.append(Confluence(record["id"], x, y, bool(record["out"])))
        return confluences
