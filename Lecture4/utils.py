from typing import List, Tuple, Any, Optional, Union
import Rhino.Geometry as geo
import Rhino
import functools

import ghpythonlib.components as ghcomp

TOL = 0.01  # 기본 허용 오차
DIST_TOL = 0.01
AREA_TOL = 0.1
OP_TOL = 0.00001
CLIPPER_TOL = 0.0000000001
BIGNUM = 100000
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


def explode_curve(crv: geo.Curve) -> List[geo.Curve]:
    """
    커브를 분할하여 개별 세그먼트로 나눈다.
    :param curve: Rhino.Geometry.Curve 객체
    :return: 분할된 커브 리스트 (list of Curve)
    """
    if not crv:
        return []

    # span이 1개면 추가적인 연산 필요 없다.
    if crv.SpanCount == 1:
        return [crv]

    segments = []
    for i in range(crv.SpanCount):
        param_start, param_end = crv.SpanDomain(i)
        pt_seg_start = crv.PointAt(param_start)
        pt_seg_end = crv.PointAt(param_end)
        segments.append(geo.LineCurve(pt_seg_start, pt_seg_end))

    return segments


def has_region_intersection(
    region: geo.Curve, other_region: geo.Curve, tol: float = TOL
) -> bool:
    """영역 커브와 다른 영역 커브가 교차하는지 확인한다.
    Args:
        region: 영역 커브
        other_regions: 다른 영역 커브 리스트
        tol: tolerance

    Returns:
        bool: 교차 여부
    """
    relationship = geo.Curve.PlanarClosedCurveRelationship(
        region, other_region, geo.Plane.WorldXY, tol
    )
    # 완전히 떨어져 있는 경우. 닿은 부분 없이.
    if relationship == geo.RegionContainment.Disjoint:
        return False
    return True


def get_dist_between_pt_and_crv(
    pt: geo.Point3d, crv: geo.Curve, rounding_precision=ROUNDING_PRECISION
) -> float:
    """
    주어진 점과 커브 사이의 거리 계산
    :param pt: Rhino.Geometry.Point3d 객체
    :param crv: Rhino.Geometry.Curve 객체
    :param rounding_precision: 거리 반올림 소수점 자리수
    :return: 거리 (float)
    """
    dist = pt.DistanceTo(crv.PointAt(crv.ClosestPoint(pt)[1]))
    dist = round(dist, rounding_precision)
    return dist


def is_region_inside_region(
    region: geo.Curve, other_region: geo.Curve, tol: float = TOL
) -> bool:
    """영역 커브가 다른 영역 커브 내부에 있는지 확인한다.
    Args:
        region: 영역 커브
        other_region: 다른 영역 커브
        tol: tolerance
    Returns:
        bool: 내부 여부
    """

    relationship = geo.Curve.PlanarClosedCurveRelationship(
        region, other_region, geo.Plane.WorldXY, tol
    )
    # region이 other_region 내부에 있는 경우
    if relationship == geo.RegionContainment.AInsideB:
        return True
    return False


def offset_regions_inward(
    regions: Union[geo.Curve, List[geo.Curve]], dist: float, miter: int = BIGNUM
) -> List[geo.Curve]:
    """영역 커브를 안쪽으로 offset 한다.
    단일커브나 커브리스트 관계없이 커브 리스트로 리턴한다.
    Args:
        region: offset할 대상 커브
        dist: offset할 거리

    Returns:
        offset 후 커브
    """

    if not dist:
        return regions
    return Offset().polyline_offset(regions, dist, miter).holes


def offset_regions_outward(
    regions: Union[geo.Curve, List[geo.Curve]], dist: float, miter: int = BIGNUM
) -> List[geo.Curve]:
    """영역 커브를 바깥쪽으로 offset 한다.
    단일커브나 커브리스트 관계없이 커브 리스트로 리턴한다.
    Args:
        region: offset할 대상 커브
        dist: offset할 거리
    returns:
        offset 후 커브
    """
    if isinstance(regions, geo.Curve):
        regions = [regions]

    return [offset_region_outward(region, dist, miter) for region in regions]


