# src\pyromb\core\geometry\shapefile_validation.py
import logging
from osgeo import ogr  # type: ignore
from ..gis.vector_layer import VectorLayer


def validate_shapefile_geometries(vector_layer: VectorLayer, layer_type: str) -> bool:
    """
    Validate the geometries of a vector layer based on the expected geometry type for the layer.

    Parameters
    ----------
    vector_layer : VectorLayer
        The vector layer to validate.
    layer_type : str
        The type of layer (e.g., 'reaches', 'basins', 'confluences', 'centroids').

    Returns
    -------
    bool
        True if all geometries are valid and match the expected type, False otherwise.
    """
    validation_passed = True
    layer_name = layer_type.capitalize()

    # Define expected geometry types for each layer type
    expected_geometry_types = {
        "reaches": ogr.wkbLineString,
        "basins": ogr.wkbPolygon,
        "confluences": ogr.wkbPoint,
        "centroids": ogr.wkbPoint,
    }

    # Get the expected geometry type for the layer
    expected_geom_type = expected_geometry_types.get(layer_type.lower())

    if expected_geom_type is None:
        logging.error(f"No expected geometry type defined for layer '{layer_type}'.")
        return False

    logging.info(
        f"Validating geometries for {layer_name} layer. Expected geometry type: {ogr.GeometryTypeToName(expected_geom_type)}"
    )

    for i in range(len(vector_layer)):
        # Get the geometry from the vector layer
        ogr_geom = vector_layer.get_ogr_geometry(i)
        if ogr_geom is None or ogr_geom.IsEmpty():
            logging.error(f"Feature at index {i} has an empty geometry.")
            validation_passed = False
            continue

        # Check if geometry is valid
        if not ogr_geom.IsValid():
            logging.error(f"Feature at index {i} has an invalid geometry.")
            validation_passed = False
            continue

        # Get the actual geometry type
        actual_geom_type = ogr_geom.GetGeometryType()

        # Handle multi-geometries
        if actual_geom_type in (
            ogr.wkbMultiPoint,
            ogr.wkbMultiLineString,
            ogr.wkbMultiPolygon,
            ogr.wkbMultiPoint25D,
            ogr.wkbMultiLineString25D,
            ogr.wkbMultiPolygon25D,
        ):
            num_geoms = ogr_geom.GetGeometryCount()
            if num_geoms == 1:
                logging.warning(f"Feature at index {i} is a multi-geometry with a single geometry. Proceeding.")
                # Extract the single geometry
                ogr_geom = ogr_geom.GetGeometryRef(0)
                actual_geom_type = ogr_geom.GetGeometryType()
            else:
                logging.error(
                    f"Feature at index {i} is a multi-geometry with {num_geoms} geometries. Expected only one."
                )
                validation_passed = False
                continue

        # Check if actual geometry type is acceptable, ignoring 2D vs 3D
        if not are_geometry_types_equivalent(expected_geom_type, actual_geom_type):
            expected_geom_name = ogr.GeometryTypeToName(expected_geom_type)
            actual_geom_name = ogr.GeometryTypeToName(actual_geom_type)
            logging.error(
                f"Feature at index {i} has geometry type '{actual_geom_name}', " f"but expected '{expected_geom_name}'."
            )
            validation_passed = False
            continue

    if validation_passed:
        logging.info(f"All geometries in {layer_name} layer are valid and match the expected type.")
    else:
        logging.error(f"Geometry validation failed for {layer_name} layer.")

    return validation_passed


def are_geometry_types_equivalent(expected_geom_type, actual_geom_type):
    """
    Determine if the actual geometry type is acceptable for the expected geometry type,
    ignoring the 2D vs 3D distinction.
    """
    # Remove the 3D flag if present
    expected_geom_type_2d = expected_geom_type & (~ogr.wkb25DBit)
    actual_geom_type_2d = actual_geom_type & (~ogr.wkb25DBit)

    # Map multi-geometry types to their single counterparts
    multi_to_single = {
        ogr.wkbMultiPoint: ogr.wkbPoint,
        ogr.wkbMultiLineString: ogr.wkbLineString,
        ogr.wkbMultiPolygon: ogr.wkbPolygon,
    }

    # If actual is a multi-geometry, map it to the single geometry type
    if actual_geom_type_2d in multi_to_single:
        # For multi-geometries, check if expected type matches the single type
        actual_geom_type_2d = multi_to_single[actual_geom_type_2d]

    # Similarly, if expected is a multi-geometry, map it to single type
    if expected_geom_type_2d in multi_to_single:
        expected_geom_type_2d = multi_to_single[expected_geom_type_2d]

    return expected_geom_type_2d == actual_geom_type_2d


