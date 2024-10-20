# src/pyromb/core/geometry/polygon.py
from typing import Optional
from ...math import geometry
from .line import Line
from .point import Point


class Polygon(Line):
    """An object representing a polygon shape type.

    A polygon is a closed shape that defines an area.

    Attributes
    ----------
    area : float
        The cartesian area of the polygon.
    centroid : Point
        The centroid of the polygon.

    Parameters
    ----------
    vector : Optional[List[Point]]
        The points which form the polygon.
    """

    def __init__(self, vector: Optional[list[Point]] = None) -> None:
        if vector is None:
            vector = []
        super().__init__(vector)

        if not self:
            raise ValueError("Vector cannot be empty to form a Polygon.")

        # Ensure the polygon is closed by appending the first point at the end if necessary
        if self[0] != self[-1]:
            self.append(self[0])

        # Convert the list of Points to a list of (x, y) tuples
        coords = [point.coordinates() for point in self.toVector()]

        try:
            # Create an OGR Polygon geometry
            ogr_polygon = geometry.create_polygon(coords)

            # Calculate area and centroid using the updated geometry module
            self._area = geometry.calculate_area(ogr_polygon)
            self._centroid = geometry.calculate_centroid(ogr_polygon)
        except geometry.GeometryError as ge:
            raise ValueError(f"Failed to initialize Polygon: {ge}")

    @property
    def area(self) -> float:
        """float: The cartesian area of the polygon."""
        return self._area

    @property
    def centroid(self) -> Point:
        """Point: The centroid of the polygon."""
        return self._centroid
