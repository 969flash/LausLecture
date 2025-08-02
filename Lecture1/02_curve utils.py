import Rhino.Geometry as geo

# 1 교차하는 두 커브 생성
pts1 = [geo.Point3d(0, 0, 0), geo.Point3d(5, 5, 0)]
pts2 = [geo.Point3d(0, 5, 0), geo.Point3d(5, 0, 0)]
curve1 = geo.PolylineCurve(pts1)
curve2 = geo.PolylineCurve(pts2)

# 2 교차점 계산

intersection = geo.Intersect.Intersection.CurveCurve(curve1, curve2, 0.01, 0.01)
