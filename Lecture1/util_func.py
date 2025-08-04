import Rhino.Geometry as geo

TOL = 0.01  # 기본 허용 오차
ROUNDING_PRECISION = 6  # 반올림 소수점 자리수


def get_dist_between_pts(
    pt_a: geo.Point3d, pt_b: geo.Point3d, rounding_precision=ROUNDING_PRECISION
):
    """
    두 점 사이의 거리 계산
    :param pt_a: Rhino.Geometry.Point3d 객체
    :param pt_b: Rhino.Geometry.Point3d 객체
    :param rounding_precision: 거리 반올림 소수점 자리수
    :return: 거리 (float)
    """
    return round(pt_a.DistanceTo(pt_b), rounding_precision)


def has_intersection(
    crv_a: geo.Curve, crv_b: geo.Curve, plane=geo.Plane.WorldXY, tol=TOL
):
    """
    두 커브가 교차하는지 여부를 확인
    :param curve_a: Rhino.Geometry.Curve 객체
    :param curve_b: Rhino.Geometry.Curve 객체
    :return: 교차 여부 (bool)
    """
    return geo.Curve.PlanarCurveCollision(crv_a, crv_b, plane, tol)


## 커브간의 교차 점 생성
def get_intersection_from_crvs(crv_a: geo.Curve, crv_b: geo.Curve, tol=TOL):
    """
    두 커브 사이의 교차점 계산
    :param curve_a: Rhino.Geometry.Curve 객체
    :param curve_b: Rhino.Geometry.Curve 객체
    :param tol: 허용 오차
    :return: 교차점 리스트 (list of Point3d)
    """
    intersections = geo.Intersect.Intersection.CurveCurve(crv_a, crv_b, tol, tol)

    # 교차점이 없을 경우 빈 리스트 반환
    if not intersections:
        return []

    return [pt.PointA for pt in intersections if pt.IsPointAValid]


## 커브간의 점간의 거리 계산
def get_dist_between_crvs(
    crv_a: geo.Curve, crv_b: geo.Curve, rounding_precision=ROUNDING_PRECISION
):
    """
    두 커브 사이의 최소 거리 계산
    :param curve_a: Rhino.Geometry.Curve 객체
    :param curve_b: Rhino.Geometry.Curve 객체
    :param rounding_precision: 거리 반올림 소수점 자리수
    :return: 최소 거리 (float)
    """
    _, a, b = crv_a.ClosestPoints(crv_b)
    dist = a.DistanceTo(b)
    return round(dist, rounding_precision)
