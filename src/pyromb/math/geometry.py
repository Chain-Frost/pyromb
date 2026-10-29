"""Geometry calculations and the OGR boundary used by catchment construction."""

from __future__ import annotations

import math
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


def ogr_polygon(vertices: list[tuple[float, float]]) -> ogr.Geometry:
    """Create a validated single-ring OGR polygon.

    The QGIS adapter flattens the vertex sequence. A completed exterior ring
    followed by further non-closing vertices indicates unsupported holes or
    additional polygon parts. Do not silently miscalculate basin areas.
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

    # Repeated opening/closing vertices are harmless. Only treat a return to
    # the first vertex as ring closure after three distinct vertices exist.
    origin = coords[0]
    distinct: set[tuple[float, float]] = set()
    exterior_closed = False
    for point in coords:
        distinct.add(point)
        if point == origin and len(distinct) >= 3:
            exterior_closed = True
        elif exterior_closed:
            raise ValueError(
                "Polygon has multiple rings (holes) or parts. "
                "Remove holes or split multipart basins into single-part "
                "polygons in QGIS before rebuilding."
            )

    if coords[0] != coords[-1]:
        coords.append(coords[0])
    if len(set(coords[:-1])) < 3:
        raise ValueError("Polygon has fewer than three distinct vertices")

    ring = ogr.Geometry(ogr.wkbLinearRing)
    for x, y in coords:
        ring.AddPoint_2D(x, y)
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    if polygon.IsEmpty() or not polygon.IsValid() or polygon.GetArea() <= 0:
        raise ValueError("Polygon is empty, invalid, or has zero area")
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
