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
TOL = 0.01  # 허용 오차

# # 그래스호퍼 인풋을 위한 임시 변수
# target_region = geo.Curve()
# entrance_pt = geo.Point3d()


def get_axis_from_region(region: geo.Curve) -> geo.Plane:
    """
    주차장 영역의 방향성을 파악하기위한 축 생성
    :param region: 주차장 영역 (PolylineCurve)
    :return: 축 (Plane)
    """
    # 모든 변을 기준으로 바운딩 박스를 생성하여 최소 바운딩 박스를 구하여 해당 변을 축으로 설정

    min_bbox = None
    for segment in utils.explode_curve(region):
        # segment를 기준으로 regigon의 바운딩 박스를 구함
        x_vec = segment.TangentAt(0)
        y_vec = geo.Vector3d(-x_vec.Y, x_vec.X, 0)
        plane_from_seg = geo.Plane(segment.PointAtStart, x_vec, y_vec)
        bbox = region.GetBoundingBox(plane_from_seg)

        if min_bbox is None:
            min_bbox = bbox
            axis = plane_from_seg

        if min_bbox.Area < bbox.Area:
            continue

        min_bbox = bbox
        axis = plane_from_seg

    return axis


def generate_pattern_list(l) -> List[float]:
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


def get_cells_from_inside_region(region: geo.Curve, axis: geo.Plane) -> List[geo.Curve]:
    """
    내부 영역에서 셀을 생성
    :param region: 내부 영역 (PolylineCurve)
    :return: 셀 리스트 (list of PolylineCurve)
    """
    bbox_region = utils.get_bounding_box_crv(region, axis)
    bbox_segs = utils.explode_curve(bbox_region)
    bbox_segs = sorted(bbox_segs, key=lambda seg: seg.GetLength())
    short_seg, long_seg = bbox_segs[0], bbox_segs[-1]

    vec = -utils.get_outside_perp_vec_from_pt(short_seg.PointAt(0.5), bbox_region)
    length_to_move = 0
    cells = []
    pattern = generate_pattern_list(long_seg.GetLength())
    for moved_length in pattern:
        length_to_move += moved_length
        seg_for_cell = utils.move_curve(short_seg, vec * length_to_move)
        if 5 - TOL < moved_length < 5 + TOL:
            cells += get_cells_from_segement(seg_for_cell, -vec)

    return cells


def get_cells_from_inside(
    target_region: geo.Curve,
) -> List[geo.Curve]:
    """
    내부 영역에서 셀을 생성
    :param target_region: 전체 영역 (PolylineCurve)
    :return: 셀 리스트 (list of PolylineCurve)
    """

    # 1. 축 생성
    axis = get_axis_from_region(target_region)

    # 2. 전체 영역을 CELL_LENGTH + ROAD_WIDTH 만큼 안쪽으로 offset
    inside_regions = utils.offset_regions_inward(
        target_region, CELL_LENGTH + ROAD_WIDTH
    )

    if not inside_regions:
        return []

    # 3. 내부 영역에서 셀 생성
    cells = []
    for region in inside_regions:
        cells.extend(get_cells_from_inside_region(region, axis))

    # 4. 내부 영역을 벗어난 셀 필터링
    cells = filter_cells_inside_region(cells, inside_regions)

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

    pts_for_cell = utils.get_pt_by_length(segment, CELL_WIDTH, True)

    cell_count = 0
    for pt in pts_for_cell:
        if cell_count >= num_cells:
            break
        cell = get_cell_rectangle(
            pt, vec, segment.TangentAtStart, CELL_LENGTH, CELL_WIDTH
        )
        cell_count += 1
        cells.append(cell)

    return cells


def get_cells_from_outside(
    target_region: geo.Curve,
    entrance_pt: geo.Point3d,
) -> List[geo.Curve]:
    """
    주차 가능 영역의 외각을 둘러싸는 셀을 생성
    :param target_region: 외부 영역 (PolylineCurve)
    :return: 셀 리스트 (list of PolylineCurve)
    """
    # 1. 주차가능 영역의 외부영역을 주차칸의 길이 + 도로폭 만큼 안쪽으로 offset
    cells = []
    offset_regions = utils.offset_regions_inward(target_region, CELL_LENGTH)

    # 2. offset된 영역의 세그먼트를 기준으로 셀 생성
    for offset_region in offset_regions:
        for segment in utils.explode_curve(offset_region):
            # segment를 기준으로 배치가능한 최대 셀 개수 측정
            segment_length = segment.GetLength()
            num_cells = int(segment_length // (CELL_LENGTH))
            if num_cells < 1:
                continue
            # segment를 기준으로 셀 생성
            center_pt = segment.PointAt(0.5)
            cell_vec = utils.get_outside_perp_vec_from_pt(center_pt, offset_region)
            cells_from_seg = get_cells_from_segement(segment, cell_vec)

            cells.extend(cells_from_seg)

    # 3. 진입로 확보를 위한 셀 필터링
    cells = filter_cells_at_entrance(cells, entrance_pt, target_region)

    return cells


def filter_cells_at_entrance(
    cells: List[geo.Curve],
    entrance_pt: geo.Point3d,
    target_region: geo.Curve,
) -> List[geo.Curve]:
    """진입로 확보를 위한 셀 필터링
    :param cells: 셀 리스트 (list of PolylineCurve)
    :param entrance_pt: 진입점 (Point3d)
    :param target_region: 전체 영역 (PolylineCurve)
    :return: 필터링된 셀 리스트 (list of PolylineCurve)
    """
    filtered_cells = []
    for cell in cells:
        # entrance_pt와의 거리가 2.5M 이하인 셀 제거
        pt_on_region = target_region.PointAt(target_region.ClosestPoint(entrance_pt)[1])
        if utils.get_dist_between_pt_and_crv(pt_on_region, cell) > CELL_WIDTH:
            filtered_cells.append(cell)

    return filtered_cells


def filter_cells_inside_region(
    cells: List[geo.Curve], inside_regions: List[geo.Curve]
) -> List[geo.Curve]:
    """내부 영역에 맞게 셀 필터링
    :param cells: 셀 리스트 (list of PolylineCurve)
    :param inside_regions: 내부 영역 리스트 (list of PolylineCurve)
    :return: 필터링된 셀 리스트 (list of PolylineCurve)
    """
    filtered_cells = []
    for cell in cells:
        if any(utils.is_region_inside_region(cell, ir) for ir in inside_regions):
            filtered_cells.append(cell)
    return filtered_cells


# 1. 외부 영역에서 셀 생성
cells_from_outside = get_cells_from_outside(target_region, entrance_pt)

# 2. 내부 영역에서 셀 생성
cells_from_inside = get_cells_from_inside(target_region)

# 최종 셀 리스트 생성
cells = cells_from_outside + cells_from_inside
