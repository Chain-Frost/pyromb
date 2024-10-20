# src/pyromb/core/geometry/point.py


class Point:
    """An object representing a point shape type.

    Parameters
    ----------
    x : float
        The x coordinate.
    y : float
        The y coordinate.
    """

    def __init__(self, x: float = 0.0, y: float = 0.0):
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise ValueError(f"Invalid coordinates: x={x}, y={y}. Both must be numbers.")
        self._x = float(x)
        self._y = float(y)

    @property
    def x(self) -> float:
        """float: The x coordinate."""
        return self._x

    @property
    def y(self) -> float:
        """float: The y coordinate."""
        return self._y

    def coordinates(self) -> tuple[float, float]:
        """Get the coordinates of the point.

        Returns
        -------
        Tuple[float, float]
            The (x, y) coordinates.
        """
        return (self._x, self._y)

    def __str__(self) -> str:
        """Return a string representation of the point."""
        return f"[{self._x}, {self._y}]"

    def __repr__(self) -> str:
        """Return an unambiguous string representation of the point."""
        return f"Point(x={self._x}, y={self._y})"

    def __eq__(self, other) -> bool:
        """Check if two points are equal based on their coordinates.

        Parameters
        ----------
        other : Point
            The other point to compare.

        Returns
        -------
        bool
            True if both points have the same coordinates, False otherwise.
        """
        if not isinstance(other, Point):
            return NotImplemented
        return self._x == other._x and self._y == other._y
