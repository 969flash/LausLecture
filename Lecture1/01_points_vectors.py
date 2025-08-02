import Rhino.Geometry as geo

base_pt = geo.Point3d(0, 0, 0)
vec = geo.Vector3d(10, 5, 3)
moved_pt = base_pt + vec
