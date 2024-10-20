# src/pyromb/math/geometry.py
import math
from typing import Union
from osgeo import ogr
from ..core.geometry.point import Point
import logging


class GeometryError(Exception):
    """Custom exception for geometry-related errors."""

    pass


def wkbFlatten(geometry_type: int) -> int:
    return geometry_type & (~ogr.wkb25DBit)


def calculate_length(geometry: ogr.Geometry) -> float:
    """
    Calculate the length of an OGR geometry.

    Parameters
    ----------
    geometry : ogr.Geometry
        The geometry to calculate the length for.

    Returns
    -------
    float
        The length of the geometry.

    Raises
    ------
    GeometryError
        If the geometry is None or empty.
    """
    if geometry is None or geometry.IsEmpty():
        raise GeometryError("Cannot calculate length: Geometry is None or empty.")
    return geometry.Length()


def calculate_area(geometry: ogr.Geometry) -> float:
    """
    Calculate the area of an OGR Polygon or MultiPolygon geometry.

    Parameters
    ----------
    geometry : ogr.Geometry
        The polygon geometry to calculate the area for.

    Returns
    -------
    float
        The area of the polygon.

    Raises
    ------
    GeometryError
        If the geometry is None, empty, or not a Polygon/MultiPolygon.
    """
    if geometry is None or geometry.IsEmpty():
        raise GeometryError("Cannot calculate area: Geometry is None or empty.")
    geom_type = wkbFlatten(geometry.GetGeometryType())
    if geom_type not in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
        raise GeometryError("Cannot calculate area: Geometry is not a Polygon or MultiPolygon.")
    return geometry.GetArea()


def calculate_centroid(geometry: ogr.Geometry) -> Point:
    """
    Calculate the centroid of an OGR Polygon or MultiPolygon geometry.

    Parameters
    ----------
    geometry : ogr.Geometry
        The polygon geometry to calculate the centroid for.

    Returns
    -------
    Point
        The centroid as a Point object.

    Raises
    ------
    GeometryError
        If the geometry is None, empty, or not a Polygon/MultiPolygon.
        If the centroid calculation fails.
    """
    if geometry is None or geometry.IsEmpty():
        raise GeometryError("Cannot calculate centroid: Geometry is None or empty.")
    geom_type = wkbFlatten(geometry.GetGeometryType())
    if geom_type not in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
        raise GeometryError("Cannot calculate centroid: Geometry is not a Polygon or MultiPolygon.")

    centroid_geom = geometry.Centroid()
    if centroid_geom is None or centroid_geom.IsEmpty():
        raise GeometryError("Centroid calculation failed: Resulting centroid geometry is None or empty.")

    return Point(x=centroid_geom.GetX(), y=centroid_geom.GetY())


def calculate_distance(pt1: ogr.Geometry, pt2: ogr.Geometry) -> float:
    """
    Calculate the Euclidean distance between two OGR point geometries.

    Parameters
    ----------
    pt1 : ogr.Geometry
        The first point geometry.
    pt2 : ogr.Geometry
        The second point geometry.

    Returns
    -------
    float
        The Euclidean distance between pt1 and pt2.

    Raises
    ------
    GeometryError
        If either pt1 or pt2 is None, empty, or not a point geometry.
    """
    if pt1 is None or pt1.IsEmpty():
        raise GeometryError("First point is None or empty.")
    if pt2 is None or pt2.IsEmpty():
        raise GeometryError("Second point is None or empty.")
    if wkbFlatten(pt1.GetGeometryType()) != ogr.wkbPoint:
        raise GeometryError("First geometry is not a Point.")
    if wkbFlatten(pt2.GetGeometryType()) != ogr.wkbPoint:
        raise GeometryError("Second geometry is not a Point.")

    return math.sqrt((pt1.GetX() - pt2.GetX()) ** 2 + (pt1.GetY() - pt2.GetY()) ** 2)


def point_on_reference(pt: ogr.Geometry, ref_points: list[ogr.Geometry], tolerance: float = 1e-6) -> bool:
    """
    Check if a point coincides with any reference point within a given tolerance.

    Parameters
    ----------
    pt : ogr.Geometry
        The point to check.
    ref_points : List[ogr.Geometry]
        The list of reference points.
    tolerance : float, optional
        The tolerance distance, by default 1e-6.

    Returns
    -------
    bool
        True if the point coincides with any reference point within the tolerance, False otherwise.

    Raises
    ------
    GeometryError
        If pt is None, empty, or not a point geometry.
        If any reference point in ref_points is None, empty, or not a point geometry.
    """
    if pt is None or pt.IsEmpty():
        raise GeometryError("Input point is None or empty.")
    if wkbFlatten(pt.GetGeometryType()) != ogr.wkbPoint:
        raise GeometryError("Input geometry is not a Point.")

    for ref_pt in ref_points:
        if ref_pt is None or ref_pt.IsEmpty():
            raise GeometryError("Reference point is None or empty.")
        if wkbFlatten(ref_pt.GetGeometryType()) != ogr.wkbPoint:
            raise GeometryError("Reference geometry is not a Point.")
        distance = calculate_distance(pt, ref_pt)
        if distance <= tolerance:
            return True
    return False


def create_line_string(coords: list[tuple[float, float]]) -> ogr.Geometry:
    """
    Create an OGR LineString geometry from a list of (x, y) tuples.

    Parameters
    ----------
    coords : List[Tuple[float, float]]
        The coordinates of the LineString vertices.

    Returns
    -------
    ogr.Geometry
        The created LineString geometry.

    Raises
    ------
    GeometryError
        If coords is empty or contains invalid coordinate tuples.
    """
    if not coords:
        raise GeometryError("Coordinate list is empty.")

    line = ogr.Geometry(ogr.wkbLineString)
    for idx, (x, y) in enumerate(coords):
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise GeometryError(f"Invalid coordinates at index {idx}: ({x}, {y})")
        line.AddPoint(x, y)
    return line


