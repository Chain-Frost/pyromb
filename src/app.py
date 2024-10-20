# src/app.py
import os
import pyromb
from plot_catchment import plot_catchment
from sf_vector_layer import SFVectorLayer
import logging
from typing import Any, Optional
from serialise import serialize_object, serialize_matrix_to_csv

# Configure logging
# logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Define shapefile paths
DIR = os.path.dirname(__file__)
REACH_PATH = os.path.join(DIR, "../data", "reaches.shp")
BASIN_PATH = os.path.join(DIR, "../data", "basins.shp")
CENTROID_PATH = os.path.join(DIR, "../data", "centroids.shp")
CONFUL_PATH = os.path.join(DIR, "../data", "confluences.shp")


def main(
    output_name: Optional[str] = None,
    reach_path: str = REACH_PATH,
    basin_path: str = BASIN_PATH,
    centroid_path: str = CENTROID_PATH,
    confluence_path: str = CONFUL_PATH,
    model: Any = pyromb.RORB(),
    plot: bool = False,
    serialise_for_testing: bool = False,
) -> None:
    """
    Main function to build and process catchment data.

    Parameters
    ----------
    output_name : Optional[str]
        Name of the output file. If not provided, a default name is assigned based on the model.
    reach_path : str, optional
        Path to the reaches shapefile. Defaults to REACH_PATH.
    basin_path : str, optional
        Path to the basins shapefile. Defaults to BASIN_PATH.
    centroid_path : str, optional
        Path to the centroids shapefile. Defaults to CENTROID_PATH.
    confluence_path : str, optional
        Path to the confluences shapefile. Defaults to CONFUL_PATH.
    plot : bool, optional
        Whether to plot the catchment. Defaults to False.
    model :
        The hydrology model to use. Defaults to pyromb.RORB().
    """

    # Assign default output name based on the model type
    if isinstance(model, pyromb.RORB):
        default_output = os.path.join(DIR, "../vector.catg")
    else:
        default_output = os.path.join(DIR, "../runfile.wbnm")
    output_name = output_name or default_output

    ### Build Catchment Objects ###
    try:
        # Initialize vector layers using OGR
        reach_vector = SFVectorLayer(reach_path)
        basin_vector = SFVectorLayer(basin_path)
        centroid_vector = SFVectorLayer(centroid_path)
        confluence_vector = SFVectorLayer(confluence_path)
        logging.info("Successfully loaded all shapefile layers.")
    except (FileNotFoundError, IndexError, ValueError) as e:
        logging.error(f"Failed to load shapefile layers: {e}")
        return
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading shapefiles: {e}")
        return

    # Create the builder
    try:
        builder = pyromb.Builder()
        logging.info("Builder initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize Builder: {e}")
        return

    # Build catchment components
    try:
        tr = builder.reach(reach_vector)
        logging.info("Built reaches.")
        tc = builder.confluence(confluence_vector)
        logging.info("Built confluences.")
        tb = builder.basin(centroid_vector, basin_vector)
        logging.info("Built basins.")
        logging.info("Catchment components built successfully.")

        # Serialize components if flag is set
        if serialise_for_testing:
            serialize_object(tr, "reach")
            # Serializes to "reach_new.json" or "reach_old.json" based on serialise.py copy
            serialize_object(tc, "confluence")  # Serializes to "confluence_new.json" or "confluence_old.json"
            serialize_object(tb, "basin")  # Serializes to "basin_new.json" or "basin_old.json"
            logging.info("Serialized reaches, confluences, and basins.")
    except Exception as e:
        logging.error(f"Failed to build catchment components: {e}")
        return

    ### Create the catchment ###
    try:
        catchment = pyromb.Catchment(tc, tb, tr)
        connected = catchment.connect()
        logging.info("Catchment created and connected successfully.")

        # Serialize catchment if flag is set
        if serialise_for_testing:
            serialize_object(catchment, "catchment")
            # Serializes to "catchment_new.json" or "catchment_old.json"
            logging.info("Serialized catchment.")
    except Exception as e:
        logging.error(f"Failed to create and connect catchment: {e}")
        return

    # Connect the catchment and serialize connection matrices
    try:
        ds_matrix, us_matrix = catchment.connect()
        if serialise_for_testing:
            serialize_matrix_to_csv(ds_matrix.tolist(), "ds_matrix")
            # Serializes to "ds_matrix_new.json" or "ds_matrix_old.json"
            serialize_matrix_to_csv(us_matrix.tolist(), "us_matrix")
            # Serializes to "us_matrix_new.json" or "us_matrix_old.json"
            logging.info("Serialized connection matrices.")
    except Exception as e:
        logging.error(f"Failed to connect catchment or serialize connection matrices: {e}")
        return

    # Create the traveller and pass the catchment.
    try:
        traveller = pyromb.Traveller(catchment)
        logging.info("Traveller created successfully.")
    except Exception as e:
        logging.error(f"Failed to create Traveller: {e}")
        return

    ### Write ###
    try:
        with open(output_name, "w") as f:
            f.write(traveller.getVector(model))
        logging.info(f"Output written to {output_name}")
    except Exception as e:
        logging.error(f"Failed to write output: {e}")
        return

    ### Plot the catchment ###
    if plot:
        try:
            plot_catchment(connected, tr, tc, tb)
            logging.info("Catchment plotted successfully.")
        except Exception as e:
            logging.error(f"Failed to plot catchment: {e}")


if __name__ == "__main__":
    main()
