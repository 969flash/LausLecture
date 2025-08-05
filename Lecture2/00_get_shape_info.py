# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
from typing import List, Tuple, Any, Optional

import utils
import importlib

importlib.reload(utils)


class Parcel:
    """기본 필지 클래스"""

    def __init__(
        self,
        region: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve] = None,
    ):
        self.region = region  # 외부 경계 커브
        self.hole_regions = (
            hole_regions if hole_regions is not None else []
        )  # 내부 구멍들
        self.pnu = pnu
        self.jimok = jimok
        self.record = record

    def preprocess_curve(self) -> bool:
        """커브 전처리 (invalid 제거, 자체교차 제거, 단순화)"""
        if not self.region or not self.region.IsValid:
            return False

        # 자체교차 확인
        intersection_events = geo.Intersect.Intersection.CurveSelf(self.region, 0.001)
        if intersection_events:
            simplified = self.region.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
            if simplified:
                self.region = simplified
            else:
                return False

        # 일반 단순화
        simplified = self.region.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
        if simplified:
            self.region = simplified

        # 내부 구멍들도 처리
        valid_hole_regions = []
        for hole_region in self.hole_regions:
            if hole_region and hole_region.IsValid:
                simplified_hole = hole_region.Simplify(
                    geo.CurveSimplifyOptions.All, 0.1, 1.0
                )
                if simplified_hole:
                    valid_hole_regions.append(simplified_hole)
                else:
                    valid_hole_regions.append(hole_region)
        self.hole_regions = valid_hole_regions

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
    # 최소 3개의 점이 필요
    if end_idx - start_idx < 3:
        return None

    # 시작과 끝 점이 동일하지 않으면(닫혀있지 않으면) None 반환
    first_pt = points[start_idx]
    last_pt = points[end_idx - 1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        return None

    curve_points = [
        geo.Point3d(points[i][0], points[i][1], 0) for i in range(start_idx, end_idx)
    ]

    curve_crv = geo.PolylineCurve(curve_points)
    return curve_crv if curve_crv and curve_crv.IsValid else None


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
    boundary_region = None
    hole_regions = []

    part_indices = get_part_indices(shape)

    for i, (start_idx, end_idx) in enumerate(part_indices):
        curve_crv = get_curve_from_points(shape.points, start_idx, end_idx)
        if curve_crv:
            if i == 0:
                boundary_region = curve_crv
            else:
                hole_regions.append(curve_crv)

    # 단일 폴리곤이고 닫혀있지 않은 경우 처리
    if boundary_region is None and len(part_indices) == 1:
        points = [geo.Point3d(pt[0], pt[1], 0) for pt in shape.points]
        if len(points) >= 3:
            if points[0].DistanceTo(points[-1]) > 0.001:
                points.append(points[0])
            curve_crv = geo.PolylineCurve(points)
            if curve_crv and curve_crv.IsValid:
                boundary_region = curve_crv

    return boundary_region, hole_regions


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
    boundary_region, hole_regions = get_curves_from_shape(shape)

    if not boundary_region or not boundary_region.IsValid:
        return None

    pnu = get_field_value(record, fields, "A1")  # 구 PNU
    jimok = get_field_value(record, fields, "A11")  # 구 JIMOK

    if jimok == "도로":
        parcel = Road(boundary_region, pnu, jimok, record, hole_regions)
    else:
        parcel = Lot(boundary_region, pnu, jimok, record, hole_regions)

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
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "AL_D194_11680_20250123.shp")

    # SHP 파일 읽기
    shapes, records, fields = read_shp_file(shp_path)

    # Parcel 객체 생성
    parcels = get_parcels_from_shapes(shapes, records, fields)

    # 필지 분류
    lots, roads = classify_parcels(parcels)
    print(f"대지: {len(lots)}개, 도로: {len(roads)}개")

    # 지목별 카운트
    jimok_counter = {}
    for parcel in parcels:
        jimok = parcel.jimok
        if jimok in jimok_counter:
            jimok_counter[jimok] += 1
        else:
            jimok_counter[jimok] = 1

    total_count = len(parcels)
    sorted_jimok = sorted(jimok_counter.items(), key=lambda x: x[1], reverse=True)

    # 결과 출력
    print(f"\n전체 필지: {total_count:,}개")
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

    # Grasshopper 출력용 변수
    all_lot_crvs = [lot.region for lot in lots]
    road_crvs = [road.region for road in roads]
