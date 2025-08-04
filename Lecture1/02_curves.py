import Rhino.Geometry as geo

# 1. 기본적은 폴리라인 커브 생성
pts = [geo.Point3d(i, i * i * 0.1, 0) for i in range(-5, 6)]
base_crv = geo.PolylineCurve(pts)

# 커브의 길이 계산
length = base_crv.GetLength()
print("Length of the curve:", length)

# 2. 커브를 닫아서 루프 생성
# 커브를 닫기 위해 첫번째 점을 마지막에 추가
closed_crv = geo.PolylineCurve(pts + [pts[0]])

# 3. 커브의 닫힘 여부 확인
print("Is the curve closed?", closed_crv.IsClosed)

# 4. 커브의 면적 계산
area = geo.AreaMassProperties.Compute(closed_crv).Area
print("Area of the closed curve:", area)

# 5. 커브의 제어점 수 출력
print("Number of control points:", closed_crv.PointCount)

# 6. 커브의 모서리 수 출력
print("Number of span counts:", closed_crv.SpanCount)

# Nurbs 곡선 커브 생성
nurbs_crv = geo.NurbsCurve.CreateControlPointCurve(pts, 3)
