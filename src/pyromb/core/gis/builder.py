"""Build catchment entities from the public VectorLayer interface."""

import math
from typing import Protocol, SupportsFloat, cast

from ...math import geometry
from ..attributes.basin import Basin
from ..attributes.confluence import Confluence
from ..attributes.reach import Reach, ReachType
from ..gis.vector_layer import VectorLayer


class _Record(Protocol):
    """The field access shared by dictionaries and QGIS feature records."""

    def __getitem__(self, key: str, /) -> object: ...


class Builder:
    """Build and validate the entities consumed by Catchment.

    A calling application (including the QGIS plugin) only needs to implement
    VectorLayer.geometry(), record(), and __len__().
    """

    @staticmethod
    def _record(layer: VectorLayer, index: int, fields: tuple[str, ...], kind: str) -> _Record:
        record: _Record = layer.record(index)
        for field in fields:
            try:
                value = record[field]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError(
                    f"{kind} feature {index} is missing required field {field!r}"
                ) from exc
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(
                    f"{kind} feature {index} has an empty required field {field!r}"
                )
        return record

    @staticmethod
    def _real(value: object, kind: str, index: int, field: str) -> float:
        """Check numeric model attributes."""
        if isinstance(value, bool):
            raise ValueError(f"{kind} feature {index}: {field!r} must be numeric")
        try:
            # Conversion is deliberately delegated to float at this data boundary.
            result = float(cast(str | SupportsFloat, value))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{kind} feature {index}: {field!r} must be numeric") from exc
        if not math.isfinite(result):
            raise ValueError(f"{kind} feature {index}: {field!r} must be finite")
        return result

    @staticmethod
    def _binary(value: object, kind: str, index: int, field: str) -> bool:
        """Accept boolean/integer 0 or 1, never an arbitrary truthy value."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str) or value not in (0, 1):
            raise ValueError(f"{kind} feature {index}: {field!r} must be 0 or 1")
        return bool(value)

    @staticmethod
    def _reach_type(value: object, index: int) -> ReachType:
        number = Builder._real(value, "Reach", index, "t")
        if not number.is_integer():
            raise ValueError(f"Reach feature {index}: 't' must be an integer")
        try:
            return ReachType(int(number))
        except ValueError as exc:
            raise ValueError(
                f"Reach feature {index}: unsupported reach type {number:g}"
            ) from exc

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
            try:
                geometry.validate_line(points)
            except ValueError as exc:
                raise ValueError(f"Reach feature {i}: {exc}") from exc
            kind = self._reach_type(record["t"], i)
            slope = self._real(record["s"], "Reach", i, "s")
            if slope < 0:
                raise ValueError(f"Reach feature {i}: 's' must not be negative")
            reaches.append(Reach(cast(str, record["id"]), points, kind, slope))
        return reaches

    def basin(self, centroid: VectorLayer, basin: VectorLayer) -> list[Basin]:
        """Assign each centroid to its containing basin polygon, not the nearest centre.

        Every centroid must lie in exactly one polygon and each polygon must
        belong to exactly one centroid. Ambiguous or incomplete GIS inputs
        raise instead of silently writing wrong catchment areas.

        Polygon coordinates must use a projected CRS in metres. The current
        VectorLayer interface supplies flattened XY coordinates. Polygons
        with interior rings (holes) or multiple parts are not supported and
        must be corrected in QGIS before building. Source geometry type and
        CRS are not exposed; callers must verify these properties.
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

        basins: list[Basin] = []
        assigned: set[int] = set()
        identifiers: set[object] = set()
        for i in range(len(centroid)):
            record = self._record(centroid, i, ("id", "fi"), "Centroid")
            if record["id"] in identifiers:
                raise ValueError(
                    f"Centroid feature {i} has duplicate catchment id {record['id']!r}"
                )
            identifiers.add(record["id"])
            impervious = self._real(record["fi"], "Centroid", i, "fi")
            if not 0 <= impervious <= 1:
                raise ValueError(
                    f"Centroid feature {i}: 'fi' must be between 0 and 1"
                )
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
            basins.append(Basin(cast(str, record["id"]), point[0], point[1], area, impervious))

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
            outlet = self._binary(record["out"], "Confluence", i, "out")
            confluences.append(Confluence(cast(str, record["id"]), x, y, outlet))
        outlet_count = sum(item.isOut for item in confluences)
        if outlet_count != 1:
            raise ValueError(
                f"Confluences must have exactly one outlet ('out'=1); found {outlet_count}"
            )
        return confluences
