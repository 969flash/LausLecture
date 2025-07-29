# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
import time
from collections import Counter
from typing import List, Tuple, Any, Optional


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
    pass


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


if __name__ == "__main__":
    # 전체 실행 시간 측정
    total_start = time.time()
    
    print("=" * 60)
    print("지목별 분포 분석")
    print("=" * 60)
    
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "AL_D194_11680_20250123.shp")
    
    # 1. SHP 파일 읽기
    print("\n1. SHP 파일 읽기...")
    start = time.time()
    shapes, records, fields = read_shp_file(shp_path)
    print(f"   완료: {time.time() - start:.2f}초")
    
    # 2. Parcel 객체 생성
    print("\n2. Parcel 객체 생성...")
    start = time.time()
    parcels = get_parcels_from_shapes(shapes, records, fields)
    print(f"   완료: {time.time() - start:.2f}초 ({len(parcels)}개 생성)")
    
    # 3. 필지 분류
    print("\n3. 필지 분류...")
    start = time.time()
    lots, roads = classify_parcels(parcels)
    print(f"   완료: {time.time() - start:.2f}초")
    print(f"   대지: {len(lots)}개, 도로: {len(roads)}개")
    
    # 4. 지목 분석
    print("\n4. 지목 정보 분석...")
    start = time.time()
    
    # 지목별 카운트
    jimok_counter = Counter()
    for parcel in parcels:
        jimok_counter[parcel.jimok] += 1
    
    total_count = len(parcels)
    sorted_jimok = sorted(jimok_counter.items(), key=lambda x: x[1], reverse=True)
    
    print(f"   완료: {time.time() - start:.2f}초")
    
    # 결과 출력
    print(f"\n=== 분석 결과 ===")
    print(f"전체 필지: {total_count:,}개")
    print(f"\n지목별 분포:")
    print("-" * 40)
    
    for jimok, count in sorted_jimok:
        percentage = (count / total_count) * 100
        print(f"{jimok:10s}: {count:6,}개 ({percentage:5.2f}%)")
    
    print("-" * 40)
    print(f"총 지목 종류: {len(jimok_counter)}개")
    
    # 주요 지목 TOP 5
    print("\n주요 지목 TOP 5:")
    for i, (jimok, count) in enumerate(sorted_jimok[:5]):
        percentage = (count / total_count) * 100
        print(f"{i+1}. {jimok}: {count:,}개 ({percentage:.1f}%)")
    
    print(f"\n총 실행 시간: {time.time() - total_start:.2f}초")
    
    # Grasshopper 출력용 변수
    all_lot_crvs = [lot.curve for lot in lots]
    road_crvs = [road.curve for road in roads]