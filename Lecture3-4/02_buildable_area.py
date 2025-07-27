# Lecture 3-4 - Practice 2: 건축 가능 영역 생성
# 사선 제한 및 높이 제한을 반영한 건축 가능 영역 계산

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

def apply_setback_requirements(site_boundary, setbacks):
    """대지경계선에서 이격거리 적용"""
    # setbacks = {'front': 3, 'side': 1, 'rear': 2}
    
    # 단순한 경우: 균일한 이격
    uniform_setback = max(setbacks.values())
    
    # 내부로 오프셋
    offset_result = rs.OffsetCurve(
        site_boundary,
        rs.CurveAreaCentroid(site_boundary)[0],
        -uniform_setback
    )
    
    if offset_result:
        return offset_result[0]
    
    return None

def create_daylight_plane(boundary_curve, angle, direction, max_height=100):
    """일조 사선 평면 생성"""
    # 경계를 따라 점 생성
    points = []
    divisions = 50
    
    for i in range(divisions + 1):
        t = i / float(divisions)
        param = boundary_curve.Domain.ParameterAt(t)
        pt = boundary_curve.PointAt(param)
        
        # 접선 방향 구하기
        tangent = boundary_curve.TangentAt(param)
        
        # 법선 방향 (내부 방향)
        normal = rg.Vector3d(-tangent.Y, tangent.X, 0)
        normal.Unitize()
        
        # 방향 조정
        center = rs.CurveAreaCentroid(boundary_curve)[0]
        to_center = center - pt
        if normal * to_center < 0:
            normal = -normal
        
        points.append(pt)
    
    # 사선 평면 생성
    surfaces = []
    angle_rad = math.radians(angle)
    
    for i in range(len(points) - 1):
        pt1 = points[i]
        pt2 = points[i + 1]
        
        # 상부 점 계산
        horizontal_dist = max_height / math.tan(angle_rad)
        
        # 내부 방향 벡터
        edge_vec = pt2 - pt1
        edge_normal = rg.Vector3d(-edge_vec.Y, edge_vec.X, 0)
        edge_normal.Unitize()
        
        # 중심 방향 확인
        mid_pt = (pt1 + pt2) / 2
        to_center = center - mid_pt
        if edge_normal * to_center < 0:
            edge_normal = -edge_normal
        
        # 상부 점
        pt3 = pt1 + edge_normal * horizontal_dist + rg.Vector3d(0, 0, max_height)
        pt4 = pt2 + edge_normal * horizontal_dist + rg.Vector3d(0, 0, max_height)
        
        # 면 생성
        surface = rg.NurbsSurface.CreateFromCorners(pt1, pt2, pt4, pt3)
        if surface:
            surfaces.append(surface)
    
    return surfaces

def apply_height_restrictions(base_boundary, absolute_height, district_height=None):
    """절대 높이 제한 적용"""
    # 기본 높이 제한
    height_limit = absolute_height
    
    # 지구단위계획 높이 제한이 있으면 더 낮은 것 적용
    if district_height:
        height_limit = min(height_limit, district_height)
    
    # 높이 제한 평면 생성
    plane = rg.Plane(rg.Point3d(0, 0, height_limit), rg.Vector3d.ZAxis)
    
    # 경계 박스로 평면 크기 결정
    bbox = rs.BoundingBox(base_boundary)
    if bbox:
        width = bbox[1].X - bbox[0].X + 20
        depth = bbox[3].Y - bbox[0].Y + 20
        center_x = (bbox[0].X + bbox[1].X) / 2
        center_y = (bbox[0].Y + bbox[3].Y) / 2
        
        plane.Origin = rg.Point3d(center_x, center_y, height_limit)
        interval_x = rg.Interval(-width/2, width/2)
        interval_y = rg.Interval(-depth/2, depth/2)
        
        height_surface = rg.PlaneSurface(plane, interval_x, interval_y)
        return height_surface, height_limit
    
    return None, height_limit

