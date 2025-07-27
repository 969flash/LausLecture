import Rhino.Geometry as geo

sphere = geo.Sphere(geo.Point3d(0, 0, 0), 5)
brep = geo.Brep.CreateFromSphere(sphere)
xform = geo.Transform.Translation(10, 0, 0)
brep_x = brep.Duplicate()
brep_x.Transform(xform)
