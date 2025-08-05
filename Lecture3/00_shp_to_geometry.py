# -*- coding:utf-8 -*-
from typing import List, Tuple, Optional
import zipfile
import shapefile
import Rhino.Geometry as geo
import ghpythonlib.components as ghcomp  # ignore

#########################
# bsh960flash@snu.ac.kr #
#########################


# Contour Divide Resolution(Higher value means more points in terrain mesh)
RESOLUTION = 4

# Shape type mapping
# This dictionary categorizes shape types based on their IDs as defined in the shapefile specification.
# The categories are 'point' and 'polyline', and the IDs represent different geometry types.
shape_types = {
    "point": [
        1,  # POINT
        8,  # MULTIPOINT
        11,  # POINTS
        18,  # MULTIPOINTZ
        21,  # POINTM
        28,  # MULTIPOINTM
    ],
    "polyline": [
        3,  # POLYLINE
        5,  # POLYGON
        13,  # POLYLINES
        15,  # POLYGONZ
        23,  # POLYLINEM
        25,  # POLYGONM
        31,  # MULTIPATCH
    ],
}


class ShapefileHandler:
    """
    A class to manage Shapefile operations.
    """

    def __init__(self, zip_paths: List[str]):
        self.zip_files = [zipfile.ZipFile(zip_path, "r") for zip_path in zip_paths]

    def read_shapefile(self, file_prefixes: List[str]) -> List[shapefile.Reader]:
        """
        Attempts to read shapefiles from the zip archives using a list of prefixes.
        """
        readers = []
        for zip_file in self.zip_files:
            for prefix in file_prefixes:
                try:
                    readers.append(
                        shapefile.Reader(
                            shp=zip_file.open(f"{prefix}.shp"),
                            shx=zip_file.open(f"{prefix}.shx"),
                            dbf=zip_file.open(f"{prefix}.dbf"),
                            prj=zip_file.open(f"{prefix}.prj"),
                        )
                    )
                except KeyError:
                    continue
        return readers

    def extract_data(self, shapefiles: List[shapefile.Reader]) -> "ShpData":
        """
        Extracts data from a list of shapefiles.
        """
        all_geometry = []
        all_fields = []
        all_field_names = []
        all_records = []
        shape_type = None

        for sf in shapefiles:
            result = ShapefileParser.read_shapefile(sf)
            if shape_type is None:
                shape_type = result[0]
            all_geometry.extend(result[1])
            all_fields.extend(result[2])
            all_field_names.extend(result[3])
            all_records.extend(result[4])

        return ShpData(
            shape_type, all_geometry, all_fields, all_field_names, all_records
        )


class ShpData:
    """
    A class to store Shapefile data.
    """

    def __init__(self, shape_type, geometry, fields, field_names, records):
        self.shape_type = shape_type
        self.geometry = geometry
        self.fields = fields
        self.field_names = field_names
        self.records = records


class ShapefileParser:
    """
    A class to handle parsing operations for shapefiles.
    """

    @staticmethod
    def find_type(shape_type):
        for key, values in shape_types.items():
            if shape_type in values:
                return key
        return None

    @staticmethod
    def read_shapefile(sf: shapefile.Reader, encoding="utf-8") -> Tuple:
        result_geom = []
        result_fields = []
        result_field_names = []
        result_records = []

        shape_type = ShapefileParser.find_type(sf.shapeType)

        # Extract field names
        for field in sf.fields:
            if field[0] != "DeletionFlag":
                _field = field[0]
                if isinstance(_field, bytes):
                    _field = _field.decode(encoding, errors="replace")
                result_field_names.append(_field)
                result_fields.append(field)

        # Extract geometry and records
        for shape, record in zip(sf.shapes(), sf.records()):
            geom = ShapefileParser.parse_geometry(shape, shape_type)
            result_geom.append(geom)
            _record = []
            for rec in record:
                if isinstance(rec, bytes):
                    _record.append(rec.decode(encoding, errors="replace"))
                else:
                    _record.append(rec)
            result_records.append(_record)

        return (
            shape_type,
            result_geom,
            result_fields,
            result_field_names,
            result_records,
        )

    @staticmethod
    def parse_geometry(shape, shape_type):
        if shape_type == "point":
            return [GeometryUtils.get_point_from_shape(pt) for pt in shape.points]
        elif shape_type == "polyline":
            parts = [
                shape.points[
                    shape.parts[i] : (
                        shape.parts[i + 1] if i + 1 < len(shape.parts) else None
                    )
                ]
                for i in range(len(shape.parts))
            ]
            return [
                geo.PolylineCurve(
                    [GeometryUtils.get_point_from_shape(pt) for pt in part]
                )
                for part in parts
            ]
        return []


