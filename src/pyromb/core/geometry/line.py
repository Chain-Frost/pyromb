# src/pyromb/core/geometry/line.py
from typing import Optional, Iterator
from osgeo import ogr
from ...math import geometry
from .point import Point


class GeometryError(Exception):
    """Custom exception for geometry-related errors."""

    pass


class Line:
    """An object representing a line shape type.

    A line is a sequence of points that defines a path.

    Attributes
    ----------
    length : float
        The cartesian length of the line.

    Parameters
    ----------
    vector : Optional[List[Point]]
        The points that make up the line.
    """

    def __init__(self, vector: Optional[list[Point]] = None) -> None:
        if vector is None:
            vector = []
        self._vector: list[Point] = self.pointVector(vector)
        self._length: float = self.calculate_length()

    def __iter__(self) -> Iterator[Point]:
        self._current = 0
        return self

    def __next__(self) -> Point:
        if self._current < len(self._vector):
            point = self._vector[self._current]
            self._current += 1
            return point
        else:
            raise StopIteration

    def __len__(self) -> int:
        """Return the number of points in the line."""
        return len(self._vector)

    def __getitem__(self, index: int) -> Point:
        return self._vector[index]

    def __setitem__(self, index: int, value: Point):
        if not isinstance(value, Point):
            raise TypeError("Only Point instances can be assigned.")
        self._vector[index] = value
        self._length = self.calculate_length()

    def append(self, point: Point):
        """Add an additional point to the line.

        Parameters
        ----------
        point : Point
            The point to add to the line.
        """
        if not isinstance(point, Point):
            raise TypeError("Only Point instances can be appended.")
        self._vector.append(point)
        self._length = self.calculate_length()

    @property
    def length(self) -> float:
        """float: The cartesian length of the line."""
        return self._length

    def toVector(self) -> list[Point]:
        """Convert the line into a list of points.

        Returns
        -------
        List[Point]
            A list of Point objects.
        """
        return self._vector.copy()

    def getStart(self) -> Point:
        """Get the starting point of the line.

        Returns
        -------
        Point
            The start point.

        Raises
        ------
        GeometryError
            If the line is empty.
        """
        if not self._vector:
            raise GeometryError("Line is empty. No start point available.")
        return self._vector[0]

    def getEnd(self) -> Point:
        """Get the end point of the line.

        Returns
        -------
        Point
            The end point.

        Raises
        ------
        GeometryError
            If the line is empty.
        """
        if not self._vector:
            raise GeometryError("Line is empty. No end point available.")
        return self._vector[-1]

    def calculate_length(self) -> float:
        """Calculate the cartesian length of the line.

        Returns
        -------
        float
            The length of the line.

        Raises
        ------
        GeometryError
            If the line cannot be converted to an OGR LineString.
        """
        if not self._vector:
            return 0.0
        coords = [point.coordinates() for point in self._vector]
        try:
            ogr_line = geometry.create_line_string(coords)
            length = geometry.calculate_length(ogr_line)
            return length
        except geometry.GeometryError as ge:
            raise GeometryError(f"Failed to calculate length: {ge}")

    @staticmethod
    def pointVector(vector: list[Point]) -> list[Point]:
        """Convert a list of Points ensuring all elements are Point instances.

        Parameters
        ----------
        vector : List[Point]
            A list of Point objects.

        Returns
        -------
        List[Point]
            A validated list of Point objects.

        Raises
        ------
        TypeError
            If any element in the vector is not a Point instance.
        """
        if not isinstance(vector, list):
            raise TypeError("Vector must be a list of Point instances.")
        for idx, item in enumerate(vector):
            if not isinstance(item, Point):
                raise TypeError(f"Item at index {idx} is not a Point instance.")
        return vector.copy()