def create_polygon(coords: list[tuple[float, float]]) -> ogr.Geometry:
    """
    Create an OGR Polygon geometry from a list of (x, y) tuples.

    Parameters
    ----------
    coords : List[Tuple[float, float]]
        The coordinates of the Polygon vertices. The first and last points must be the same to close the ring.

    Returns
    -------
    ogr.Geometry
        The created Polygon geometry.

    Raises
    ------
    GeometryError
        If coords are insufficient to form a polygon or if the ring is not closed.
    """
    if not coords:
        raise GeometryError("Coordinate list is empty.")
    if len(coords) < 4:
        raise GeometryError("At least four coordinates are required to form a Polygon (including closure).")
    if coords[0] != coords[-1]:
        raise GeometryError("Polygon ring is not closed. First and last coordinates must be the same.")

    ring = ogr.Geometry(ogr.wkbLinearRing)
    for idx, (x, y) in enumerate(coords):
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise GeometryError(f"Invalid coordinates at index {idx}: ({x}, {y})")
        ring.AddPoint(x, y)

    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    return polygon


def create_point(x: float, y: float) -> ogr.Geometry:
    """
    Create an OGR Point geometry from x and y coordinates.

    Parameters
    ----------
    x : float
        The X coordinate.
    y : float
        The Y coordinate.

    Returns
    -------
    ogr.Geometry
        The created Point geometry.

    Raises
    ------
    GeometryError
        If x or y is not a valid number.
    """
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        raise GeometryError(f"Invalid coordinates: ({x}, {y})")

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(x, y)
    return point


def is_geometry_empty(geom: ogr.Geometry) -> bool:
    """
    Check if an OGR geometry is empty.

    Parameters
    ----------
    geom : ogr.Geometry
        The geometry to check.

    Returns
    -------
    bool
        True if the geometry is empty, False otherwise.

    Raises
    ------
    GeometryError
        If geom is None.
    """
    if geom is None:
        raise GeometryError("Geometry is None.")
    return geom.IsEmpty()


def contains(polygon: ogr.Geometry, point: ogr.Geometry) -> bool:
    """
    Check if a polygon contains a point.

    Parameters
    ----------
    polygon : ogr.Geometry
        The Polygon or MultiPolygon geometry.
    point : ogr.Geometry
        The Point geometry.

    Returns
    -------
    bool
        True if the polygon contains the point, False otherwise.

    Raises
    ------
    GeometryError
        If either polygon or point is None, empty, or of incorrect geometry types.
    """
    if polygon is None or polygon.IsEmpty():
        raise GeometryError("Polygon geometry is None or empty.")
    if point is None or point.IsEmpty():
        raise GeometryError("Point geometry is None or empty.")

    # The wkbFlatten function is not directly available in the osgeo.ogr module in some versions of GDAL/OGR's Python
    # bindings. This function is used in the C++ API but may not be exposed in the Python API.
    polygon_geom_type = wkbFlatten(polygon.GetGeometryType())
    point_geom_type = wkbFlatten(point.GetGeometryType())

    if polygon_geom_type not in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
        raise GeometryError(
            f"First geometry is not a Polygon or MultiPolygon: {ogr.GeometryTypeToName(polygon_geom_type)}"
        )
    if point_geom_type != ogr.wkbPoint:
        raise GeometryError(f"Second geometry is not a Point: {ogr.GeometryTypeToName(point_geom_type)}")

    # Handle MultiPolygon with multiple geometries
    if polygon_geom_type == ogr.wkbMultiPolygon:
        num_geoms = polygon.GetGeometryCount()
        if num_geoms > 1:
            logging.warning(f"Polygon is a MultiPolygon with {num_geoms} parts.")
        elif num_geoms == 1:
            logging.warning("Polygon is a MultiPolygon with a single part. Proceeding.")
            polygon = polygon.GetGeometryRef(0)  # Use the first (and only) polygon

    return polygon.Contains(point)


# Define a type alias for clarity
Coordinate = Union[tuple[float, float], list[float]]


def length(vertices: list[Coordinate]) -> float:
    """
    Calculate the Cartesian length of a vector defined by a list of coordinates.

    Parameters
    ----------
    vertices : List[Coordinate]
        The list of coordinates to calculate the length. Each coordinate should be a tuple or list
        containing at least two numerical values representing (x, y).

    Returns
    -------
    float
        The total Cartesian length of the vector.

    Raises
    ------
    ValueError
        If a vertex does not contain at least two numerical values.
    TypeError
        If the vertices are not provided as a list of tuples or lists.
    """
    if not isinstance(vertices, list):
        raise TypeError("vertices must be a list of coordinate tuples or lists.")

    total_length = 0.0

    for i in range(len(vertices) - 1):
        current_vertex = vertices[i]
        next_vertex = vertices[i + 1]

        # Ensure each vertex has at least two elements
        if not (isinstance(current_vertex, (tuple, list)) and isinstance(next_vertex, (tuple, list))):
            raise TypeError("Each vertex must be a tuple or list containing numerical coordinates.")
        if len(current_vertex) < 2 or len(next_vertex) < 2:
            raise ValueError("Each vertex must contain at least two numerical values for (x, y).")

        dx: float = next_vertex[0] - current_vertex[0]
        dy: float = next_vertex[1] - current_vertex[1]
        segment_length: float = math.hypot(dx, dy)
        total_length += segment_length

    return total_length