def offset_region_outward(
    region: geo.Curve, dist: float, miter: float = BIGNUM
) -> geo.Curve:
    """영역 커브를 바깥쪽으로 offset 한다.
    단일 커브를 받아서 단일 커브로 리턴한다.
    Args:
        region: offset할 대상 커브
        dist: offset할 거리

    Returns:
        offset 후 커브
    """

    if not dist:
        return region
    if not isinstance(region, geo.Curve):
        raise ValueError("region must be curve")
    return Offset().polyline_offset(region, dist, miter).contour[0]


def get_outside_perp_vec_from_pt(pt: geo.Point3d, region: geo.Curve) -> geo.Vector3d:
    _, param = region.ClosestPoint(pt)
    vec_perp_outer = region.PerpendicularFrameAt(param)[1].XAxis

    if region.ClosedCurveOrientation() == geo.CurveOrientation.Clockwise:
        vec_perp_outer = -vec_perp_outer

    return vec_perp_outer


def get_pt_by_length(
    crv: geo.Curve, length: float, include_start: bool = False
) -> List[geo.Point3d]:
    """커브를 주어진 길이로 나누는 점을 구한다."""
    params = crv.DivideByLength(length, include_start)

    # crv가 length보다 짧은 경우
    if not params:
        return []

    return [crv.PointAt(param) for param in params]


def move_curve(crv: geo.Curve, vec: geo.Vector3d):
    """커브를 주어진 벡터로 이동시킨다."""
    moved_crv = crv.Duplicate()
    moved_crv.Translate(vec)
    return moved_crv


def get_bounding_box_crv(curve: geo.Curve, plane: geo.Plane) -> geo.PolylineCurve:
    """주어진 커브의 바운딩 박스를 구한다."""
    bbox = curve.GetBoundingBox(plane)

    corners = list(bbox.GetCorners())[:4]  # type: List[geo.Point3d]
    for corner in corners:
        corner.Transform(geo.Transform.ChangeBasis(plane, geo.Plane.WorldXY))

    return geo.PolylineCurve(corners + [corners[0]])


def convert_io_to_list(func):
    """인풋과 아웃풋을 리스트로 만들어주는 데코레이터"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        new_args = []
        for arg in args:
            if isinstance(arg, geo.Curve):
                arg = [arg]
            new_args.append(arg)

        result = func(*new_args, **kwargs)
        if isinstance(result, geo.Curve):
            result = [result]

        if hasattr(result, "__dict__"):
            for key, values in result.__dict__.items():
                if isinstance(values, geo.Curve):
                    setattr(result, key, [values])
        return result

    return wrapper


class Offset:
    class _PolylineOffsetResult:
        def __init__(self):
            self.contour: Optional[List[geo.Curve]] = None
            self.holes: Optional[List[geo.Curve]] = None

    @convert_io_to_list
    def polyline_offset(
        self,
        crvs: List[geo.Curve],
        dists: List[float],
        miter: int = BIGNUM,
        closed_fillet: int = 2,
        open_fillet: int = 2,
        tol: float = Rhino.RhinoMath.ZeroTolerance,
    ) -> _PolylineOffsetResult:
        """
        Args:
            crv (_type_): _description_
            dists (_type_): _description_
            miter : miter
            closed_fillet : 0 = round, 1 = square, 2 = miter
            open_fillet : 0 = round, 1 = square, 2 = butt

        Returns:
            _type_: _PolylineOffsetResult
        """
        if not crvs:
            raise ValueError("No Curves to offset")

        plane = geo.Plane(geo.Point3d(0, 0, crvs[0].PointAtEnd.Z), geo.Vector3d.ZAxis)
        result = ghcomp.ClipperComponents.PolylineOffset(
            crvs,
            dists,
            plane,
            tol,
            closed_fillet,
            open_fillet,
            miter,
        )

        polyline_offset_result = Offset._PolylineOffsetResult()
        for name in ("contour", "holes"):
            setattr(polyline_offset_result, name, result[name])
        return polyline_offset_result