class GeometryUtils:
    """
    A utility class for geometry-related operations.
    """

    @staticmethod
    def get_point_from_shape(pts):
        pts = list(pts)
        if len(pts) == 2:
            pts.append(0)
        return geo.Point3d(*pts)

    @staticmethod
    def get_vertices(curve):
        vertices = [
            curve.PointAt(curve.SpanDomain(i)[0]) for i in range(curve.SpanCount)
        ]
        if not curve.IsClosed:
            vertices.append(curve.PointAtEnd)
        return vertices

    @staticmethod
    def get_projected_pt_on_mesh(pt, mesh):
        for direction in [geo.Vector3d(0, 0, -1), geo.Vector3d(0, 0, 1)]:
            ray = geo.Ray3d(pt, direction)
            t = geo.Intersect.Intersection.MeshRay(mesh, ray)
            if t >= 0:
                return ray.PointAt(t)
        return None


class ContourProcessor:
    """
    A class to handle contour operations.
    """

    @staticmethod
    def create_contour_curves(contour_geometry_records):
        contour_crvs = []
        for contour_geom, contour_record in contour_geometry_records:
            contour_crvs.append(
                geo.PolylineCurve(
                    [
                        geo.Point3d(
                            contour_geom[0].Point(pt_count).X,
                            contour_geom[0].Point(pt_count).Y,
                            contour_record[1],
                        )
                        for pt_count in range(contour_geom[0].SpanCount)
                    ]
                )
            )
        return contour_crvs

    @staticmethod
    def create_points_for_mesh(contour_curves, resolution):
        points = []
        for curve in contour_curves:
            params = curve.DivideByLength(resolution, True)
            if params:
                points.extend([curve.PointAt(param) for param in params])
        return points


class BuildingProcessor:
    """
    A class to process building geometries.
    """

    @staticmethod
    def create_building_breps(building_geometry_records, mesh_terrain):
        breps = []
        for geom, record in building_geometry_records:
            base_curve = geom[0]
            height = record[5] * 3.5
            vertices = GeometryUtils.get_vertices(base_curve)

            projected_pts = [
                GeometryUtils.get_projected_pt_on_mesh(pt, mesh_terrain)
                for pt in vertices
            ]
            projected_pts = list(filter(None, projected_pts))

            if projected_pts:
                min_z = min(pt.Z for pt in projected_pts)
                base_curve.Translate(geo.Vector3d(0, 0, min_z - vertices[0].Z))
                breps.append(geo.Extrusion.Create(base_curve, -height, True))
        return breps


# paths -> parameter of the component in grasshopper that is the path to the zip files

# Main workflow
handler = ShapefileHandler(paths)
contour_shapes = handler.read_shapefile(["N1L_F0010000", "N3L_F0010000"])
building_shapes = handler.read_shapefile(["N1A_B0010000", "N3A_B0010000"])
road_region_shapes = handler.read_shapefile(["N3A_A0010000"])
road_centerline_shapes = handler.read_shapefile(["N3L_A0020000"])

# Extract data
contour_data = handler.extract_data(contour_shapes)
building_data = handler.extract_data(building_shapes)
road_region_data = handler.extract_data(road_region_shapes)
road_centerline_data = handler.extract_data(road_centerline_shapes)

# Process contour
contour_geometry_records = list(zip(contour_data.geometry, contour_data.records))
contour_curves = ContourProcessor.create_contour_curves(contour_geometry_records)

# Process terrain
mesh_points = ContourProcessor.create_points_for_mesh(contour_curves, RESOLUTION)
terrain_mesh = ghcomp.DelaunayMesh(mesh_points)

# Process buildings
building_geometry_records = list(zip(building_data.geometry, building_data.records))
building_breps = BuildingProcessor.create_building_breps(
    building_geometry_records, terrain_mesh
)

# Process road
road_region_curves = [data[0] for data in road_region_data.geometry]
road_centerline_curves = [data[0] for data in road_centerline_data.geometry]
