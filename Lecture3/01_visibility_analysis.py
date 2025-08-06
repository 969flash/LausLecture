import ghpythonlib.components as ghcomp
import Rhino.Geometry as geo
import time
import utils
import importlib

importlib.reload(utils)

# ## input = path_crv, obstacles,
# terrain_mesh = None  # geo.Mesh
# path_crv = None  # geo.Curve
# obstacles = None  # List[geo.Brep]

print("Start processing...")
start_time = time.time()
print("Processing time: {:.2f} seconds".format(time.time() - start_time))

points_on_path = ghcomp.DivideLength(path_crv, 50.0).points


def get_nearby_breps(obstacles, point, radius=50.0, tol=1.0):
    """
    Returns obstacles within (radius + tol) distance from the path curve.
    """
    obstacles_nearby = []
    for brep in obstacles:
        brep_closest_pt = brep.ClosestPoint(point)
        if brep_closest_pt:
            dist = point.DistanceTo(brep_closest_pt)
            if dist <= radius + tol:
                obstacles_nearby.append(brep)
    return obstacles_nearby


# 2. Generate IsoVist for each point
isovist_regions = []
for pt in points_on_path:
    # 지형에 분석 점 투영
    pt_on_mesh = utils.get_projected_pt_on_mesh(pt, terrain_mesh)
    # 투영된 점을 사람 눈높이 만큼 올리기
    pt_on_mesh.Z += 1.6  # Assuming eye level is 1.6 meters above the terrain

    nearby_obstacles = get_nearby_breps(obstacles, pt_on_mesh, radius=50.0)
    plane = geo.Plane(pt_on_mesh, geo.Vector3d.ZAxis)
    isovist = ghcomp.IsoVist(
        plane,
        100,  # count
        50.0,  # radius
        nearby_obstacles,  # obstacles: list of Breps and/or Meshes
    )

    iso_points = list(isovist.points)
    iso_region = geo.PolylineCurve(iso_points + [iso_points[0]])  # Close the polyline
    isovist_regions.append(iso_region)

print(
    "Finished processing. Total time: {:.2f} seconds".format(time.time() - start_time)
)
