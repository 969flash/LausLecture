### 자주식 지상 주차장 레이아웃 자동화 스크립트

from operator import ge
from typing import List, Tuple, Any, Optional
import Rhino.Geometry as geo
import ghpythonlib.components as ghcomp
import scriptcontext as sc

import utils
import importlib

importlib.reload(utils)


# Constants
CELL_WIDTH = 2.5  # meters
CELL_LENGTH = 5.0  # meters
ROAD_WIDTH = 6.0  # meters

# # 그래스호퍼 인풋을 위한 임시 변수
# target_region = geo.Curve()
# entrance_pt = geo.Point3d()


def get_axis_from_region(region: geo.Curve, entrance_pt: geo.Point3d) -> geo.Plane:
    """
    주차장 영역의 방향성을 파악하기위한 축 생성
    :param region: 주차장 영역 (PolylineCurve)
    :param entrance_pt: 진입점 (Point3d)
    :return: 축 (Plane)
    """
    # 모든 변을 기준으로 바운딩 박스를 생성하여 최소 바운딩 박스를 구하여 해당 변을 축으로 설정

    min_bbox = None
    for segment in utils.explode_curve(region):
        print(f"Segment: {segment}")
        # segment를 기준으로 regigon의 바운딩 박스를 구함
        plane_from_seg = geo.Plane(segment.PointAtStart, segment.TangentAt(0))
        bbox = region.GetBoundingBox(plane_from_seg)
        print(f"Bounding Box: {bbox}")

        if min_bbox is None:
            min_bbox = bbox
            axis = plane_from_seg

        if min_bbox.Area < bbox.Area:
            continue

        min_bbox = bbox
        axis = plane_from_seg

    return axis


def get_cells_from_inside_regions(
    regions: List[geo.Curve], axis: geo.Plane
) -> List[geo.Curve]:
    """
    내부 영역에서 셀을 생성
    :param regions: 내부 영역 리스트 (PolylineCurve)
    :param axis: 축 (Plane)
    :return: 셀 리스트 (list of PolylineCurve)
    """

    def generate_pattern_list_v2(l) -> List[float]:
        """
        주차장 셀의 패턴 리스트 생성
        """
        if l < 5:
            return []

        pattern, pattern_sum = [], 0
        values = [5, 5, 6]
        i = 0
        while pattern_sum + values[i % 3] <= l:
            val = values[i % 3]
            pattern.append(val)
            pattern_sum += val
            i += 1

        edge = (l - pattern_sum) / 2
        return [edge] + pattern + [edge]

    for region in regions:
        # region 기준으로 axis를 축으로하는 바운딩 박스 생성
        bbox = region.GetBoundingBox(axis)
        dx = abs(bbox.Max.X - bbox.Min.X)
        dy = abs(bbox.Max.Y - bbox.Min.Y)
        main_length = max(dx, dy)

        cell_pattern = generate_pattern_list_v2(main_length)

        for i, length in enumerate(cell_pattern):
            # length가 5가 되는 시점마다 Bbox main_length의 수직방향으로 셀의 베이스 세그먼트생성
            if length < 5:
                continue
            if length == 5:
                # 셀의 베이스 세그먼트 생성
                if dx > dy:
                    base_pt = geo.Point3d(bbox.Min.X, bbox.Min.Y + i * CELL_WIDTH, 0)
                    vec = geo.Vector3d(0, CELL_LENGTH * dy, 0)
                else:
                    base_pt = geo.Point3d(bbox.Min.X + i * CELL_WIDTH, bbox.Min.Y, 0)
                    vec = geo.Vector3d(CELL_LENGTH * dx, 0, 0)

                segment_for_cell = geo.LineCurve(base_pt, base_pt + vec)
                # 셀 생성
                cells_from_seg = get_cells_from_segement(segment_for_cell, vec)

                cells.extend(cells_from_seg)

        # bbox의 긴변을 기준으로 셀 패턴 생성
        # region 내부의 셀만 필터링
        cells = [
            cell
            for cell in cells
            if utils.is_region_inside_region(cell, region, tol=utils.TOL)
        ]

    return cells


