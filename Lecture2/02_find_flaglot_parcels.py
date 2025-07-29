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
        self.holes = holes if holes is not None else []  # 내부 구멍들
        self.pnu = pnu
        self.jimok = jimok
        self.record = record

    def preprocess_curve(self) -> bool:
        """커브 전처리 (invalid 제거, 자체교차 제거, 단순화)"""
        if not self.curve or not self.curve.IsValid:
            return False

        # 자체교차 확인
        intersection_events = geo.Intersect.Intersection.CurveSelf(self.curve, 0.001)
        if intersection_events:
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
                simplified_hole = hole.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
                if simplified_hole:
                    valid_holes.append(simplified_hole)
                else:
                    valid_holes.append(hole)
        self.holes = valid_holes

        return True


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
        self.is_flag_lot = False  # 자루형 토지 여부
        self.has_road_access = False  # 도로 접근 여부


# ================ 파일 읽기 관련 함수 ================

def read_shp_file(file_path: str) -> Tuple[List[Any], List[Any], List[str]]:
    """shapefile을 읽어서 shapes와 records를 반환"""
    try:
        sf = shapefile.Reader(file_path, encoding="utf-8")
    except:
        try:
            sf = shapefile.Reader(file_path, encoding="cp949")
        except:
            sf = shapefile.Reader(file_path)

    shapes = sf.shapes()
    records = sf.records()
    fields = [field[0] for field in sf.fields[1:]]
    return shapes, records, fields


