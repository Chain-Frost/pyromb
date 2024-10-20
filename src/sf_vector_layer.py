# src/sf_vector_layer.py

import pyromb
from osgeo import ogr


class SFVectorLayer(pyromb.VectorLayer):
    """
    Wrap the OGR layer with the necessary interface to work with the Builder.
    """

    def __init__(self, path: str) -> None:
        """
        Initialize the SFVectorLayer with the given shapefile path.

        Parameters
        ----------
        path : str
            The path to the shapefile.
        """
        self.path = path
        self.driver = ogr.GetDriverByName("ESRI Shapefile")
        self.datasource = self.driver.Open(path, 0)  # 0 means read-only
        if self.datasource is None:
            raise FileNotFoundError(f"Could not open shapefile: {path}")
        self.layer = self.datasource.GetLayer()

    def geometry(self, i: int) -> list:
        """
        Retrieve the geometry points for the ith feature.

        Parameters
        ----------
        i : int
            The index of the feature.

        Returns
        -------
        list
            A list of (x, y) tuples representing the geometry.
        """
        feature = self.layer.GetFeature(i)
        if feature is None:
            raise IndexError(f"Feature {i} not found in shapefile.")
        geom = feature.GetGeometryRef()
        if geom is None:
            raise ValueError(f"Feature {i} has no geometry.")

        geom_type = geom.GetGeometryType()
        points = []

        if geom_type == ogr.wkbPoint:
            points.append((geom.GetX(), geom.GetY()))
        elif geom_type in [ogr.wkbLineString, ogr.wkbMultiLineString]:
            points = geom.GetPoints()
        elif geom_type in [ogr.wkbPolygon, ogr.wkbMultiPolygon]:
            # Extract points from the exterior ring
            ring = geom.GetGeometryRef(0)
            if ring:
                points = ring.GetPoints()
            else:
                raise ValueError(f"Polygon geometry at feature {i} has no exterior ring.")
        else:
            raise ValueError(f"Unsupported geometry type: {geom_type} at feature {i}")

        return points

    def record(self, i: int) -> dict:
        """
        Retrieve the attributes for the ith feature.

        Parameters
        ----------
        i : int
            The index of the feature.

        Returns
        -------
        dict
            A dictionary of attribute names and their corresponding values.
        """
        feature = self.layer.GetFeature(i)
        if feature is None:
            raise IndexError(f"Feature {i} not found in shapefile.")

        field_count = feature.GetFieldCount()
        fields = [feature.GetFieldDefnRef(j).GetName() for j in range(field_count)]
        values = [feature.GetField(j) for j in range(field_count)]

        return dict(zip(fields, values))

    def __len__(self) -> int:
        """
        Get the number of features in the shapefile.

        Returns
        -------
        int
            The total number of features.
        """
        return self.layer.GetFeatureCount()

    def __del__(self):
        """
        Destructor to clean up the OGR datasource.
        """
        if self.datasource:
            self.datasource.Release()

    def get_fields(self) -> list[tuple[str, int]]:
        """
        Return field names and types for the vector layer.

        Returns
        -------
        List[Tuple[str, int]]
            A list of tuples containing field names and their OGR field type codes.
        """
        fields = []
        layer_defn = self.layer.GetLayerDefn()
        for i in range(layer_defn.GetFieldCount()):
            field_defn = layer_defn.GetFieldDefn(i)
            field_name = field_defn.GetName()
            field_type_code = field_defn.GetType()
            fields.append((field_name, field_type_code))
        return fields

    def get_ogr_geometry(self, i: int) -> ogr.Geometry:
        feature = self.layer.GetFeature(i)
        if feature is None:
            raise IndexError(f"Feature {i} not found in layer.")
        geometry = feature.GetGeometryRef()
        if geometry is None:
            raise ValueError(f"No geometry found for feature {i}.")
        return geometry.Clone()
