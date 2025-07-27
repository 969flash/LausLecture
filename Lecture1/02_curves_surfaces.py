import Rhino.Geometry as geo

pts = [geo.Point3d(i, i * i * 0.1, 0) for i in range(-5, 6)]
curve = geo.NurbsCurve.Create(False, 3, pts)

rail = geo.Line(geo.Point3d(0, 0, 0), geo.Point3d(0, 0, 10)).ToNurbsCurve()
surface = geo.Surface.CreateExtrusion(curve, geo.Vector3d(0, 0, 5))