def get_curve_from_points(
    points: List[Tuple[float, float]], start_idx: int, end_idx: int
) -> Optional[geo.PolylineCurve]:
    """점 리스트에서 특정 구간의 커브를 생성"""
    if end_idx - start_idx < 3:
        return None

    first_pt = points[start_idx]
    last_pt = points[end_idx - 1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        return None

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

    pnu = get_field_value(record, fields, "A1")  # 구 PNU
    jimok = get_field_value(record, fields, "A11")  # 구 JIMOK

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


# ================ 도로 접근성 검사 함수 ================

def check_bounding_boxes_intersect(bbox1: geo.BoundingBox, bbox2: geo.BoundingBox) -> bool:
    """두 바운딩박스가 교차하는지 확인"""
    return not (
        bbox1.Max.X < bbox2.Min.X or 
        bbox1.Min.X > bbox2.Max.X or
        bbox1.Max.Y < bbox2.Min.Y or 
        bbox1.Min.Y > bbox2.Max.Y
    )


def check_curve_proximity(
    curve1: geo.Curve, curve2: geo.Curve, tolerance: float = 0.5
) -> bool:
    """두 커브가 tolerance 거리 이내에 있는지 확인"""
    # 바운딩박스 사전 체크
    bbox1 = curve1.GetBoundingBox(False)
    bbox2 = curve2.GetBoundingBox(False)
    bbox1.Inflate(tolerance)
    bbox2.Inflate(tolerance)
    
    if not check_bounding_boxes_intersect(bbox1, bbox2):
        return False
    
    # 교차점 확인
    events = geo.Intersect.Intersection.CurveCurve(curve1, curve2, tolerance, tolerance)
    if events and events.Count > 0:
        return True

    # 끝점 간 거리 확인
    start1 = curve1.PointAtStart
    end1 = curve1.PointAtEnd
    start2 = curve2.PointAtStart
    end2 = curve2.PointAtEnd

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
    for idx in range(len(road_curves)):
        if check_bounding_boxes_intersect(lot_bbox, road_bboxes[idx]):
            if check_curve_proximity(lot.curve, road_curves[idx], tolerance):
                return True
    
    return False


def get_all_road_curves(roads: List[Road]) -> List[geo.Curve]:
    """도로의 모든 커브(외부 경계 + 내부 구멍)를 추출"""
    curves = []
    for road in roads:
        curves.append(road.curve)
        curves.extend(road.holes)
    return curves


# ================ 오프셋 관련 함수 ================

def perform_clipper_offset(
    curve: geo.Curve, 
    distance: float,
    get_holes: bool = True
) -> List[geo.Curve]:
    """Clipper를 사용한 오프셋 수행"""
    plane = geo.Plane.WorldXY
    tolerance = 0.1
    
    try:
        result = ghcomp.ClipperComponents.PolylineOffset(
            curve,
            distance,
            plane,
            tolerance,
            2,  # closed_fillet: 2 = miter
            2,  # open_fillet: 2 = butt
            1,  # miter limit
        )
        
        if not result:
            return []
        
        # holes (내부 오프셋) 또는 contour (외부 오프셋) 반환
        output = result.holes if get_holes else result.contour
        
        if not output:
            return []
        
        # 리스트로 변환
        if hasattr(output, "__iter__"):
            return list(output)
        return [output]
        
    except:
        return []


def is_curve_flag_shaped(
    curve: geo.Curve,
    road_curves: List[geo.Curve],
    road_bboxes: List[geo.BoundingBox],
    offset_distance: float
) -> bool:
    """커브가 자루형인지 판별
    
    1. 안쪽으로 오프셋
    2. 다시 바깥쪽으로 오프셋 (복원)
    3. 복원된 형태가 도로와 접하지 않으면 자루형
    """
    # 1단계: 안쪽으로 오프셋
    inner_curves = perform_clipper_offset(curve, offset_distance, get_holes=True)
    
    if not inner_curves:
        return False
    
    # 2단계: 각 내부 커브를 다시 바깥으로 오프셋하여 검사
    for inner_curve in inner_curves:
        # 바깥쪽으로 오프셋 (복원)
        restored_curves = perform_clipper_offset(inner_curve, offset_distance, get_holes=False)
        
        if not restored_curves:
            continue
        
        # 복원된 커브가 도로와 접하는지 확인
        for restored_curve in restored_curves:
            restored_bbox = restored_curve.GetBoundingBox(False)
            restored_bbox.Inflate(0.5)
            
            # 빠른 바운딩박스 검사
            for i, road_bbox in enumerate(road_bboxes):
                if check_bounding_boxes_intersect(restored_bbox, road_bbox):
                    if check_curve_proximity(restored_curve, road_curves[i], 0.5):
                        # 하나라도 도로와 접하면 자루형이 아님
                        return False
    
    # 모든 복원된 커브가 도로와 접하지 않으면 자루형
    return True


# ================ 자루형 토지 찾기 메인 함수 ================

def find_flag_lots(
    lots: List[Lot], 
    roads: List[Road], 
    offset_distance: float = 4.0
) -> List[Lot]:
    """자루형 토지를 찾아서 반환
    
    자루형 토지: 도로에 접하지만 좁은 통로로만 연결되어 있어
    offset_distance만큼 안쪽으로 오프셋하면 도로 접근이 사라지는 토지
    """
    # 준비 작업
    road_curves = get_all_road_curves(roads)
    road_bboxes = create_road_bounding_boxes(road_curves)
    
    print(f"\n도로 커브 수: {len(road_curves)}개")
    
    # 1단계: 도로에 접한 토지만 필터링
    print("\n도로 접근성 필터링...")
    filter_start = time.time()
    
    accessible_lots = []
    for lot in lots:
        if check_lot_road_access(lot, road_curves, road_bboxes):
            lot.has_road_access = True
            accessible_lots.append(lot)
    
    print(f"도로 접근 토지: {len(accessible_lots)}개 / {len(lots)}개 ({time.time() - filter_start:.2f}초)")
    
    # 2단계: 자루형 토지 판별
    print(f"\n자루형 토지 판별 시작 (대상: {len(accessible_lots)}개)")
    start_time = time.time()
    
    flag_lots = []
    processed = 0
    
    for lot in accessible_lots:
        if is_curve_flag_shaped(lot.curve, road_curves, road_bboxes, offset_distance):
            lot.is_flag_lot = True
            flag_lots.append(lot)
        
        # 진행률 표시
        processed += 1
        if processed % max(1, len(accessible_lots) // 10) == 0:
            elapsed = time.time() - start_time
            print(f"  처리 진행: {processed}/{len(accessible_lots)} ({elapsed:.2f}초)")
    
    # 완료 통계
    total_time = time.time() - start_time
    print(f"\n자루형 토지 판별 완료: {total_time:.2f}초")
    
    if accessible_lots:
        print(f"평균 처리 시간: {total_time/len(accessible_lots)*1000:.2f}ms/필지")
    
    return flag_lots




if __name__ == "__main__":
    # 전체 실행 시간 측정
    total_start = time.time()
    
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "AL_D194_11680_20250123.shp")

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
    
    if lots:
        print(f"자루형 토지 비율: {len(flag_lots)/len(lots)*100:.1f}%")
    
    print(f"\n총 실행 시간: {time.time() - total_start:.2f}초")

    # 커브만 추출
    all_lot_crvs = [lot.curve for lot in lots]
    road_crvs = [road.curve for road in roads]
    flag_lot_crvs = [lot.curve for lot in flag_lots]