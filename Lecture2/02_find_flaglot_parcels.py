# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
import time
from typing import List, Tuple, Any, Optional
import ghpythonlib.components as ghcomp


class Parcel:
    """기본 필지 클래스"""

    def __init__(
        self,
        curve: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        holes: List[geo.Curve] = None,
    ):
        self.curve = curve  # 외부 경계 커브
        self.holes = holes if holes is not None else []  # 내부 구멍들 (도넛의 구멍)
        self.pnu = pnu
        self.jimok = jimok
        self.record = record

    def preprocess_curve(self) -> bool:
        """커브 전처리 (invalid 제거, 자체교차 제거, 단순화)"""
        # 외부 경계 커브 처리
        if not self.curve or not self.curve.IsValid:
            return False

        # 자체교차 확인
        intersection_events = geo.Intersect.Intersection.CurveSelf(self.curve, 0.001)
        if intersection_events:
            # 자체교차가 있으면 단순화 시도
            simplified = self.curve.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
            if simplified:
                self.curve = simplified
            else:
                return False

        # 일반 단순화
        simplified = self.curve.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
        if simplified:
            self.curve = simplified

        # 내부 구멍들도 처리
        valid_holes = []
        for hole in self.holes:
            if hole and hole.IsValid:
                # 구멍도 단순화
                simplified_hole = hole.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
                if simplified_hole:
                    valid_holes.append(simplified_hole)
                else:
                    valid_holes.append(hole)
        self.holes = valid_holes

        return True

    def get_all_curves(self) -> List[geo.Curve]:
        """외부 경계와 모든 구멍 커브를 반환"""
        all_curves = [self.curve]
        all_curves.extend(self.holes)
        return all_curves


class Road(Parcel):
    """도로 클래스"""

    pass


class Lot(Parcel):
    """대지 클래스"""

    def __init__(
        self,
        curve: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        holes: List[geo.Curve] = None,
    ):
        super().__init__(curve, pnu, jimok, record, holes)
        self.is_landlocked = False  # 맹지 여부
        self.is_flag_lot = False  # 자루형 토지 여부
        self.road_access_length = 0.0  # 도로 접도 길이


def read_shp_file(file_path: str) -> Tuple[List[Any], List[Any], List[str]]:
    """shapefile을 읽어서 shapes와 records를 반환"""
    # 간단하게 utf-8로 먼저 시도, 실패시 cp949
    try:
        sf = shapefile.Reader(file_path, encoding="utf-8")
    except:
        try:
            sf = shapefile.Reader(file_path, encoding="cp949")
        except:
            sf = shapefile.Reader(file_path)  # 인코딩 없이

    shapes = sf.shapes()
    records = sf.records()
    fields = [field[0] for field in sf.fields[1:]]  # 필드명 리스트
    return shapes, records, fields


