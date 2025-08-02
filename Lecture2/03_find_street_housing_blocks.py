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
        region: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve] = None,
    ):
        self.region = region  # 외부 경계 커브
        self.hole_regions = hole_regions if hole_regions is not None else []  # 내부 구멍들
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
        for hole in self.hole_regions:
            if hole and hole.IsValid:
                simplified_hole = hole.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
                if simplified_hole:
                    valid_hole_regions.append(simplified_hole)
                else:
                    valid_hole_regions.append(hole)
        self.hole_regions = valid_hole_regions

        return True


class Road(Parcel):
    """도로 클래스"""

    pass


class Lot(Parcel):
    """대지 클래스"""

    pass


class Block:
    """블록 클래스 - 여러 필지가 합쳐진 단위"""

    def __init__(self, region: geo.Curve, block_id: str = None):
        self.region = region
        self.block_id = block_id
        self.area = self.calculate_area()
        self.is_eligible = False  # 가로주택 정비사업 적격 여부
        self.has_through_road = False  # 관통도로 여부

    def calculate_area(self) -> float:
        """블록의 면적 계산"""
        if not self.region or not self.region.IsClosed:
            return 0.0

        area_result = geo.AreaMassProperties.Compute(self.region)
        return area_result.Area if area_result else 0.0

    def check_area_requirement(self, max_area: float = 10000.0) -> bool:
        """면적 요건 확인 (10,000m² 미만)"""
        return self.area < max_area


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


# ================ 오프셋 관련 함수 ================


def perform_clipper_offset(
    regions: List[geo.Curve], distance: float = 0.1
) -> List[geo.Curve]:
    """Clipper를 사용하여 커브들을 offset"""
    if not regions:
        return []

    offset_regions = []

    try:
        result = ghcomp.ClipperComponents.PolylineOffset(
            regions,
            distance,
            geo.Plane.WorldXY,
            0.01,  # tolerance
            2,  # closed_fillet: 2 = miter
            2,  # open_fillet: 2 = butt
            1,  # miter_limit
        )

        if result and result.contour:
            if hasattr(result.contour, "__iter__"):
                offset_regions = list(result.contour)
            else:
                offset_regions = [result.contour]

    except Exception as e:
        print(f"Offset 오류: {e}")

    return offset_regions


# ================ 공간 그룹핑 관련 함수 ================


def get_curve_center(curve_crv: geo.Curve) -> geo.Point3d:
    """커브의 중심점 계산"""
    area_props = geo.AreaMassProperties.Compute(curve_crv)
    if area_props:
        return area_props.Centroid
    else:
        bbox = curve_crv.GetBoundingBox(False)
        return bbox.Center


def check_bounding_boxes_intersect(
    bbox1: geo.BoundingBox, bbox2: geo.BoundingBox
) -> bool:
    """두 바운딩박스가 교차하는지 확인"""
    return not (
        bbox1.Max.X < bbox2.Min.X
        or bbox1.Min.X > bbox2.Max.X
        or bbox1.Max.Y < bbox2.Min.Y
        or bbox1.Min.Y > bbox2.Max.Y
    )


def get_spatial_groups(
    regions: List[geo.Curve], max_distance: float = 50.0
) -> List[List[int]]:
    """공간적으로 가까운 커브들을 그룹으로 묶기"""
    n = len(regions)
    if n == 0:
        return []

    # 각 커브의 중심점과 바운딩박스 계산
    centers = []
    bboxes = []
    for region in regions:
        centers.append(get_curve_center(region))
        bbox = region.GetBoundingBox(False)
        bbox.Inflate(max_distance)
        bboxes.append(bbox)

    # Union-Find 구조로 그룹 관리
    parent = list(range(n))

    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # 바운딩박스가 겹치고 중심점이 가까운 경우 그룹화
    for i in range(n):
        for j in range(i + 1, n):
            # 바운딩박스 체크
            if check_bounding_boxes_intersect(bboxes[i], bboxes[j]):
                # 중심점 거리 체크
                dist = centers[i].DistanceTo(centers[j])
                if dist <= max_distance:
                    union(i, j)

    # 그룹별로 인덱스 수집
    groups_dict = {}
    for i in range(n):
        root = find(i)
        if root not in groups_dict:
            groups_dict[root] = []
        groups_dict[root].append(i)

    return list(groups_dict.values())


# ================ Boolean Union 관련 함수 ================


def union_curves_in_group(regions: List[geo.Curve]) -> List[geo.Curve]:
    """그룹 내 커브들을 Union"""
    if not regions or len(regions) <= 1:
        return regions

    try:
        # CreateBooleanRegions 사용 (urban-geometry 스타일)
        boolean_regions = geo.Curve.CreateBooleanRegions(
            regions, geo.Plane.WorldXY, True, 0.01  # combine_regions  # tolerance
        )

        if boolean_regions and boolean_regions.RegionCount > 0:
            result_regions = []
            for i in range(boolean_regions.RegionCount):
                region_curves = boolean_regions.RegionCurves(i)
                if region_curves and len(region_curves) > 0:
                    # 첫 번째 커브가 외부 경계
                    outer_boundary = region_curves[0]
                    if outer_boundary.IsClosed:
                        result_regions.append(outer_boundary)

            if result_regions:
                return result_regions

    except Exception as e:
        pass  # 실패시 다음 방법 시도

    # CreateBooleanUnion 백업 방법
    try:
        union_result = geo.Curve.CreateBooleanUnion(regions, 0.01)
        if union_result and len(union_result) > 0:
            return list(union_result)
    except:
        pass

    # 모든 방법 실패시 원본 반환
    return regions


