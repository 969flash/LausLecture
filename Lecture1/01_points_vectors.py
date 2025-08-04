import Rhino.Geometry as geo

# 기본 점 생성
base_pt = geo.Point3d(0, 0, 0)

# 점의 X 좌표 출력
print(base_pt.X)

# 점간의 거리 계산
test_pt = geo.Point3d(3, 4, 0)
print(base_pt.DistanceTo(test_pt))

# 점의 좌표 유사성 판단
print(base_pt.EpsilonEquals(test_pt, 0.01))

# 벡터 생성
vec = geo.Vector3d(10, 5, 3)

# 벡터의 길이 출력
print("Length of the vector:", vec.Length)

# 벡터를 사용하여 점 이동
moved_pt = base_pt + vec