def get_curve_from_points(
    points: List[Tuple[float, float]], start_idx: int, end_idx: int
) -> Optional[geo.PolylineCurve]:
    """점 리스트에서 특정 구간의 커브를 생성"""
    if end_idx - start_idx < 3:
        return None

    # 닫힌 폴리곤인지 확인
    first_pt = points[start_idx]
    last_pt = points[end_idx - 1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        return None

    # Point3d로 변환
    curve_points = [
        geo.Point3d(points[i][0], points[i][1], 0) for i in range(start_idx, end_idx)
    ]

    curve = geo.PolylineCurve(curve_points)
    return curve if curve and curve.IsValid else None


def get_part_indices(shape: Any) -> List[Tuple[int, int]]:
    """shape의 각 파트의 시작과 끝 인덱스를 반환"""
    if not hasattr(shape, "parts") or len(shape.parts) <= 1:
        return [(0, len(shape.points))]

    parts = list(shape.parts) + [len(shape.points)]
    return [(parts[i], parts[i + 1]) for i in range(len(shape.parts))]


def get_curves_from_shape(
    shape: Any,
) -> Tuple[Optional[geo.PolylineCurve], List[geo.PolylineCurve]]:
    """shape에서 외부 경계와 내부 구멍 커브들을 추출"""
    boundary = None
    holes = []

    part_indices = get_part_indices(shape)

    for i, (start_idx, end_idx) in enumerate(part_indices):
        curve = get_curve_from_points(shape.points, start_idx, end_idx)
        if curve:
            if i == 0:
                boundary = curve
            else:
                holes.append(curve)

    # 단일 폴리곤이고 닫혀있지 않은 경우 처리
    if boundary is None and len(part_indices) == 1:
        points = [geo.Point3d(pt[0], pt[1], 0) for pt in shape.points]
        if len(points) >= 3:
            # 닫혀있지 않으면 닫기
            if points[0].DistanceTo(points[-1]) > 0.001:
                points.append(points[0])
            curve = geo.PolylineCurve(points)
            if curve and curve.IsValid:
                boundary = curve

    return boundary, holes


def get_field_value(
    record: List[Any], fields: List[str], field_name: str, default: str = "Unknown"
) -> str:
    """레코드에서 특정 필드값을 안전하게 추출"""
    try:
        index = fields.index(field_name)
        return record[index]
    except (ValueError, IndexError):
        return default


def create_parcel_from_shape(
    shape: Any, record: List[Any], fields: List[str]
) -> Optional[Parcel]:
    """shape에서 Parcel 객체 생성"""
    boundary, holes = get_curves_from_shape(shape)

    if not boundary or not boundary.IsValid:
        return None

    pnu = get_field_value(record, fields, "PNU")
    jimok = get_field_value(record, fields, "JIMOK")

    if jimok == "도로":
        parcel = Road(boundary, pnu, jimok, record, holes)
    else:
        parcel = Lot(boundary, pnu, jimok, record, holes)

    return parcel if parcel.preprocess_curve() else None


def get_parcels_from_shapes(
    shapes: List[Any], records: List[Any], fields: List[str]
) -> List[Parcel]:
    """모든 shape에서 Parcel 객체들을 생성"""
    parcels = []

    for shape, record in zip(shapes, records):
        parcel = create_parcel_from_shape(shape, record, fields)
        if parcel:
            parcels.append(parcel)

    return parcels


def classify_parcels(parcels: List[Parcel]) -> Tuple[List[Lot], List[Road]]:
    """Parcel 리스트를 Lot과 Road로 분류"""
    lots = []
    roads = []

    for parcel in parcels:
        if isinstance(parcel, Road):
            roads.append(parcel)
        else:
            lots.append(parcel)

    return lots, roads


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
    lot: Lot,
    road_curves: List[geo.Curve],
    road_bboxes: List[geo.BoundingBox],
    tolerance: float = 0.5,
) -> bool:
    """토지가 도로에 접근 가능한지 확인"""
    lot_bbox = lot.curve.GetBoundingBox(False)
    lot_bbox.Inflate(tolerance)

    # 바운딩박스로 1차 필터링
    candidate_indices = get_intersecting_road_indices(lot_bbox, road_bboxes)

    # 상세 근접성 검사
    for idx in candidate_indices:
        if check_curve_proximity(lot.curve, road_curves[idx], tolerance):
            return True
    return False


def get_all_road_curves(roads: List[Road]) -> List[geo.Curve]:
    """도로의 모든 커브(외부 경계 + 내부 구멍)를 추출"""
    curves = []
    for road in roads:
        # 외부 경계 추가
        curves.append(road.curve)
        # 내부 구멍들 추가
        curves.extend(road.holes)
    return curves


def get_road_contact_segments(
    lot_curve: geo.Curve, road_curves: List[geo.Curve], tolerance: float = 0.5
) -> List[geo.Curve]:
    """토지가 도로와 접하는 구간들을 찾아 반환"""
    contact_segments = []

    for road_curve in road_curves:
        # 두 커브의 교차 지점 찾기
        events = geo.Intersect.Intersection.CurveCurve(
            lot_curve, road_curve, tolerance, tolerance
        )

        if events and events.Count > 0:
            for event in events:
                if event.IsOverlap:
                    # 겹치는 구간을 추출
                    overlap_curve = lot_curve.Trim(event.OverlapA[0], event.OverlapA[1])
                    if overlap_curve:
                        contact_segments.append(overlap_curve)

    return contact_segments


def calculate_total_road_access_length(lot: Lot, road_curves: List[geo.Curve]) -> float:
    """토지의 총 도로 접도 길이 계산"""
    contact_segments = get_road_contact_segments(lot.curve, road_curves)
    total_length = 0.0

    for segment in contact_segments:
        total_length += segment.GetLength()

    return total_length