def validate_shapefile_fields(
    vector_layer: VectorLayer, shapefile_name: str, expected_fields: list[dict[str, str]]
) -> bool:
    """
    Validate the fields of a vector layer against expected field names and types.

    Parameters
    ----------
    vector_layer : VectorLayer
        The vector layer to validate.
    shapefile_name : str
        The name of the shapefile for logging.
    expected_fields : list[dict[str, str]]
        A list of expected field definitions with name and type.

    Returns
    -------
    bool
        True if all expected fields are present and valid, False otherwise.
    """
    validation_passed = True

    logging.info(f"Starting field validation for {shapefile_name} layer.")

    # Get the actual fields and their types from the vector layer
    actual_fields = vector_layer.get_fields()  # Call the method to get field names and types

    # Normalize actual field names to lowercase for case-insensitive comparison
    actual_field_names = [field[0].lower() for field in actual_fields]
    actual_field_types = {field[0].lower(): field[1] for field in actual_fields}

    logging.info(f"Expected fields for {shapefile_name}:")
    for exp_field in expected_fields:
        logging.info(f"  Field Name: {exp_field['name']}, Expected Type: {exp_field['type']}")

    logging.info(f"Actual fields in {shapefile_name}:")
    for name, type_code in actual_fields:
        type_name = ogr.GetFieldTypeName(type_code)
        logging.info(f"  Field Name: {name}, Type: {type_name}")

    # Define acceptable type mappings
    type_mappings = {
        "Integer": ["Integer", "Integer64"],
        "Integer64": ["Integer", "Integer64"],
        "Real": ["Real"],
        "String": ["String"],
    }

    # Validate field names and types
    for exp_field in expected_fields:
        exp_name = exp_field["name"].lower()
        exp_type = exp_field["type"]

        if exp_name not in actual_field_names:
            logging.error(f"Missing expected field '{exp_field['name']}' in {shapefile_name}.")
            validation_passed = False
        else:
            actual_type_code = actual_field_types[exp_name]
            actual_type_name = ogr.GetFieldTypeName(actual_type_code)
            # Get acceptable types for expected type
            acceptable_types = type_mappings.get(exp_type, [exp_type])
            if actual_type_name not in acceptable_types:
                logging.error(
                    f"Type mismatch for field '{exp_field['name']}' in {shapefile_name}: "
                    f"Expected '{exp_type}', Got '{actual_type_name}'"
                )
                validation_passed = False
            else:
                logging.info(f"Field '{exp_field['name']}' in {shapefile_name} matches expected type '{exp_type}'.")

    # Data integrity validation (e.g., missing or empty values)
    if validation_passed:
        logging.info(f"Field names and types validated successfully for {shapefile_name}.")
        validation_passed = validate_field_data_integrity(vector_layer, shapefile_name, expected_fields)
        if validation_passed:
            logging.info(f"Field data integrity validated successfully for {shapefile_name}.")
        else:
            logging.error(f"Field data integrity validation failed for {shapefile_name}.")
    else:
        logging.error(f"Field names or types validation failed for {shapefile_name}.")

    return validation_passed


