# src/pyromb/core/attributes/reach.py
from typing import Optional, cast
from ..geometry.line import Line
from enum import Enum
from .node import Node
from ..geometry.point import Point


class ReachType(Enum):
    NATURAL = 1
    UNLINED = 2
    LINED = 3
    DROWNED = 4


class Reach(Line):
    """A Reach object represents a reach as defined in hydrological models.

    Attributes
    ----------
    name : str
        The name of the reach, should be unique
    reachType : ReachType
        The type of reach as specified by the hydrological model.
    slope : float
        The slope of the reach in m/m
    """

    def __init__(
        self,
        name: str = "",
        vector: Optional[list[Node]] = None,
        reachType: ReachType = ReachType.NATURAL,
        slope: float = 0.0,
    ):
        super().__init__(cast(list[Point], vector) if vector is not None else [])
        self._name: str = name
        self._reachType: ReachType = reachType
        self._slope: float = slope

    def __str__(self) -> str:
        return f"Name: {self._name}\nLength: {round(self.length, 3)}\nType: {self.reachType}\nSlope: {self._slope}"

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def reachType(self) -> ReachType:
        return self._reachType

    @reachType.setter
    def reachType(self, reachType: ReachType) -> None:
        self._reachType = reachType

    @property
    def slope(self) -> float:
        return self._slope

    @slope.setter
    def slope(self, slope: float) -> None:
        self._slope = slope

    def getPoint(self, direction: str) -> Node:
        """Returns either the upstream or downstream 'us'/'ds' point of the reach.

        Parameters
        ----------
        direction : str
            'us' - for upstream point.
            'ds' - for downstream point

        Returns
        -------
        Node
            The US or DS point

        Raises
        ------
        KeyError
            If direction is not either 'us' or 'ds'
        """
        if direction == "us":
            return cast(Node, self._vector[0])  # Assuming the first point is upstream
        elif direction == "ds":
            return cast(Node, self._vector[-1])  # Assuming the last point is downstream
        else:
            raise KeyError("Node direction not properly defined: expected 'us' or 'ds'.")

    def getStart(self) -> Node:
        """Get the upstream node of the reach."""
        return self.getPoint("us")

    def getEnd(self) -> Node:
        """Get the downstream node of the reach."""
        return self.getPoint("ds")
