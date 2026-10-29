"""Geometry calculations and the OGR boundary used by catchment construction."""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING

from ..core.geometry.point import Point

if TYPE_CHECKING:
    from osgeo import ogr  # type: ignore[import-untyped]  # QGIS bundles GDAL without typing metadata.


def length(vertices: list[Point]) -> float:
    """Calculate the cartesian length of a vector of co-ordinates.

    Parameters
    ----------
    vertices : list
        The list of co-ordinates to calculate the length.

    Returns:
    -------
    float
        The vector length.
    """
    length: float = 0
    for i in range(len(vertices) - 1):
        length += math.sqrt( \
        math.pow((vertices[i+1].coordinates()[0] - vertices[i].coordinates()[0]), 2) + \
        math.pow((vertices[i+1].coordinates()[1] - vertices[i].coordinates()[1]), 2)
        )
    return length

# Shoelace algorithm
def polygon_area(vertices: list[Point]) -> float:
    """Calculate the cartesian area of a polygon.

    Parameters
    ----------
    vertices : list
        A list of points representing the polygon.

    Returns:
    -------
    float
        The polygon area.
    """
    psum: float = 0
    nsum: float = 0
    for i in range(len(vertices)):
        sindex = (i + 1) % len(vertices)
        prod = vertices[i].coordinates()[0] * vertices[sindex].coordinates()[1]
        psum += prod

    for i in range(len(vertices)):
        sindex = (i + 1) % len(vertices)
        prod = vertices[sindex].coordinates()[0] * vertices[i].coordinates()[1]
        nsum += prod

    return abs(1/2*(psum - nsum))

def polygon_centroid(vertices: list[Point]) -> Point:
    """Calculate the centroid of a polygon.

    Parameters
    ----------
    vertices : list
        A list of points representing the polygon.

    Returns:
    -------
    Point
        The centroid.
    """
    sumx: float = 0
    sumy: float = 0
    suma: float = 0
    for i in range(len(vertices) - 1):
        p = [vertices[i].coordinates(), vertices[i+1].coordinates()]
        sumx += (p[0][0] + p[1][0]) * (p[0][0] * p[1][1] - p[1][0] * p[0][1])
        sumy += (p[0][1] + p[1][1]) * (p[0][0] * p[1][1] - p[1][0] * p[0][1])
        suma += p[0][0] * p[1][1] - p[1][0] * p[0][1]

    A = 0.5 * suma
    Cx = (1 / (6 * A)) * sumx
    Cy = (1 / (6 * A)) * sumy

    return Point(Cx, Cy)



def validate_line(vertices: list[tuple[float, float]]) -> None:
    """Validate the available XY line coordinates without changing them."""
    if len(vertices) < 2 or all(point == vertices[0] for point in vertices[1:]):
        raise ValueError("requires a non-zero-length line")
    for index, point in enumerate(vertices):
        try:
            valid = len(point) >= 2 and all(math.isfinite(value) for value in point[:2])
        except (TypeError, OverflowError) as exc:
            raise ValueError(f"vertex {index} has invalid coordinates") from exc
        if not valid:
            raise ValueError(f"vertex {index} requires finite XY coordinates")


def ogr_polygon(
    vertices: list[tuple[float, float]], *, context: str = "Basin polygon"
) -> ogr.Geometry:
    """Create a polygon from an exterior ring and optional closed interior rings.

    Importing OGR only when needed keeps the rest of Pyromb importable
    outside QGIS; GDAL Python bindings are required to build basins.
    Closed rings concatenated by the QGIS adapter retain their closing vertex.
    Preserve those boundaries instead of joining them with artificial edges.
    Additional exterior parts and malformed ring sequences remain unsupported.
    """
    try:
        from osgeo import ogr
    except ImportError as exc:
        raise RuntimeError(
            "OGR Python bindings are required for basin matching. "
            "Run under QGIS/OSGeo4W or install GDAL in the Python environment."
        ) from exc

    try:
        coords = [(float(x), float(y)) for x, y in vertices]
    except (TypeError, ValueError) as exc:
        raise ValueError("Polygon requires a sequence of (x, y) coordinates") from exc
    if len(coords) < 3 or any(
        not math.isfinite(x) or not math.isfinite(y) for x, y in coords
    ):
        raise ValueError("Polygon needs at least three finite coordinates")
    rings: list[list[tuple[float, float]]] = []
    pending: list[tuple[float, float]] = []
    for point in coords:
        pending.append(point)
        if len(pending) > 1 and point == pending[0]:
            rings.append(pending)
            pending = []
    if pending:
        if rings:
            raise ValueError("Polygon has an unclosed ring after a closed ring")
        # Preserve support for a single exterior ring without a closing vertex.
        rings.append([*pending, pending[0]])

    polygons = []
    for points in rings:
        if len(set(points[:-1])) < 3:
            raise ValueError("Polygon ring has fewer than three distinct vertices")
        ring = ogr.Geometry(ogr.wkbLinearRing)
        for x, y in points:
            ring.AddPoint_2D(x, y)
        part = ogr.Geometry(ogr.wkbPolygon)
        part.AddGeometry(ring)
        if part.IsEmpty() or not part.IsValid() or part.GetArea() <= 0:
            raise ValueError("Polygon ring is empty, invalid, or has zero area")
        polygons.append(part)

    polygon = polygons[0].Clone()
    for interior in polygons[1:]:
        if not polygons[0].Contains(interior):
            raise ValueError(
                "Polygon has invalid interior rings or multiple exterior parts; "
                "each interior ring must lie inside the first exterior ring"
            )
        polygon.AddGeometry(interior.GetGeometryRef(0))
    if polygon.IsEmpty() or not polygon.IsValid() or polygon.GetArea() <= 0:
        raise ValueError("Polygon is empty, invalid, or has zero area")
    if len(polygons) > 1:
        count = len(polygons) - 1
        excluded_area = sum(part.GetArea() for part in polygons[1:])
        warnings.warn(
            f"{context} contains {count} interior ring{'s' if count != 1 else ''} "
            f"(hole area {excluded_area:g} square CRS units excluded from basin area). "
            "Proceeding with the polygon and its holes preserved; input geometry is unchanged.",
            UserWarning,
            stacklevel=2,
        )
    return polygon


def contains(polygon: ogr.Geometry, point: tuple[float, float]) -> bool:
    """Check strict point-in-polygon containment using OGR/GEOS.

    A point exactly on a basin boundary is not considered inside.
    """
    from osgeo import ogr

    test_point = ogr.Geometry(ogr.wkbPoint)
    test_point.AddPoint_2D(*point)
    return bool(polygon.Contains(test_point))


def ogr_area(polygon: ogr.Geometry) -> float:
    """Return a validated OGR polygon's plan area in CRS units squared."""
    return float(polygon.GetArea())