def find_flag_lots(
    lots: List[Lot], roads: List[Road], offset_distance: float = 4.0
) -> List[Lot]:
    """자루형 토지와 맹지를 찾아서 반환"""
    flag_lots: List[Lot] = []

    # 도로 커브 추출
    road_curves = get_all_road_curves(roads)
    print(f"\n도로 커브 수: {len(road_curves)}개")

    # 도로 바운딩박스 사전 계산
    road_bboxes = create_road_bounding_boxes(road_curves)
    
    # 시간 측정 시작
    start_time = time.time()
    total_lots = len(lots)
    processed = 0

    # 각 토지의 도로 접근성 검사
    for lot in lots:
        has_access = check_lot_road_access(lot, road_curves, road_bboxes)

        if not has_access:
            continue

        # 오프셋 테스트로 자루형 토지 판별
        # clipper를 사용한 내부 오프셋
        plane = geo.Plane.WorldXY
        tolerance = 0.1

        offset_result = ghcomp.ClipperComponents.PolylineOffset(
            lot.curve,
            offset_distance,  # 내부로 오프셋
            plane,
            tolerance,
            2,  # closed_fillet: 2 = miter
            2,  # open_fillet: 2 = butt
            1,  # miter limit
        )

        # 오프셋 결과가 없으면 스킵
        if not offset_result.holes:
            continue

        # offset_result.holes을 밖 방향으로 오프셋한 결과 모두 도로와 엑세스가 없는 경우 자루형 토지로판단
        is_flag_lot = True

        # holes가 리스트인지 단일 커브인지 확인
        holes_list = []
        if hasattr(offset_result.holes, "__iter__"):
            holes_list = list(offset_result.holes)
        else:
            holes_list = [offset_result.holes]

        for offset_curve in holes_list:
            # 다시 외부로 오프셋 (원래 크기로 복원 시도)
            outward_result = ghcomp.ClipperComponents.PolylineOffset(
                offset_curve,
                offset_distance,  # 외부로 오프셋
                plane,
                tolerance,
                2,  # closed_fillet: 2 = miter
                2,  # open_fillet: 2 = butt
                1,  # miter limit
            )

            if not outward_result.contour:
                continue

            # 복원된 커브로 임시 Lot 생성
            temp_lot = Lot(outward_result.contour, lot.pnu, lot.jimok, lot.record)

            # 복원된 토지가 도로와 접하는지 확인
            offset_has_access = check_lot_road_access(
                temp_lot, road_curves, road_bboxes
            )

            # 오프셋 후 도로 접근이 하나라도 있는 경우
            if offset_has_access:
                is_flag_lot = False
                break

        if is_flag_lot:
            lot.is_flag_lot = True
            flag_lots.append(lot)
        
        # 진행률 표시
        processed += 1
        if processed % max(1, total_lots // 10) == 0:
            elapsed = time.time() - start_time
            print(f"  처리 진행: {processed}/{total_lots} ({elapsed:.2f}초)")
    
    # 총 소요 시간
    total_time = time.time() - start_time
    print(f"\n자루형 토지 판별 완료: {total_time:.2f}초")
    print(f"평균 처리 시간: {total_time/total_lots*1000:.2f}ms/필지")

    return flag_lots


if __name__ == "__main__":
    # 전체 실행 시간 측정
    total_start = time.time()
    
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "test_lots_in_seoul.shp")

    print("1. SHP 파일 읽기...")
    start = time.time()
    shapes, records, fields = read_shp_file(shp_path)
    print(f"   완료: {time.time() - start:.2f}초")

    print("\n2. Parcel 객체 생성...")
    start = time.time()
    parcels = get_parcels_from_shapes(shapes, records, fields)
    print(f"   완료: {time.time() - start:.2f}초 ({len(parcels)}개 생성)")

    print("\n3. 필지 분류...")
    start = time.time()
    lots, roads = classify_parcels(parcels)
    print(f"   완료: {time.time() - start:.2f}초")
    print(f"   대지: {len(lots)}개, 도로: {len(roads)}개")

    print("\n4. 자루형 토지 찾기...")
    flag_lots = find_flag_lots(lots, roads, offset_distance=4.0)

    # 결과 출력
    print(f"\n=== 결과 ===")
    print(f"전체 대지: {len(lots)}개")
    print(f"자루형 토지: {len(flag_lots)}개")
    print(f"자루형 토지 비율: {len(flag_lots)/len(lots)*100:.1f}%")
    print(f"\n총 실행 시간: {time.time() - total_start:.2f}초")

    # 커브만 추출
    all_lot_crvs = [lot.curve for lot in lots]
    road_crvs = [road.curve for road in roads]
    flag_lot_crvs = [lot.curve for lot in flag_lots]