def create_blocks_with_spatial_union(
    lot_regions: List[geo.Curve],
    offset_distance: float = 0.1,
    group_distance: float = 50.0,
) -> List[Block]:
    """공간적으로 가까운 필지들을 Union하여 블록 생성"""
    if not lot_regions:
        return []

    print(f"   블록 생성 시작 ({len(lot_regions)}개 필지)...")
    start_time = time.time()

    # 1. Offset 처리
    print(f"   Offset 처리 ({offset_distance}m)...")
    offset_regions = perform_clipper_offset(lot_regions, offset_distance)
    print(f"   Offset 완료: {len(lot_regions)} -> {len(offset_regions)}개")

    if not offset_regions:
        print("   Offset 실패")
        return []

    # 2. 공간 그룹 생성
    print(f"   공간 그룹핑 (최대거리: {group_distance}m)...")
    groups = get_spatial_groups(offset_regions, group_distance)
    print(f"   {len(groups)}개 그룹 생성")

    # 3. 각 그룹별로 Union하여 블록 생성
    print(f"   그룹별 Union 처리...")
    blocks = []

    for i, group_indices in enumerate(groups):
        if i % max(1, len(groups) // 10) == 0:
            print(f"   진행중: {i}/{len(groups)} 그룹")

        # 그룹의 커브들 추출
        group_regions = [offset_regions[idx] for idx in group_indices]

        # 그룹 내 Union
        union_results = union_curves_in_group(group_regions)

        # 블록 객체 생성
        for j, region in enumerate(union_results):
            if region and region.IsValid and region.IsClosed:
                block = Block(region, f"Block_{len(blocks)}")
                blocks.append(block)

    # 4. 전체 결과를 다시 한번 Union (선택적)
    if len(blocks) > 1 and len(blocks) < 100:
        print(f"   전체 Union 시도...")
        all_regions = [block.region for block in blocks]
        final_results = union_curves_in_group(all_regions)

        if len(final_results) < len(blocks):
            print(f"   전체 Union 성공: {len(blocks)} -> {len(final_results)}개")
            blocks = []
            for i, region in enumerate(final_results):
                if region and region.IsValid and region.IsClosed:
                    block = Block(region, f"Block_{i}")
                    blocks.append(block)

    print(f"   블록 생성 완료: {len(blocks)}개 블록 ({time.time() - start_time:.2f}초)")
    return blocks


# ================ 가로주택 정비사업 블록 찾기 메인 함수 ================


def find_street_housing_blocks(
    lots: List[Lot],
    offset_distance: float = 0.1,
    group_distance: float = 50.0,
    max_area: float = 10000.0,
) -> Tuple[List[Block], List[Block]]:
    """가로주택 정비사업 적격 블록 찾기

    Args:
        lots: 대지 리스트
        offset_distance: 필지 간 틈새를 메우기 위한 오프셋 거리
        group_distance: 공간 그룹핑 최대 거리
        max_area: 최대 면적 요건 (10,000m²)

    Returns:
        (적격 블록 리스트, 부적격 블록 리스트)
    """
    # 대지 커브 추출
    lot_regions = [lot.region for lot in lots]

    # 블록 생성
    blocks = create_blocks_with_spatial_union(
        lot_regions, offset_distance, group_distance
    )

    # 적격성 판별
    eligible_blocks = []
    ineligible_blocks = []

    for block in blocks:
        if block.check_area_requirement(max_area):
            block.is_eligible = True
            eligible_blocks.append(block)
        else:
            block.is_eligible = False
            ineligible_blocks.append(block)

    return eligible_blocks, ineligible_blocks


if __name__ == "__main__":
    # 전체 실행 시간 측정
    total_start = time.time()

    print("=" * 60)
    print("가로주택 정비사업 블록 찾기")
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

    # 4. 가로주택 정비사업 블록 찾기
    print("\n4. 가로주택 정비사업 블록 찾기...")
    eligible_blocks, ineligible_blocks = find_street_housing_blocks(
        lots, offset_distance=0.1, group_distance=50.0, max_area=10000.0
    )

    # 결과 출력
    print(f"\n=== 결과 ===")
    print(f"전체 블록: {len(eligible_blocks) + len(ineligible_blocks)}개")
    print(f"적격 블록: {len(eligible_blocks)}개")
    print(f"부적격 블록: {len(ineligible_blocks)}개")

    if eligible_blocks:
        areas = [block.area for block in eligible_blocks]
        print(f"\n적격 블록 면적 분포:")
        print(f"  최소: {min(areas):.1f}m²")
        print(f"  최대: {max(areas):.1f}m²")
        print(f"  평균: {sum(areas)/len(areas):.1f}m²")

    print(f"\n총 실행 시간: {time.time() - total_start:.2f}초")

    # Grasshopper 출력용 변수
    all_lot_crvs = [lot.region for lot in lots]
    road_crvs = [road.region for road in roads]

    # 블록 커브와 면적
    eligible_block_crvs = [block.region for block in eligible_blocks]
    ineligible_block_crvs = [block.region for block in ineligible_blocks]
