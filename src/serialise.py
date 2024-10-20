# src/serialise.py
import json
import csv
import logging
import pyromb
from pyromb.core.attributes.basin import Basin
from pyromb.core.attributes.confluence import Confluence
from pyromb.core.attributes.reach import Reach
from pyromb.core.catchment import Catchment

# Set the default suffix
suffix_item = "_sample_new.json"


def serialize_to_json(data, filename: str, suffix: str = suffix_item) -> None:
    """
    Serializes data to a JSON file.

    Parameters:
        data: The data to serialize (e.g., dictionaries, lists).
        filename: The target JSON file name without suffix.
        suffix: The suffix to append to the filename.
    """
    try:
        with open(filename + suffix, "w") as f:
            json.dump(data, f, indent=4)
        logging.info(f"Serialized data to {filename + suffix}")
    except Exception as e:
        logging.error(f"Failed to serialize data to {filename + suffix}: {e}")
        print(data)


def serialize_object(obj, filename: str, suffix: str = suffix_item) -> None:
    """
    Serializes a custom object or list of objects to JSON.
    Converts each object to a dictionary using helper functions.

    Parameters:
        obj: The object or list of objects to serialize.
        filename: The target JSON file name without suffix.
        suffix: The suffix to append to the filename.
    """
    try:
        if isinstance(obj, list):
            # Determine the type of objects in the list and convert accordingly
            if len(obj) == 0:
                data = []
            else:
                first_item = obj[0]
                if isinstance(first_item, Reach):
                    data = [reach_to_dict(reach) for reach in obj]
                elif isinstance(first_item, Confluence):
                    data = [confluence_to_dict(conf) for conf in obj]
                elif isinstance(first_item, Basin):
                    data = [basin_to_dict(basin) for basin in obj]
                else:
                    data = obj  # Fallback: assume serializable
        elif hasattr(obj, "to_dict"):
            # If the object has a to_dict method, use it
            data = obj.to_dict()
        elif isinstance(obj, Catchment):
            data = catchment_to_dict(obj)
        else:
            data = obj.__dict__  # Fallback: attempt to use __dict__

        serialize_to_json(data, filename, suffix)
    except Exception as e:
        logging.error(f"Failed to serialize object to {filename + suffix}: {e}")


def serialize_matrix_to_csv(matrix, filename: str, suffix: str = suffix_item) -> None:
    """
    Serializes a matrix (list of lists) to a CSV file.

    Parameters:
        matrix: The matrix to serialize.
        filename: The target CSV file name without suffix.
        suffix: The suffix to append to the filename.
    """
    try:
        with open(filename + suffix, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(matrix)
        logging.info(f"Serialized matrix to {filename + suffix}")
    except Exception as e:
        logging.error(f"Failed to serialize matrix to {filename + suffix}: {e}")


def reach_to_dict(reach):
    """
    Converts a Reach object to a dictionary.
    """
    return {
        "name": reach.name,
        "type": reach.reachType.name,  # Convert Enum to string
        "slope": reach.slope,
        "vector": [{"x": point._x, "y": point._y} for point in reach._vector],
        # Accessing the internal _vector attribute
    }


def confluence_to_dict(confluence):
    """
    Converts a Confluence object to a dictionary.
    """
    return {
        "name": confluence.name,
        "isOut": confluence.isOut,  # Correct attribute
        # Add other relevant attributes here if necessary
    }


def basin_to_dict(basin):
    """
    Converts a Basin object to a dictionary.
    """
    return {
        "name": basin.name,
        "area": basin.area,
        "fi": basin.fi,
        # Add other relevant attributes here if necessary
    }


def catchment_to_dict(catchment):
    """
    Converts a Catchment object to a dictionary.
    """
    return {
        "edges": [reach.name for reach in catchment._edges],  # Assuming _edges is a list of Reach objects
        "vertices": [conf.name for conf in catchment._vertices],  # Assuming _vertices is a list of Confluence objects
        "incidenceMatrixDS": catchment._incidenceMatrixDS.tolist(),
        "incidenceMatrixUS": catchment._incidenceMatrixUS.tolist(),
        # Add other relevant attributes here if necessary
    }
