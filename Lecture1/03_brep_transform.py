import Rhino.Geometry as geo


# 1. 닫힌 커브로부터 평면 서페이스 생성
pts = [
    geo.Point3d(1, 1, 1),
    geo.Point3d(2, 2, 2),
    geo.Point3d(3, 1, 1),
    geo.Point3d(2, 0, 0),
    geo.Point3d(1, 1, 1),
]
base_region = geo.PolylineCurve(pts)
print(base_region.IsClosed)

surface = geo.Brep.CreatePlanarBreps(base_region)[0]


# 2. 레일을 따라 선형 돌출 생성
rail_crv = geo.Line(geo.Point3d(0, 0, 0), geo.Point3d(10, 0, 0)).ToNurbsCurve()
extrusion = geo.Surface.CreateExtrusion(rail_crv, geo.Vector3d(0, 0, 5))

# 3. 구면을 생성하고 변환 적용
sphere = geo.Sphere(geo.Point3d(0, 0, 0), 5)
brep = geo.Brep.CreateFromSphere(sphere)
xform = geo.Transform.Translation(10, 0, 0)
brep_x = brep.Duplicate()
brep_x.Transform(xform)

## 오늘 수엄 여기까지