def get_cell_rectangle(
    base_pt: geo.Point3d,
    x_vec: geo.Vector3d,
    y_vec: geo.Vector3d,
    x_dist: float,
    y_dist: float,
) -> geo.PolylineCurve:
    # 원본 변수가 수정되지 않도록 새 객체 생성하여 사용
    x_vec = geo.Vector3d(x_vec)
    y_vec = geo.Vector3d(y_vec)
    x_vec.Unitize()
    y_vec.Unitize()
    pt_b = base_pt + (y_vec * y_dist)
    pt_c = base_pt + (y_vec * y_dist) + (x_vec * x_dist)
    pt_d = base_pt + (x_vec * x_dist)
    return geo.PolylineCurve([base_pt, pt_b, pt_c, pt_d, base_pt])


def get_cells_from_segement(segment: geo.Curve, vec: geo.Vector3d) -> List[geo.Curve]:
    """
    segment를 기준으로 셀을 생성
    :param segment: segment (LineCurve)
    :param vec: Cell의 생성 방향 벡터 (Vector3d)
    :return: 셀 리스트 (list of PolylineCurve)
    """

    cells = []
    segment_length = segment.GetLength()
    num_cells = int(segment_length // (CELL_WIDTH))
    if num_cells < 1:
        return cells

    pts_for_cell = utils.get_pt_by_length(segment, CELL_WIDTH)

    for pt in pts_for_cell:
        cell = get_cell_rectangle(
            pt, vec, segment.TangentAtStart, CELL_LENGTH, CELL_WIDTH
        )
        cells.append(cell)
    return cells


def get_cells_from_outside_regions(
    outside_region: geo.Curve,
    entrance_pt: geo.Point3d,
    axis: geo.Plane,
    inside_regions: List[geo.Curve],
) -> List[geo.Curve]:
    """
    외부 영역에서 셀을 생성
    :param outside_region: 외부 영역 (PolylineCurve)
    :param entrance_pt: 진입점 (Point3d)
    :param axis: 축 (Plane)
    :param inside_regions: 내부 영역 리스트 (list of PolylineCurve)
    :return: 셀 리스트 (list of PolylineCurve)
    """
    cells = []
    offset_regions = utils.offset_regions_inward(outside_region, CELL_LENGTH)

    for offset_region in offset_regions:
        for segment in utils.explode_curve(offset_region):
            # segment를 기준으로 배치가능한 최대 셀 개수 측정
            segment_length = segment.GetLength()
            num_cells = int(segment_length // (CELL_LENGTH + ROAD_WIDTH))
            if num_cells < 1:
                continue
            # segment를 기준으로 셀 생성

            center_pt = segment.PointAt(0.5)
            cell_vec = utils.get_outside_perp_vec_from_pt(center_pt, segment)
            cells_from_seg = get_cells_from_segement(segment, cell_vec)

            cells.extend(cells_from_seg)

    return cells


# 1. 축 생성

axis = get_axis_from_region(target_region, entrance_pt)

# 2. 전체 영역을 CELL_LENGTH + ROAD_WIDTH 만큼 안쪽으로 offset
inside_regions = utils.offset_regions_inward(target_region, CELL_LENGTH + ROAD_WIDTH)

if not inside_regions:
    raise Exception("Offset failed. 해당 알고리즘으로 탐색하기엔 작은 영역")

# 3. 외부 영역에서 셀 생성
cells_from_outside = get_cells_from_outside_regions(
    target_region, entrance_pt, axis, inside_regions
)

# 4. 내부 영역에서 셀 생성
cells_from_inside = get_cells_from_inside_regions(inside_regions, entrance_pt, axis)
# cells_from_inside = []

# 최종 셀 리스트 생성
cells = cells_from_inside + cells_from_outside
