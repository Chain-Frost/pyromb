# src/pyromb/core/catchment.py

from typing import Optional, Union
import numpy as np
import logging
from collections import deque
from .attributes.basin import Basin
from .attributes.confluence import Confluence
from .attributes.node import Node
from .attributes.reach import Reach
import math

# Configure logging (adjust as needed or configure in a higher-level module)
# logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class Catchment:
    """
    The Catchment is a tree of attributes that describes how water
    flows through the model and the entities which act upon it.

    Parameters
    ----------
    confluences : Optional[List[Confluence]]
        The Confluences in the catchment.
    basins : Optional[List[Basin]]
        The Basins in the catchment.
    reaches : Optional[List[Reach]]
        The Reaches in the catchment.
    """

    def __init__(
        self,
        confluences: Optional[list[Confluence]] = None,
        basins: Optional[list[Basin]] = None,
        reaches: Optional[list[Reach]] = None,
    ) -> None:
        self._edges: list[Reach] = reaches if reaches is not None else []
        self._vertices: list[Node] = []
        if confluences:
            self._vertices.extend(confluences)
        if basins:
            self._vertices.extend(basins)
        self._incidenceMatrixDS: np.ndarray = np.array([])
        self._incidenceMatrixUS: np.ndarray = np.array([])
        self._out_node_index: int = -1
        self._endSentinel: int = -1

    def _initialize_connection_matrix(self, num_vertices: int, num_edges: int) -> np.ndarray:
        """
        Initialize and populate the connection matrix based on vertex and edge distances.

        Parameters
        ----------
        num_vertices : int
            Number of vertices in the catchment.
        num_edges : int
            Number of edges (reaches) in the catchment.

        Returns
        -------
        np.ndarray
            The populated connection matrix.
        """
        connection_matrix = np.zeros((num_vertices, num_edges), dtype=int)

        for edge_idx, edge in enumerate(self._edges):
            start_node = edge.getStart()
            end_node = edge.getEnd()

            # Find the closest start and end vertices
            closest_start_idx = self._find_closest_vertex(start_node)
            closest_end_idx = self._find_closest_vertex(end_node)

            if closest_start_idx == -1 or closest_end_idx == -1:
                logging.warning(f"Edge {edge_idx} has no valid start or end vertex.")
                continue

            # Update the connection matrix
            connection_matrix[closest_start_idx, edge_idx] = 1  # Upstream connection
            connection_matrix[closest_end_idx, edge_idx] = 2  # Downstream connection

        return connection_matrix

    def _build_incidence_matrices(
        self,
        connection_matrix: np.ndarray,
        incidence_matrix_ds: np.ndarray,
        incidence_matrix_us: np.ndarray,
        num_vertices: int,
        num_edges: int,
    ) -> None:
        """
        Build the downstream and upstream incidence matrices using BFS traversal.

        Parameters
        ----------
        connection_matrix : np.ndarray
            The connection matrix indicating upstream and downstream connections.
        incidence_matrix_ds : np.ndarray
            The downstream incidence matrix to populate.
        incidence_matrix_us : np.ndarray
            The upstream incidence matrix to populate.
        num_vertices : int
            Number of vertices in the catchment.
        num_edges : int
            Number of edges (reaches) in the catchment.
        """
        # Initialize separate BFS queues and color matrices for US and DS
        queue_us = deque()
        queue_ds = deque()

        # Start BFS for Upstream connections
        queue_us.append((self._out_node_index, -1))  # (vertex index, edge index)
        colour_us = np.zeros((num_vertices, num_edges), dtype=int)

        while queue_us:
            current_vertex, incoming_edge = queue_us.popleft()

            for edge_idx in range(num_edges):
                connection_type = connection_matrix[current_vertex, edge_idx]

                if connection_type != 1:
                    continue  # Only process upstream connections

                if colour_us[current_vertex, edge_idx] != 0:
                    continue  # Edge already processed

                # Mark as visited
                colour_us[current_vertex, edge_idx] = 1

                # Determine downstream vertex based on connection type
                edge: Reach = self._edges[edge_idx]
                downstream_node: Node = edge.getEnd()

                downstream_vertex_coords = downstream_node.coordinates()
                downstream_vertex_idx = self._find_vertex_by_coordinates(downstream_vertex_coords)

                if downstream_vertex_idx == -1:
                    logging.warning(
                        f"Downstream vertex for edge {edge_idx} not found.\n"
                        f"Edge Details: Start Node ID {edge.getStart().name}, "
                        f"End Node ID {edge.getEnd().name}, Edge ID {edge.name}.\n"
                        f"Downstream Node Coordinates: {downstream_node.coordinates()}"
                    )
                    continue

                # Update incidence matrices
                incidence_matrix_us[current_vertex, edge_idx] = downstream_vertex_idx

                # Enqueue the downstream vertex for further processing
                queue_us.append((downstream_vertex_idx, edge_idx))

        # Start BFS for Downstream connections
        queue_ds.append((self._out_node_index, -1))  # (vertex index, edge index)
        colour_ds = np.zeros((num_vertices, num_edges), dtype=int)

        while queue_ds:
            current_vertex, incoming_edge = queue_ds.popleft()

            for edge_idx in range(num_edges):
                connection_type = connection_matrix[current_vertex, edge_idx]

                if connection_type != 2:
                    continue  # Only process downstream connections

                if colour_ds[current_vertex, edge_idx] != 0:
                    continue  # Edge already processed

                # Mark as visited
                colour_ds[current_vertex, edge_idx] = 1

                # Determine upstream vertex based on connection type
                edge: Reach = self._edges[edge_idx]
                upstream_node: Node = edge.getStart()

                upstream_vertex_coords = upstream_node.coordinates()
                upstream_vertex_idx = self._find_vertex_by_coordinates(upstream_vertex_coords)

                if upstream_vertex_idx == -1:
                    logging.warning(
                        f"Upstream vertex for edge {edge_idx} not found.\n"
                        f"Edge Details: Start Node ID {edge.getStart().name}, "
                        f"End Node ID {edge.getEnd().name}, Edge ID {edge.name}.\n"
                        f"Upstream Node Coordinates: {upstream_node.coordinates()}"
                    )
                    continue

                # Update incidence matrices
                incidence_matrix_ds[current_vertex, edge_idx] = upstream_vertex_idx

                # Enqueue the upstream vertex for further processing
                queue_ds.append((upstream_vertex_idx, edge_idx))

    def _find_vertex_by_coordinates(self, coords: Union[list[float], tuple[float, float]], tol=1e-1) -> int:
        """
        Find the index of a vertex based on its coordinates with a tolerance.

        Parameters
        ----------
        coords : Union[List[float], Tuple[float, float]]
            The (x, y) coordinates to match.
        tol : float
            Tolerance for floating-point comparison.

        Returns
        -------
        int
            The index of the matching vertex. Returns -1 if not found.
        """
        for idx, vertex in enumerate(self._vertices):
            vertex_coords = vertex.coordinates()
            distance = math.hypot(vertex_coords[0] - coords[0], vertex_coords[1] - coords[1])
            if distance <= tol:
                return idx
        return -1

    def connect(self) -> tuple[np.ndarray, np.ndarray]:
        """
        Connect the individual attributes to create the catchment.

        Returns
        -------
        tuple[np.ndarray, np.ndarray]
            (downstream, upstream) incidence matrices of the catchment tree.
        """
        num_vertices = len(self._vertices)
        num_edges = len(self._edges)

        # Initialize the connection matrix
        connection_matrix = np.zeros((num_vertices, num_edges), dtype=int)

        for edge_idx, edge in enumerate(self._edges):
            start_node = edge.getStart()
            end_node = edge.getEnd()

            # Find the closest start and end vertex indices
            closest_start_idx = self._find_closest_vertex(start_node)
            closest_end_idx = self._find_closest_vertex(end_node)

            if closest_start_idx == -1 or closest_end_idx == -1:
                logging.warning(f"Edge {edge_idx} has no valid start or end vertex.")
                continue

            # Populate connection matrix
            connection_matrix[closest_start_idx, edge_idx] = 1  # Upstream connection
            connection_matrix[closest_end_idx, edge_idx] = 2  # Downstream connection

        # Find the 'out' node
        self._find_out_node()

        # Initialize incidence matrices with sentinel values
        incidence_matrix_ds = np.full((num_vertices, num_edges), self._endSentinel, dtype=int)
        incidence_matrix_us = np.full((num_vertices, num_edges), self._endSentinel, dtype=int)

        # Populate Upstream Incidence Matrix
        for edge_idx, edge in enumerate(self._edges):
            start_idx = self._find_closest_vertex(edge.getStart())
            end_idx = self._find_closest_vertex(edge.getEnd())

            if start_idx != -1 and end_idx != -1:
                # Corrected: Downstream Matrix: [start_vertex][edge] = end_vertex
                incidence_matrix_ds[start_idx, edge_idx] = end_idx

                # Corrected: Upstream Matrix: [end_vertex][edge] = start_vertex
                incidence_matrix_us[end_idx, edge_idx] = start_idx

        # Debugging: Log the matrices
        logging.debug("Connection Matrix:")
        logging.debug(connection_matrix)
        logging.debug("Incidence Matrix US:")
        logging.debug(incidence_matrix_us)
        logging.debug("Incidence Matrix DS:")
        logging.debug(incidence_matrix_ds)

        self._incidenceMatrixDS = incidence_matrix_ds.copy()
        self._incidenceMatrixUS = incidence_matrix_us.copy()

        return (self._incidenceMatrixDS, self._incidenceMatrixUS)

    def _find_closest_vertex(self, node: Node, tol: float = 1e-6) -> int:
        """
        Find the index of the closest vertex to a given node based on Cartesian distance.

        Parameters
        ----------
        node : Node
            The node to find the closest vertex for.
        tol : float
            Tolerance for floating-point comparison.

        Returns
        -------
        int
            The index of the closest vertex. Returns -1 if no vertex is found.
        """
        min_distance = float("inf")
        closest_vertex_idx = -1

        node_coords = node.coordinates()

        for vertex_idx, vertex in enumerate(self._vertices):
            vertex_coords = vertex.coordinates()
            distance = math.hypot(vertex_coords[0] - node_coords[0], vertex_coords[1] - node_coords[1])

            if distance < min_distance:
                min_distance = distance
                closest_vertex_idx = vertex_idx

        if min_distance > tol:
            logging.warning(f"No vertex within tolerance for node at {node_coords}. Closest distance: {min_distance}")
            return -1

        return closest_vertex_idx

    def _find_out_node(self) -> None:
        """
        Identify and set the 'out' node in the catchment.
        """
        for idx, vertex in enumerate(self._vertices):
            if isinstance(vertex, Confluence) and vertex.isOut:
                self._out_node_index = idx
                logging.info(f"'Out' node found at index {idx}.")
                return
        logging.error("No 'out' node found in confluences.")
        raise ValueError("No 'out' node found in confluences.")
