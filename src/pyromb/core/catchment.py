"""Connect catchment nodes and reaches after validating their identifiers and topology."""

import math
from collections.abc import Sequence
from numbers import Number
from typing import SupportsFloat, cast

import numpy as np
from numpy.typing import NDArray

from ..math import geometry
from .attributes.basin import Basin
from .attributes.confluence import Confluence
from .attributes.node import Node
from .attributes.reach import Reach


class Catchment:
    """Describe water flow through the catchment and its entities.

    Parameters
    ----------
    confluences : list[Confluence]
        The Confluences in the catchment
    basins : list[Basin]
        The Basins in the catchment
    reaches: list[Reach]
        The Reaches in the catchment
    """

    @staticmethod
    def _validate_identifiers(
        confluences: Sequence[Confluence], basins: Sequence[Basin], reaches: Sequence[Reach]
    ) -> None:
        """Enforce one global namespace across model nodes and reaches."""
        names: set[str] = set()
        categories: tuple[tuple[str, Sequence[Node | Reach]], ...] = (
            ("Confluence", confluences),
            ("Basin", basins),
            ("Reach", reaches),
        )
        for category, elements in categories:
            for i, element in enumerate(elements):
                raw: object = element.name
                if isinstance(raw, Number) and not isinstance(raw, int):
                    try:
                        finite = math.isfinite(cast(SupportsFloat, raw))
                    except (TypeError, ValueError, OverflowError):
                        finite = False
                    if not finite:
                        raise ValueError(
                            f"{category} feature {i} has an invalid identifier"
                        )
                value = str(raw).strip() if raw is not None else ""
                if not value:
                    raise ValueError(f"{category} feature {i} has an empty identifier")
                if value in names:
                    raise ValueError(
                        f"Duplicate model identifier {value!r} at {category} feature {i}"
                    )
                names.add(value)

    def __init__(
        self, confluences: list[Confluence] = [], basins: list[Basin] = [], reaches: list[Reach] = []
    ) -> None:
        """Store model entities after checking their global identifier namespace."""
        self._validate_identifiers(confluences, basins, reaches)
        self._edges: list[Reach] = reaches
        self._vertices: list[Node] = [*confluences, *basins]
        self._incidenceMatrixDS: list[list[int]] | NDArray[np.int_] = []
        self._incidenceMatrixUS: list[list[int]] | NDArray[np.int_] = []
        self._out = 0
        self._endSentinel = -1

    def _validate_topology(self, tolerance: float) -> None:
        """Fail on unsnapped reach ends, ambiguous nodes and invalid networks.

        The preflight is deliberately separate from the inherited traversal.
        It does not move or join vertices or alter accepted connectivity.
        """
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)):
            raise ValueError("Connection tolerance must be a finite non-negative number")
        try:
            finite_tolerance = math.isfinite(tolerance)
        except OverflowError as exc:
            raise ValueError("Connection tolerance must be a finite non-negative number") from exc
        if not finite_tolerance or tolerance < 0:
            raise ValueError("Connection tolerance must be a finite non-negative number")
        if not self._vertices or not self._edges:
            raise ValueError("Catchment must contain nodes and reaches")

        outlets = [
            node for node in self._vertices
            if isinstance(node, Confluence) and node.isOut
        ]
        if len(outlets) != 1:
            raise ValueError(f"Catchment must have exactly one outlet; found {len(outlets)}")

        coordinates = [node.coordinates() for node in self._vertices]
        for node, (x, y) in zip(self._vertices, coordinates):
            if not math.isfinite(x) or not math.isfinite(y):
                raise ValueError(f"Node {node.name!r} has non-finite coordinates")
        adjacency: list[set[int]] = [set() for _ in self._vertices]

        for edge in self._edges:
            for index, vertex in enumerate(edge.toVector()):
                if not all(math.isfinite(value) for value in vertex.coordinates()):
                    raise ValueError(
                        f"Reach {edge.name!r} vertex {index} has non-finite coordinates"
                    )
            endpoints = (edge.getStart(), edge.getEnd())
            indexes = []
            for direction, point in zip(("start", "end"), endpoints):
                x, y = point.coordinates()
                distances = [
                    math.hypot(x - vx, y - vy) for vx, vy in coordinates
                ]
                matches = [
                    idx for idx, distance in enumerate(distances)
                    if distance <= tolerance
                ]
                if not matches:
                    nearest = min(range(len(distances)), key=distances.__getitem__)
                    raise ValueError(
                        f"Reach {edge.name!r} {direction} endpoint ({x}, {y}) "
                        f"is not snapped within {tolerance:g} CRS units; "
                        f"nearest node {self._vertices[nearest].name!r} "
                        f"is {distances[nearest]:g} units away"
                    )
                if len(matches) != 1:
                    candidates = [
                        (self._vertices[idx].name, distances[idx]) for idx in matches
                    ]
                    raise ValueError(
                        f"Reach {edge.name!r} {direction} endpoint is ambiguous: "
                        f"matches nodes (name, distance) {candidates!r} "
                        f"within {tolerance:g} CRS units"
                    )
                indexes.append(matches[0])

            start, end = indexes
            if start == end:
                raise ValueError(
                    f"Reach {edge.name!r} connects node "
                    f"{self._vertices[start].name!r} to itself"
                )
            adjacency[start].add(end)
            adjacency[end].add(start)

        # The graph must be a single undirected tree reaching the model outlet.
        outlet_index = next(
            idx for idx, node in enumerate(self._vertices)
            if isinstance(node, Confluence) and node.isOut
        )
        visited = {outlet_index}
        pending = [outlet_index]
        while pending:
            current = pending.pop()
            for neighbour in adjacency[current] - visited:
                visited.add(neighbour)
                pending.append(neighbour)

        if len(visited) != len(self._vertices):
            missing = [
                node.name for idx, node in enumerate(self._vertices)
                if idx not in visited
            ]
            raise ValueError(
                f"Disconnected catchment: nodes not connected to outlet: {missing!r}"
            )
        if len(self._edges) != len(self._vertices) - 1:
            raise ValueError(
                "Catchment must be a tree: cycle or parallel reaches detected "
                f"({len(self._vertices)} nodes, {len(self._edges)} reaches); "
                f"reach IDs: {[edge.name for edge in self._edges]!r}"
            )

    def connect(self, tolerance: float = 1e-6) -> tuple[NDArray[np.int_], NDArray[np.int_]]:
        """Connect the individual attributes to create the catchment.

        Returns:
        -------
        tuple
            (downstream, upstream) incidence matricies of the catchment tree.
        """
        self._validate_topology(tolerance)

        connectionMatrix = np.zeros((len(self._vertices), len(self._edges)), dtype=int)
        for i, edge in enumerate(self._edges):
            s = edge.getStart()
            e = edge.getEnd()
            minStart = math.inf
            minEnd = math.inf
            closestStart = 0
            closestEnd = 0
            for j, vert in enumerate(self._vertices):
                tempStart = geometry.length([vert, s])
                tempEnd = geometry.length([vert, e])
                if tempStart < minStart:
                    closestStart = j
                    minStart = tempStart
                if tempEnd < minEnd:
                    closestEnd = j
                    minEnd = tempEnd
            connectionMatrix[closestStart][i] = 1
            connectionMatrix[closestEnd][i] = 2


        # Find the 'out' node
        # Used to determine the starting point of breath first search
        # And subsequently the direction of flow
        for k, conf in enumerate(self._vertices):
            if isinstance(conf, Confluence):
                if conf.isOut:
                    self._out = k
                    break


        # Determine incidence matrix relating reaches to nodes and map downstream direction between elements
        # Matrix I (m * m - 1)
        # m = nodes
        # n = reaches
        # value of m n =  the index of the downstream node
        # Think about I as relating upstream nodes (m) to downstream nodes (m n) through reach (n)
        # (m n) of -1 indicates no downstream node for relationship m n
        newIncidenceDS = np.zeros((len(self._vertices), len(self._edges)), dtype=int)
        newIncidenceDS.fill(self._endSentinel)
        newIncidenceUS = newIncidenceDS.copy()
        queue = []
        colour = np.zeros((len(self._vertices), len(self._edges)))
        i = self._out
        j = 0
        queue.append((i, j))
        while(len(queue) != 0):
            #Move in the n direction
            u = queue.pop()
            idxi = u[0]
            j = u[1]
            for k in range(len(connectionMatrix[u[0]])):
                idxj = j % len(connectionMatrix[idxi])
                if connectionMatrix[idxi][idxj] > 0:
                    if colour[idxi][idxj] == 0:
                        colour[idxi][idxj] = 1
                        u = (idxi, idxj)
                        queue.append(u)
                j += 1

            #Move in the m direction
            i = u[0]
            idxj = u[1]
            for row_index in range(len(connectionMatrix)):
                idxi = i % len(connectionMatrix)
                if connectionMatrix[idxi][idxj] > 0:
                    if colour[idxi][idxj] == 0:
                        colour[idxi][idxj] = 1
                        queue.append((idxi, idxj))
                        newIncidenceUS[u[0]][u[1]] = idxi
                        newIncidenceDS[idxi][idxj] = u[0]
                i += 1
        self._incidenceMatrixDS = newIncidenceDS.copy()
        self._incidenceMatrixUS = newIncidenceUS.copy()

        return (self._incidenceMatrixDS, self._incidenceMatrixUS)
