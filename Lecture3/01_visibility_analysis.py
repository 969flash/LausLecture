import ghpythonlib.components as ghcomp
import Rhino.Geometry as geo
import time


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
    nearby_obstacles = get_nearby_breps(obstacles, pt, radius=50.0)
    plane = geo.Plane(pt, geo.Vector3d.ZAxis)
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