def validate_field_names_and_types(
    shapefile_name: str, expected_fields: list[dict[str, str]], actual_fields: list[tuple[str, int]]
) -> bool:
    """
    Validate the field names and types against the expected fields.

    Parameters
    ----------
    shapefile_name : str
        The name of the shapefile for logging purposes.
    expected_fields : list of dict
        List of expected field names and types.
    actual_fields : list of tuple
        List of (field_name, field_type_code) from the vector layer.

    Returns
    -------
    bool
        True if all expected fields are present with correct types, False otherwise.
    """
    actual_field_names = [field[0] for field in actual_fields]
    actual_field_types = {field[0]: field[1] for field in actual_fields}

    validation_passed = True

    for exp_field in expected_fields:
        exp_name = exp_field["name"]
        exp_type = exp_field["type"]

        if exp_name not in actual_field_names:
            logging.error(f"Missing expected field '{exp_name}' in {shapefile_name}.")
            validation_passed = False
        else:
            actual_type_code = actual_field_types[exp_name]
            actual_type_name = ogr.GetFieldTypeName(actual_type_code)

            if actual_type_name != exp_type:
                logging.error(
                    f"Type mismatch for field '{exp_name}' in {shapefile_name}: "
                    f"Expected '{exp_type}', Got '{actual_type_name}'"
                )
                validation_passed = False

    return validation_passed


def validate_field_data_integrity(
    vector_layer: VectorLayer, shapefile_name: str, expected_fields: list[dict[str, str]]
) -> bool:
    """
    Validate the data integrity of required fields in the vector layer.

    Parameters
    ----------
    vector_layer : VectorLayer
        The vector layer to validate.
    shapefile_name : str
        The name of the shapefile for logging purposes.
    expected_fields : list of dict
        List of expected field names and types.

    Returns
    -------
    bool
        True if all required fields contain valid data, False otherwise.
    """
    validation_passed = True
    logging.info(f"Validating data integrity for fields in {shapefile_name}...")

    for i in range(len(vector_layer)):
        fid = i  # Assume vector layer uses index as feature ID
        for exp_field in expected_fields:
            exp_name = exp_field["name"]
            value = vector_layer.get_attributes(i).get(exp_name)

            if value is None:
                logging.error(f"None value found in field '{exp_name}' for Feature ID {fid} in {shapefile_name}.")
                validation_passed = False
            elif isinstance(value, str) and not value.strip():
                logging.error(f"Empty string found in field '{exp_name}' for Feature ID {fid} in {shapefile_name}.")
                validation_passed = False

    return validation_passed


def validate_confluences_out_field(vector_layer: VectorLayer, shapefile_name: str) -> bool:
    """
    Validate that the 'out' field in the confluences vector layer has exactly one '1' and the rest '0'.

    Parameters
    ----------
    vector_layer : VectorLayer
        The vector layer to validate.
    shapefile_name : str
        The name of the shapefile for logging purposes.

    Returns
    -------
    bool: True if the validation passes, False otherwise.
    """
    validation_passed = True

    out_values = [vector_layer.get_attributes(i).get("out") for i in range(len(vector_layer))]

    count_ones = out_values.count(1)
    count_zeros = out_values.count(0)
    total_records = len(out_values)

    if count_ones != 1:
        logging.error(f"The 'out' field in {shapefile_name} should have exactly one '1'. Found {count_ones}.")
        validation_passed = False

    if count_zeros != (total_records - 1):
        logging.error(f"The 'out' field in {shapefile_name} should have {total_records - 1} '0's. Found {count_zeros}.")
        validation_passed = False

    if validation_passed:
        logging.info(f"'out' field validation passed for {shapefile_name}: 1 '1' and {count_zeros} '0's.")
    else:
        logging.error(f"'out' field validation failed for {shapefile_name}.")

    return validation_passed


def load_points(vector_layer: VectorLayer) -> list[ogr.Geometry]:
    """
    Load point geometries from a vector layer.

    Parameters
    ----------
    vector_layer : VectorLayer
        The vector layer to extract point geometries from.

    Returns
    -------
    List[ogr.Geometry]
        List of point geometries.
    """
    points = []
    for i in range(len(vector_layer)):
        geom_coords = vector_layer.get_geometry(i)
        if len(geom_coords) == 1:  # Assuming point geometries have one coordinate
            x, y = geom_coords[0]
            point = ogr.Geometry(ogr.wkbPoint)
            point.AddPoint(x, y)
            points.append(point)
        else:
            logging.error(f"Invalid point geometry at index {i} in vector layer.")
    return points
