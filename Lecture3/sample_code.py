import ghpythonlib.components as ghcomp
import Rhino.Geometry as geo


points = ghcomp.DivideLength(curve, 50).points

planes = [ghcomp.XYPlane(point) for point in points]


iso_regions = []
for plane in planes:
    iso_points = ghcomp.Isoview(plane, 20, 50, obstacles).points
    iso_region = geo.PolylineCurve(iso_points + [iso_points[0]])
    iso_regions.append(iso_region)
