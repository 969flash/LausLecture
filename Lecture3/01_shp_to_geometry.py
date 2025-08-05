# -*- coding:utf-8 -*-
from typing import List, Tuple, Optional
import ghpythonlib.components as ghcomp  # ignore
import os
import Rhino.Geometry as geo  # ignore
import utils
import importlib

importlib.reload(utils)

#########################
# bsh960flash@snu.ac.kr #
#########################

# Contour Divide Resolution(Higher value means more points in terrain mesh)
RESOLUTION = 4

# paths -> parameter of the component in grasshopper that is the path to the zip files

zip_paths = [os.path.join(os.path.dirname(__file__), "37608080.zip")]

# Main workflow
# Read shapefiles from zip
contour_shapes = utils.read_shapefiles_from_zip(
    zip_paths, ["N1L_F0010000", "N3L_F0010000"]
)
building_shapes = utils.read_shapefiles_from_zip(
    zip_paths, ["N1A_B0010000", "N3A_B0010000"]
)
road_region_shapes = utils.read_shapefiles_from_zip(zip_paths, ["N3A_A0010000"])
road_centerline_shapes = utils.read_shapefiles_from_zip(zip_paths, ["N3L_A0020000"])

# Extract data using utils functions
contour_data = utils.extract_data_from_shapefiles(contour_shapes)
building_data = utils.extract_data_from_shapefiles(building_shapes)
road_region_data = utils.extract_data_from_shapefiles(road_region_shapes)
road_centerline_data = utils.extract_data_from_shapefiles(road_centerline_shapes)

# Process contour using utils functions
contour_geometry_records = list(zip(contour_data.geometry, contour_data.records))
contour_curves = utils.create_contour_curves(contour_geometry_records)

# Process terrain
mesh_points = utils.create_points_for_mesh(contour_curves, RESOLUTION)
terrain_mesh = ghcomp.DelaunayMesh(mesh_points)

# Process buildings using utils functions
building_geometry_records = list(zip(building_data.geometry, building_data.records))
building_breps = utils.create_building_breps(building_geometry_records, terrain_mesh)

# Process road
road_region_curves = [data[0] for data in road_region_data.geometry]
road_centerline_curves = [data[0] for data in road_centerline_data.geometry]