def calculate_buildable_volume(site_boundary, setbacks, daylight_angles, height_limits):
    """건축 가능 볼륨 계산"""
    # 1. 이격거리 적용
    buildable_boundary = apply_setback_requirements(site_boundary, setbacks)
    if not buildable_boundary:
        print("이격거리 적용 실패")
        return None
    
    # 2. 기본 볼륨 생성 (extrude)
    base_curve = rs.coercecurve(buildable_boundary)
    max_height = height_limits.get('absolute', 50)
    
    # 수직 압출
    extrusion = rg.Extrusion.Create(
        base_curve,
        max_height,
        True  # cap
    )
    
    if not extrusion:
        print("압출 생성 실패")
        return None
    
    # Brep으로 변환
    base_brep = extrusion.ToBrep()
    
    # 3. 사선 제한 적용
    daylight_surfaces = []
    
    # 도로 사선
    if 'road' in daylight_angles:
        road_surfaces = create_daylight_plane(
            buildable_boundary,
            daylight_angles['road'],
            'road',
            max_height
        )
        daylight_surfaces.extend(road_surfaces)
    
    # 인접대지 사선
    if 'adjacent' in daylight_angles:
        adjacent_surfaces = create_daylight_plane(
            buildable_boundary,
            daylight_angles['adjacent'],
            'adjacent',
            max_height
        )
        daylight_surfaces.extend(adjacent_surfaces)
    
    # 4. 높이 제한 적용
    height_surface, actual_height = apply_height_restrictions(
        buildable_boundary,
        height_limits.get('absolute', 50),
        height_limits.get('district')
    )
    
    # 5. Boolean 연산으로 최종 볼륨 생성
    result_brep = base_brep
    
    # 사선 제한으로 자르기
    for surface in daylight_surfaces:
        if surface:
            cutter = surface.ToBrep()
            if cutter:
                # 분할
                split_result = result_brep.Split(cutter, sc.doc.ModelAbsoluteTolerance)
                if split_result:
                    # 아래쪽 부분만 선택
                    lower_parts = []
                    for part in split_result:
                        center = part.GetBoundingBox(True).Center
                        if center.Z < actual_height * 0.7:  # 하부 70% 이하
                            lower_parts.append(part)
                    
                    if lower_parts:
                        # 가장 큰 부분 선택
                        result_brep = max(lower_parts, key=lambda b: b.GetVolume())
    
    # 높이 제한으로 자르기
    if height_surface:
        height_cutter = height_surface.ToBrep()
        split_result = result_brep.Split(height_cutter, sc.doc.ModelAbsoluteTolerance)
        if split_result:
            # 아래쪽 부분 선택
            for part in split_result:
                bbox = part.GetBoundingBox(True)
                if bbox.Min.Z < actual_height:
                    result_brep = part
                    break
    
    return result_brep, buildable_boundary

