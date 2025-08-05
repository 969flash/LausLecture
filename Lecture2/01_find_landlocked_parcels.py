# r: pyshp

import Rhino.Geometry as geo
import os
from typing import List, Tuple, Any, Optional

import utils
import importlib

importlib.reload(utils)




def check_curve_proximity(
    curve1: geo.Curve, curve2: geo.Curve, tolerance: float = 0.5
) -> bool:
    """두 커브가 tolerance 거리 이내에 있는지 확인"""
    # Intersection을 사용하여 근접 여부 확인
    events = geo.Intersect.Intersection.CurveCurve(curve1, curve2, tolerance, tolerance)

    # 교차점이 있으면 근접함
    if events and events.Count > 0:
        return True

    # 추가로 끝점 간 거리도 확인 (커브 끝에서만 접하는 경우)
    start1 = curve1.PointAtStart
    end1 = curve1.PointAtEnd
    start2 = curve2.PointAtStart
    end2 = curve2.PointAtEnd

    # 끝점 간 거리 검사
    if (
        start1.DistanceTo(start2) <= tolerance
        or start1.DistanceTo(end2) <= tolerance
        or end1.DistanceTo(start2) <= tolerance
        or end1.DistanceTo(end2) <= tolerance
    ):
        return True

    # 커브 위의 가장 가까운 점 찾기
    t1 = curve1.ClosestPoint(start2)[1] if curve1.ClosestPoint(start2)[0] else -1
    if t1 >= 0 and curve1.PointAt(t1).DistanceTo(start2) <= tolerance:
        return True

    t2 = curve2.ClosestPoint(start1)[1] if curve2.ClosestPoint(start1)[0] else -1
    if t2 >= 0 and curve2.PointAt(t2).DistanceTo(start1) <= tolerance:
        return True

    return False


def create_road_bounding_boxes(
    road_curves: List[geo.Curve], tolerance: float = 0.5
) -> List[geo.BoundingBox]:
    """모든 도로 커브의 바운딩박스를 생성하고 tolerance만큼 확장"""
    road_bboxes = []
    for road_curve in road_curves:
        bbox = road_curve.GetBoundingBox(False)
        bbox.Inflate(tolerance)
        road_bboxes.append(bbox)
    return road_bboxes


def get_intersecting_road_indices(
    lot_bbox: geo.BoundingBox, road_bboxes: List[geo.BoundingBox]
) -> List[int]:
    """토지와 바운딩박스가 겹치는 도로의 인덱스 반환"""
    indices = []
    for i, road_bbox in enumerate(road_bboxes):
        # 바운딩박스 교차 확인 (각 축에서 겹치는지 확인)
        if not (
            lot_bbox.Max.X < road_bbox.Min.X
            or lot_bbox.Min.X > road_bbox.Max.X
            or lot_bbox.Max.Y < road_bbox.Min.Y
            or lot_bbox.Min.Y > road_bbox.Max.Y
        ):
            indices.append(i)
    return indices


def check_lot_road_access(
    lot: utils.Lot,
    road_curves: List[geo.Curve],
    road_bboxes: List[geo.BoundingBox],
    tolerance: float = 0.5,
) -> bool:
    """토지가 도로에 접근 가능한지 확인"""
    lot_bbox = lot.region.GetBoundingBox(False)
    lot_bbox.Inflate(tolerance)

    # 바운딩박스로 1차 필터링
    candidate_indices = get_intersecting_road_indices(lot_bbox, road_bboxes)

    # 상세 근접성 검사
    for idx in candidate_indices:
        if check_curve_proximity(lot.region, road_curves[idx], tolerance):
            return True
    return False


def get_all_road_curves(roads: List[utils.Road]) -> List[geo.Curve]:
    """도로의 모든 커브(외부 경계 + 내부 구멍)를 추출"""
    curves = []
    for road in roads:
        # 외부 경계 추가
        curves.append(road.region)
        # 내부 구멍들 추가
        curves.extend(road.hole_regions)
    return curves


def find_landlocked_lots(lots: List[utils.Lot], roads: List[utils.Road]) -> List[utils.Lot]:
    """맹지를 찾아서 반환 (바운딩박스 필터링 최적화)"""
    landlocked_lots: List[utils.Lot] = []

    # 도로 커브 추출
    road_curves = get_all_road_curves(roads)

    # 도로 바운딩박스 사전 계산
    road_bboxes = create_road_bounding_boxes(road_curves)

    # 각 토지의 도로 접근성 검사
    for lot in lots:
        has_access = check_lot_road_access(lot, road_curves, road_bboxes)

        if not has_access:
            lot.is_landlocked = True
            landlocked_lots.append(lot)

    return landlocked_lots


if __name__ == "__main__":
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "AL_D194_11680_20250123.shp")

    # SHP 파일 읽기
    shapes, records, fields = utils.read_shp_file(shp_path)

    # Parcel 객체 생성
    parcels = utils.get_parcels_from_shapes(shapes, records, fields)

    # 필지 분류
    lots, roads = utils.classify_parcels(parcels)
    print(f"대지: {len(lots)}개, 도로: {len(roads)}개")

    # 맹지 찾기
    landlocked_lots = find_landlocked_lots(lots, roads)

    # 결과 출력
    print(f"\n전체 대지: {len(lots)}개")
    print(f"맹지: {len(landlocked_lots)}개")
    
    if lots:
        print(f"맹지 비율: {len(landlocked_lots)/len(lots)*100:.1f}%")

    # Grasshopper 출력용 변수
    all_lot_crvs = [lot.region for lot in lots]
    road_crvs = [road.region for road in roads]
    landlocked_crvs = [lot.region for lot in landlocked_lots]
