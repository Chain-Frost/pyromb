# src\pyromb\core\gis\vector_layer.py
import abc
from typing import Any
from osgeo import ogr


class VectorLayer(abc.ABC):
    """
    Interface for reading shapefiles.

    Used by the Builder to access the geometry and attributes of the
    shapefile to build the catchment objects. Given the various ways a shapefile can
    be read, the VectorLayer Class wrappes the functionality of reading the shapefile
    by the chosen library in a consistent interface to be used by the builder.
    """

    @abc.abstractmethod
    def geometry(self, i: int) -> list[tuple[float, float]]:
        """
        Method to access the geometry of the ith vector in the shapefile.

        Return the geometry as a list of (x,y) tuples.

        Parameters
        ----------
        i : int
            The index of the vector to return the geometry for.

        Returns
        -------
        list
            List of x,y co-ordinates tuples
        """
        pass

    @abc.abstractmethod
    def record(self, i: int) -> dict[str, Any]:
        """
        Method to access the attributes of the ith vector in the shapefile.

        Return the set of attributes as a dictionary.

        Parameters
        ----------
        i : int
            The index of the vector to return the attributes of.

        Returns
        -------
        dict
            key:value pair of the attributes.
        """
        pass

    @abc.abstractmethod
    def __len__(self) -> int:
        """The number of vectors in the shapefile.

        Returns
        -------
        int
            Vectors in the shapefile.
        """
        pass

    def get_geometry(self, i: int) -> list[tuple[float, float]]:
        """
        Returns the geometry of the ith vector as a list of (x, y) tuples.
        Default implementation assumes geometry(i) returns this format.
        Subclasses can override this method if necessary.
        """
        return self.geometry(i)

    def get_attributes(self, i: int) -> dict[str, Any]:
        """
        Returns the attributes of the ith vector as a dictionary.
        Default implementation assumes record(i) returns a dict-like object.
        Subclasses can override this method for custom behavior.
        """
        record = self.record(i)
        if isinstance(record, dict):
            return record
        else:
            raise TypeError(f"Not expected type: {record}")

    def get_fields(self) -> list[tuple[str, int]]:
        """
        Return field names and types for the vector layer.

        This method assumes the layer provides access to its field names and types.
        Subclasses should implement this if it is required by the validation logic.

        Returns
        -------
        List of tuples containing field names and types.
        """
        raise NotImplementedError("Subclasses must implement get_fields() if needed.")

    # @abc.abstractmethod
    # def get_ogr_geometry(self, i: int) -> ogr.Geometry:
    #     """Return the OGR geometry object for the ith feature."""
    #     pass