def visualize_buildable_area(site_boundary, buildable_volume, buildable_boundary, analysis_info):
    """건축 가능 영역 시각화"""
    # 레이어 생성
    layers = {
        "Site_Boundary": (200, 200, 200),
        "Buildable_Area": (0, 255, 0),
        "Buildable_Volume": (0, 200, 255),
        "Restrictions": (255, 100, 100)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 대지 경계
    rs.ObjectLayer(site_boundary, "Site_Boundary")
    
    # 건축 가능 영역 (평면)
    if buildable_boundary:
        boundary_copy = rs.CopyObject(buildable_boundary)
        rs.ObjectLayer(boundary_copy, "Buildable_Area")
        rs.ObjectColor(boundary_copy, (0, 255, 0))
    
    # 건축 가능 볼륨
    if buildable_volume:
        volume_id = sc.doc.Objects.AddBrep(buildable_volume)
        if volume_id:
            rs.ObjectLayer(volume_id, "Buildable_Volume")
            rs.ObjectColor(volume_id, (0, 200, 255))
            
            # 투명도 설정
            material_index = rs.AddMaterialToObject(volume_id)
            rs.MaterialTransparency(material_index, 0.3)
    
    # 분석 정보 표시
    if analysis_info:
        bbox = rs.BoundingBox(site_boundary)
        text_point = rg.Point3d(bbox[0].X, bbox[3].Y + 5, 0)
        
        info_text = f"""건축 가능 영역 분석
대지 면적: {analysis_info['site_area']:.2f}m²
건축 가능 면적: {analysis_info['buildable_area']:.2f}m²
건폐율 한계: {analysis_info['coverage_limit']:.1f}%
용적률 한계: {analysis_info['far_limit']:.1f}%
최대 높이: {analysis_info['max_height']:.1f}m"""
        
        rs.AddText(info_text, text_point, height=2.0)

def calculate_analysis_info(site_boundary, buildable_boundary, buildable_volume):
    """건축 가능 영역 분석 정보 계산"""
    info = {}
    
    # 대지 면적
    site_area = rs.CurveArea(site_boundary)
    if site_area:
        info['site_area'] = site_area[0]
    
    # 건축 가능 면적
    if buildable_boundary:
        buildable_area = rs.CurveArea(buildable_boundary)
        if buildable_area:
            info['buildable_area'] = buildable_area[0]
            
            # 건폐율 한계
            if info.get('site_area'):
                info['coverage_limit'] = (info['buildable_area'] / info['site_area']) * 100
    
    # 볼륨 정보
    if buildable_volume:
        volume = buildable_volume.GetVolume()
        info['buildable_volume'] = volume
        
        # 최대 높이
        bbox = buildable_volume.GetBoundingBox(True)
        info['max_height'] = bbox.Max.Z
        
        # 용적률 한계 (대략적 계산)
        if info.get('site_area'):
            # 볼륨을 평균 층고로 나누어 연면적 추정
            estimated_gfa = volume / 3.5  # 3.5m 층고 가정
            info['far_limit'] = (estimated_gfa / info['site_area']) * 100
    
    return info

def create_sample_regulations():
    """샘플 건축 규제 생성"""
    # 대지
    site_pts = [
        (10, 10, 0), (60, 12, 0), (58, 45, 0),
        (12, 43, 0), (10, 10, 0)
    ]
    site = rs.AddPolyline(site_pts)
    
    # 규제 정보
    setbacks = {
        'front': 3.0,   # 전면 이격
        'side': 1.5,    # 측면 이격
        'rear': 2.0     # 후면 이격
    }
    
    daylight_angles = {
        'road': 56.3,      # 도로 사선 (1:1.5)
        'adjacent': 80.5   # 인접대지 사선 (1:0.25)
    }
    
    height_limits = {
        'absolute': 30,    # 절대 높이 30m
        'district': 25     # 지구단위계획 25m
    }
    
    return site, setbacks, daylight_angles, height_limits

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 데이터 생성
    site, setbacks, daylight_angles, height_limits = create_sample_regulations()
    
    print("=== 건축 가능 영역 생성 ===")
    
    # 건축 가능 볼륨 계산
    buildable_volume, buildable_boundary = calculate_buildable_volume(
        site, setbacks, daylight_angles, height_limits
    )
    
    if buildable_volume and buildable_boundary:
        # 분석 정보 계산
        analysis_info = calculate_analysis_info(site, buildable_boundary, buildable_volume)
        
        # 결과 출력
        print("\n건축 가능 영역 분석 결과:")
        for key, value in analysis_info.items():
            print(f"  {key}: {value}")
        
        # 시각화
        visualize_buildable_area(site, buildable_volume, buildable_boundary, analysis_info)
        
        # 3D 뷰 설정
        rs.Command("_SetView _World _Perspective", False)
        rs.ZoomExtents()
    else:
        print("건축 가능 영역 생성 실패")