# app_testing.py
import os
import pyromb
from plot_catchment import plot_catchment
import logging
from sf_vector_layer import SFVectorLayer
from app import main

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Capture all levels of logs (DEBUG and above)
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
    # handlers=[logging.FileHandler("debug.log"), logging.StreamHandler()],  # Log to a file  # Also log to the console
)


# Define shapefile paths
DIR = os.path.dirname(__file__)
TEST_REACH_PATH = os.path.join(DIR, "../data", "reaches.shp")
TEST_BASIN_PATH = os.path.join(DIR, "../data", "basins.shp")
TEST_CENTROID_PATH = os.path.join(DIR, "../data", "centroids.shp")
TEST_CONFUL_PATH = os.path.join(DIR, "../data", "confluences.shp")

PARENT_DIR = os.path.dirname(DIR)  # This gets the parent folder of the current directory
TEST_OUTPUT_PATH = os.path.join(PARENT_DIR, r"./")
TEST_OUTPUT_NAME = r"testing_ogr_2.catg"
TEST_OUT = os.path.join(TEST_OUTPUT_PATH, TEST_OUTPUT_NAME)


def print_vector_layer_fields(vector_layer, name):
    """
    Print the field names of a vector layer using OGR.

    Parameters:
    - vector_layer: An instance of SFVectorLayer.
    - name: A string indicating the name of the layer.
    """
    # Access the layer definition
    layer_defn = vector_layer.layer.GetLayerDefn()
    # Get the field names
    field_names = [layer_defn.GetFieldDefn(i).GetName() for i in range(layer_defn.GetFieldCount())]
    print(f"{name} fields: {field_names}")


def test_main():
    ### Config ###
    plot = True  # Set to True if you want the catchment to be plotted
    serialise_for_testing = False
    model = pyromb.RORB()
    # Select your hydrology model, either pyromb.RORB() or pyromb.WBNM()

    ### Build Catchment Objects ###
    # Vector layers with test paths
    reach_vector = SFVectorLayer(TEST_REACH_PATH)
    basin_vector = SFVectorLayer(TEST_BASIN_PATH)
    centroid_vector = SFVectorLayer(TEST_CENTROID_PATH)
    confluence_vector = SFVectorLayer(TEST_CONFUL_PATH)

    # Print field names (optional, for debugging)
    print_vector_layer_fields(reach_vector, "Reach")
    print_vector_layer_fields(basin_vector, "Basin")
    print_vector_layer_fields(centroid_vector, "Centroid")
    print_vector_layer_fields(confluence_vector, "Confluence")

    ### Call the main function with test paths and parameters ###
    main(
        reach_path=TEST_REACH_PATH,
        basin_path=TEST_BASIN_PATH,
        centroid_path=TEST_CENTROID_PATH,
        confluence_path=TEST_CONFUL_PATH,
        output_name=TEST_OUT,
        plot=plot,
        model=model,
        serialise_for_testing=serialise_for_testing,
    )


if __name__ == "__main__":
    test_main()
