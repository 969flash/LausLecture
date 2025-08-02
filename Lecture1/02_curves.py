import Rhino.Geometry as geo

# 1. 기본적은 폴리라인 커브 생성
pts = [geo.Point3d(i, i * i * 0.1, 0) for i in range(-5, 6)]
base_crv = geo.PolylineCurve(pts)

# 2. 커브를 닫아서 루프 생성
base_crv.MakeClosed()

# 커브의 길이 계산
length = base_crv.GetLength()
print("Length of the curve:", length)


# 커브의 면적 계산
area = geo.AreaMassProperties.Compute(base_crv).Area
print("Area of the closed curve:", area)

# 3. 커브의 제어점 출력
print("Number of control points:", base_crv.PointCount)

# 4. 커브의 닫힘 여부 확인
print("Is the curve closed?", base_crv.IsClosed)
