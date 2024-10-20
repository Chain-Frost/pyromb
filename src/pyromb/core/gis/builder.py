# src/pyromb/core/geometry/builder.py
import os
import json
import logging
from typing import Optional
from osgeo import ogr  # type:ignore
import importlib.resources

from ..attributes.basin import Basin
from ..attributes.confluence import Confluence
from ..attributes.reach import Reach
from ..attributes.reach import ReachType
from ..gis.vector_layer import VectorLayer
from ..attributes.node import Node

# Import validation functions
from pyromb.core.geometry.shapefile_validation import (
    validate_shapefile_fields,
    validate_shapefile_geometries,
    validate_confluences_out_field,
)

# Import geometry functions from math.geometry
from pyromb.math.geometry import (
    create_line_string,
    create_polygon,
    create_point,
    is_geometry_empty,
    calculate_area,
    contains,
)

# Configure logging
# logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")


class Builder:
    """
    Build the entities of the catchment.

    The Builder is responsible for creating the entities (geometry, attributes) that
    the catchment will be built from. Building must take place before the
    catchment is connected and traversed.

    The objects returned from the Builder are to be passed to the Catchment.
    """

    def __init__(self, expected_fields_path: Optional[str] = None):
        """
        Initialize the Builder instance by loading expected fields from a JSON file.
        """
        # Define the directory where expected_fields.json is located
        if expected_fields_path is None:
            DIR = os.path.dirname(os.path.abspath(__file__))
            expected_fields_json_path = os.path.join(DIR, "resources", "expected_fields.json")
            with importlib.resources.open_text("pyromb.resources", "expected_fields.json") as f:
                EXPECTED_FIELDS_JSON = json.load(f)
        else:
            expected_fields_json_path = expected_fields_path

        # Load expected fields from JSON file
        try:
            with importlib.resources.open_text("pyromb.resources", "expected_fields.json") as f:
                EXPECTED_FIELDS_JSON = json.load(f)
            logging.info(f"Loaded expected fields from {expected_fields_json_path}.")
        except FileNotFoundError:
            logging.critical(f"Expected fields JSON file not found at {expected_fields_json_path}.")
            raise FileNotFoundError(f"Expected fields JSON file not found at {expected_fields_json_path}.")
        except json.JSONDecodeError as e:
            logging.critical(f"Error decoding JSON from {expected_fields_json_path}: {e}")
            raise json.JSONDecodeError(
                f"Error decoding JSON from {expected_fields_json_path}: {e}",
                e.doc,
                e.pos,
            )

        # Convert JSON to the required dictionary format
        self.expected_fields: dict[str, list[dict[str, str]]] = {
            key.lower(): [{"name": field["name"], "type": field["type"]} for field in fields]
            for key, fields in EXPECTED_FIELDS_JSON.items()
        }

        # Initialize basin geometries storage
        self.basin_geometries: Optional[list] = None

    def _validate_vector_layer(
        self,
        vector_layer: VectorLayer,
        layer_type: str,
        specific_validations: Optional[list] = None,
    ) -> bool:
        """
        Validate a vector layer's fields and geometries.

        Parameters
        ----------
        vector_layer : VectorLayer
            The vector layer to validate.
        layer_type : str
            The type of layer (e.g., 'reaches', 'basins').
        specific_validations : Optional[List], optional
            Additional specific validation functions to apply, by default None.

        Returns
        -------
        bool
            True if all validations pass, False otherwise.
        """
        shapefile_name = layer_type.capitalize()
        logging.info(f"Starting validation for {shapefile_name} layer.")

        # Retrieve expected fields for the layer type
        expected_fields = self.expected_fields.get(layer_type.lower())
        logging.info(f"Expected fields for {shapefile_name}: {expected_fields}")

        if expected_fields is None:
            logging.error(f"No expected fields defined for layer type '{layer_type}'.")
            return False

        # If expected_fields is empty, skip field validation
        if expected_fields:
            logging.info(f"Performing field validation for {shapefile_name}.")
            # Validate shapefile fields
            fields_valid = validate_shapefile_fields(
                vector_layer=vector_layer,
                shapefile_name=shapefile_name,
                expected_fields=expected_fields,
            )
            if not fields_valid:
                logging.error(f"Field validation failed for {shapefile_name}.")
                return False
            else:
                logging.info(f"Field validation passed for {shapefile_name}.")
        else:
            logging.info(f"No expected fields specified for {shapefile_name}, skipping field validation.")

        # Validate shapefile geometries
        logging.info(f"Performing geometry validation for {shapefile_name}.")
        geometries_valid = validate_shapefile_geometries(vector_layer, layer_type)
        if not geometries_valid:
            logging.error(f"Geometry validation failed for {shapefile_name}.")
            return False
        else:
            logging.info(f"Geometry validation passed for {shapefile_name}.")

        # Perform any specific validations if provided
        if specific_validations:
            logging.info(f"Performing specific validations for {shapefile_name}.")
            for validation_func in specific_validations:
                logging.info(f"Running validation function '{validation_func.__name__}' for {shapefile_name}.")
                valid = validation_func(vector_layer, shapefile_name)
                if not valid:
                    logging.error(f"Specific validation '{validation_func.__name__}' failed for {shapefile_name}.")
                    return False
                else:
                    logging.info(f"Specific validation '{validation_func.__name__}' passed for {shapefile_name}.")
        else:
            logging.info(f"No specific validations provided for {shapefile_name}.")

        logging.info(f"Validation passed for {shapefile_name} layer.")
        return True

    def reach(self, reach_layer: VectorLayer) -> list[Reach]:
        """
        Build the reach objects.
        """
        logging.info("Starting to build Reach objects.")

        # Validate the reach vector layer
        if not self._validate_vector_layer(reach_layer, "reaches"):
            logging.error("Reach vector layer validation failed.")
            raise ValueError("Reach vector layer validation failed.")
        else:
            logging.info("Reach vector layer validation passed.")

        reaches = []
        num_features = len(reach_layer)
        logging.info(f"Number of features in reach layer: {num_features}")

        for i in range(num_features):
            # logging.info(f"Processing reach feature index {i}")
            try:
                # Get standardized geometry and attributes
                geometry_coords = reach_layer.get_geometry(i)  # List of (x, y) tuples
                attributes = reach_layer.get_attributes(i)
                # logging.info(f"Geometry coordinates for feature {i}: {geometry_coords}")
                # logging.info(f"Attributes for feature {i}: {attributes}")

                # Create OGR LineString geometry using the geometry function
                ogr_geom = create_line_string(geometry_coords)
                # logging.info(f"OGR geometry created for feature {i}")

                if is_geometry_empty(ogr_geom):
                    logging.warning(f"Empty geometry at Reaches index {i}. Skipping.")
                    continue

                # Extract required attributes
                reach_id = attributes["id"]
                reach_type_value = attributes["t"]
                reach_s = attributes["s"]
                # logging.info(
                #     f"Extracted attributes for feature {i} - ID: {reach_id}, Type: {reach_type_value}, Slope: {reach_s}"
                # )

                # Convert the reach type to the ReachType enum
                reach_type = ReachType(reach_type_value)
                # logging.info(f"ReachType enum for feature {i}: {reach_type}")

                # Convert list of tuples to list of Node instances
                node_vector = [Node(x=x, y=y) for x, y in geometry_coords]
                # logging.info(f"Node vector for feature {i}: {node_vector}")

                # Create the Reach object
                reach = Reach(
                    name=reach_id,
                    vector=node_vector,  # Pass List[Node] instead of List[Tuple[float, float]]
                    reachType=reach_type,
                    slope=reach_s,
                )
                reaches.append(reach)
                # logging.info(f"Successfully created Reach object for feature {i} with ID '{reach_id}'")

            # except KeyError as e:
            #     logging.error(
            #         f"Missing expected field {e} in Reaches record {i}. Available attributes: {attributes.keys()}"
            #     )
            #     raise
            except ValueError as e:
                logging.error(f"Value error processing Reaches record {i}: {e}")
                raise
            except Exception as e:
                logging.error(f"Unexpected error processing Reaches record {i}: {e}")
                raise

        logging.info(f"Successfully built {len(reaches)} Reach objects.")
        return reaches

    def basin(self, centroid_layer: VectorLayer, basin_layer: VectorLayer) -> list[Basin]:
        """
        Build the basin objects using GDAL/OGR for geometry operations.
        """
        # Validate the basin vector layer
        if not self._validate_vector_layer(basin_layer, "basins"):
            raise ValueError("Basin vector layer validation failed.")

        # Validate the centroid vector layer
        if not self._validate_vector_layer(centroid_layer, "centroids"):
            raise ValueError("Centroid vector layer validation failed.")

        basins = []
        basin_geometries = []

        # Precompute OGR geometries for all basins
        for j in range(len(basin_layer)):
            basin_attributes = basin_layer.get_attributes(j)
            geometry_coords = basin_layer.get_geometry(j)  # List of (x, y) tuples

            # Create OGR Polygon geometry using the geometry function
            polygon = create_polygon(geometry_coords)

            if is_geometry_empty(polygon):
                logging.warning(f"Empty geometry at Basins index {j}. Skipping.")
                continue

            # Store the OGR geometry and attributes
            basin_geometries.append((polygon, basin_attributes))

        for i in range(len(centroid_layer)):
            centroid_attributes = centroid_layer.get_attributes(i)
            centroid_coords = centroid_layer.get_geometry(i)  # List of (x, y) tuples

            if not centroid_coords:
                logging.warning(f"Empty geometry at Centroids index {i}. Skipping.")
                continue

            # Create OGR Point geometry using the geometry function
            x, y = centroid_coords[0]
            point = create_point(x, y)

            matching_basins = []

            # Find all basins that contain the centroid point
            for j, (basin_geom, basin_attributes) in enumerate(basin_geometries):
                if contains(basin_geom, point):
                    matching_basins.append((j, basin_geom, basin_attributes))

            if not matching_basins:
                centroid_id = centroid_attributes.get("id", f"Index {i}")
                logging.warning(f"Centroid ID {centroid_id} at ({x}, {y}) is not contained within any basin polygon.")
                continue  # Skip this centroid or handle as needed

            if len(matching_basins) > 1:
                centroid_id = centroid_attributes.get("id", f"Index {i}")
                logging.error(
                    f"Centroid ID {centroid_id} at ({x}, {y}) "
                    f"is contained within multiple basins: {[idx for idx, _, _ in matching_basins]}. "
                    f"Associating with the first matching basin."
                )

            # Associate with the first matching basin
            associated_basin_idx, associated_basin_geom, associated_basin_attributes = matching_basins[0]

            # Calculate area using the geometry function
            area = calculate_area(associated_basin_geom)

            # Convert area to square kilometers if necessary (depends on CRS units)
            # For example, if units are in meters:
            area_km2 = area / 1e6  # Convert from square meters to square kilometers

            try:
                basin_id = centroid_attributes["id"]
                fi = centroid_attributes["fi"]
                basins.append(Basin(basin_id, x, y, area_km2, fi))
            except KeyError as e:
                logging.error(f"Missing expected field {e} in Centroids record {i}.")
                raise

        logging.info(f"Successfully built {len(basins)} Basin objects.")
        return basins

    def confluence(self, confluence_layer: VectorLayer) -> list[Confluence]:
        """
        Build the confluence objects.
        """
        # Validate the confluence vector layer with specific 'out' field validation
        if not self._validate_vector_layer(
            confluence_layer,
            "confluences",
            specific_validations=[validate_confluences_out_field],
        ):
            raise ValueError("Confluence vector layer validation failed.")

        confluences = []
        for i in range(len(confluence_layer)):
            attributes = confluence_layer.get_attributes(i)
            geometry_coords = confluence_layer.get_geometry(i)  # List of (x, y) tuples

            if not geometry_coords:
                logging.warning(f"Empty geometry at Confluences index {i}. Skipping.")
                continue

            # Assuming confluence is a point geometry with one coordinate
            x, y = geometry_coords[0]

            try:
                confluence_id = attributes["id"]
                out_field = attributes["out"]
                confluences.append(Confluence(confluence_id, x, y, bool(out_field)))
            except KeyError as e:
                logging.error(f"Missing expected field {e} in Confluences record {i}.")
                raise

        logging.info(f"Successfully built {len(confluences)} Confluence objects.")
        return confluences
