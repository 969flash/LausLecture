# Lecture 3-4 - Practice 1: 지오메트리 정보 전처리
# 건축 설계를 위한 대지 및 주변 환경 정보 정리

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

def analyze_site_geometry(site_boundary):
    """대지 지오메트리 분석"""
    analysis = {}
    
    # 면적 및 둘레
    area_result = rs.CurveArea(site_boundary)
    if area_result:
        analysis['area'] = area_result[0]
        analysis['centroid'] = area_result[1]
    
    analysis['perimeter'] = rs.CurveLength(site_boundary)
    
    # 경계 박스 및 방향
    bbox = rs.BoundingBox(site_boundary)
    if bbox:
        analysis['bbox'] = bbox
        analysis['width'] = bbox[1].X - bbox[0].X
        analysis['depth'] = bbox[3].Y - bbox[0].Y
        
        # 장축 방향 계산
        if analysis['width'] > analysis['depth']:
            analysis['orientation'] = 'EW'  # 동서 방향
            analysis['aspect_ratio'] = analysis['width'] / analysis['depth']
        else:
            analysis['orientation'] = 'NS'  # 남북 방향
            analysis['aspect_ratio'] = analysis['depth'] / analysis['width']
    
    # 형태 계수
    if analysis.get('area') and analysis.get('perimeter'):
        analysis['compactness'] = 4 * math.pi * analysis['area'] / (analysis['perimeter'] ** 2)
    
    return analysis

def find_adjacent_roads(site_boundary, roads, buffer_distance=1.0):
    """인접 도로 찾기 및 정보 수집"""
    adjacent_roads = []
    site_curve = rs.coercecurve(site_boundary)
    
    for road in roads:
        road_curve = rs.coercecurve(road)
        
        # 최소 거리 확인
        result = site_curve.ClosestPoints(road_curve)
        if result[0] and result[1]:
            distance = result[1].DistanceTo(result[2])
            
            if distance <= buffer_distance:
                # 접도 구간 계산
                contact_length = calculate_contact_length(site_curve, road_curve, buffer_distance)
                
                road_info = {
                    'road': road,
                    'distance': distance,
                    'contact_length': contact_length,
                    'contact_point': result[1],
                    'road_point': result[2]
                }
                
                # 도로 폭 추정 (간단한 방법)
                road_width = estimate_road_width(road)
                road_info['width'] = road_width
                
                adjacent_roads.append(road_info)
    
    return adjacent_roads

def calculate_contact_length(site_curve, road_curve, tolerance):
    """대지와 도로의 접촉 길이 계산"""
    contact_length = 0
    
    # 대지 경계를 따라 샘플링
    divisions = 100
    contact_params = []
    
    for i in range(divisions):
        t = i / float(divisions - 1)
        param = site_curve.Domain.ParameterAt(t)
        point = site_curve.PointAt(param)
        
        # 도로까지 거리 확인
        result = road_curve.ClosestPoint(point)
        if result[0]:
            closest_pt = road_curve.PointAt(result[1])
            if point.DistanceTo(closest_pt) <= tolerance:
                contact_params.append(param)
    
    # 연속된 접촉 구간의 길이 계산
    if contact_params:
        # 파라미터 그룹화
        groups = []
        current_group = [contact_params[0]]
        
        for i in range(1, len(contact_params)):
            param_diff = abs(contact_params[i] - contact_params[i-1])
            expected_diff = site_curve.Domain.Length / divisions
            
            if param_diff < expected_diff * 2:  # 연속된 점
                current_group.append(contact_params[i])
            else:
                groups.append(current_group)
                current_group = [contact_params[i]]
        
        groups.append(current_group)
        
        # 각 그룹의 길이 계산
        for group in groups:
            if len(group) > 1:
                start_param = group[0]
                end_param = group[-1]
                length = site_curve.GetLength(rg.Interval(start_param, end_param))
                contact_length += length
    
    return contact_length

def estimate_road_width(road):
    """도로 폭 추정"""
    # 간단한 방법: 도로 커브의 면적을 길이로 나누기
    area_result = rs.CurveArea(road)
    length = rs.CurveLength(road)
    
    if area_result and length > 0:
        # 평균 폭 추정
        return area_result[0] / length
    
    return 8.0  # 기본값 8m

def analyze_neighboring_buildings(site_boundary, buildings, influence_distance=50):
    """주변 건물 분석"""
    neighbors = []
    site_curve = rs.coercecurve(site_boundary)
    site_center = rs.CurveAreaCentroid(site_boundary)[0]
    
    for building in buildings:
        building_curve = rs.coercecurve(building)
        
        # 거리 확인
        result = site_curve.ClosestPoints(building_curve)
        if result[0] and result[1]:
            distance = result[1].DistanceTo(result[2])
            
            if distance <= influence_distance:
                # 건물 정보 수집
                building_info = {
                    'building': building,
                    'distance': distance
                }
                
                # 건물 높이 (속성에서 가져오거나 추정)
                height = rs.GetUserText(building, "height")
                if height:
                    building_info['height'] = float(height)
                else:
                    building_info['height'] = 15.0  # 기본 5층 추정
                
                # 건물 면적
                area_result = rs.CurveArea(building)
                if area_result:
                    building_info['area'] = area_result[0]
                    building_info['center'] = area_result[1]
                
                # 방향 계산
                if building_info.get('center'):
                    direction = building_info['center'] - site_center
                    angle = math.atan2(direction.Y, direction.X) * 180 / math.pi
                    
                    if -45 <= angle < 45:
                        building_info['direction'] = 'E'
                    elif 45 <= angle < 135:
                        building_info['direction'] = 'N'
                    elif -135 <= angle < -45:
                        building_info['direction'] = 'S'
                    else:
                        building_info['direction'] = 'W'
                
                neighbors.append(building_info)
    
    return neighbors

def create_analysis_layers():
    """분석 결과 표시를 위한 레이어 생성"""
    layers = {
        "Site_Analysis": (255, 200, 0),
        "Adjacent_Roads": (100, 100, 100),
        "Neighboring_Buildings": (150, 150, 150),
        "Analysis_Annotations": (0, 0, 0)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)

def visualize_site_analysis(site_boundary, analysis_data, adjacent_roads, neighbors):
    """대지 분석 결과 시각화"""
    create_analysis_layers()
    
    # 대지 표시
    rs.ObjectLayer(site_boundary, "Site_Analysis")
    
    # 분석 정보 텍스트
    info_text = f"""대지 분석 정보
면적: {analysis_data['area']:.2f}m²
둘레: {analysis_data['perimeter']:.2f}m
형태계수: {analysis_data['compactness']:.3f}
장단비: {analysis_data['aspect_ratio']:.2f}
방향: {analysis_data['orientation']}"""
    
    text_point = rg.Point3d(
        analysis_data['bbox'][0].X,
        analysis_data['bbox'][3].Y + 10,
        0
    )
    rs.AddText(info_text, text_point, height=2.0)
    
    # 중심점 표시
    rs.AddPoint(analysis_data['centroid'])
    rs.AddTextDot("중심", analysis_data['centroid'])
    
    # 인접 도로 표시
    for i, road_info in enumerate(adjacent_roads):
        # 접촉 구간 하이라이트
        if road_info['contact_length'] > 0:
            rs.ObjectColor(road_info['road'], (255, 0, 0))
            
            # 도로 정보 표시
            mid_point = rg.Point3d(
                (road_info['contact_point'].X + road_info['road_point'].X) / 2,
                (road_info['contact_point'].Y + road_info['road_point'].Y) / 2,
                0
            )
            rs.AddTextDot(f"도로{i+1}\n폭:{road_info['width']:.1f}m", mid_point)
    
    # 주변 건물 영향 표시
    for building_info in neighbors:
        if building_info['distance'] < 20:  # 20m 이내 건물
            rs.ObjectColor(building_info['building'], (200, 100, 100))
            
            # 영향선 표시
            line = rs.AddLine(
                analysis_data['centroid'],
                building_info.get('center', analysis_data['centroid'])
            )
            rs.ObjectLayer(line, "Analysis_Annotations")
            rs.ObjectLinetype(line, "Dashed")

def create_sample_site_context():
    """샘플 대지 및 주변 환경 생성"""
    # 대지
    site_pts = [
        (20, 20, 0), (80, 15, 0), (85, 60, 0),
        (70, 75, 0), (25, 70, 0), (20, 20, 0)
    ]
    site = rs.AddPolyline(site_pts)
    
    # 도로
    roads = []
    
    # 전면 도로
    road1_pts = [
        (0, 0, 0), (100, -5, 0), (100, 10, 0), (0, 15, 0), (0, 0, 0)
    ]
    roads.append(rs.AddPolyline(road1_pts))
    
    # 측면 도로
    road2_pts = [
        (90, -10, 0), (95, -10, 0), (100, 90, 0), 
        (85, 90, 0), (90, -10, 0)
    ]
    roads.append(rs.AddPolyline(road2_pts))
    
    # 주변 건물
    buildings = []
    
    # 북측 건물
    building1 = rs.AddRectangle((30, 85, 0), 30, 20)
    rs.SetUserText(building1, "height", "21")  # 7층
    buildings.append(building1)
    
    # 서측 건물
    building2 = rs.AddRectangle((0, 30, 0), 15, 25)
    rs.SetUserText(building2, "height", "15")  # 5층
    buildings.append(building2)
    
    # 동측 건물
    building3 = rs.AddRectangle((95, 25, 0), 20, 30)
    rs.SetUserText(building3, "height", "30")  # 10층
    buildings.append(building3)
    
    return site, roads, buildings

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 데이터 생성
    site, roads, buildings = create_sample_site_context()
    
    print("=== 대지 지오메트리 분석 ===")
    
    # 대지 분석
    site_analysis = analyze_site_geometry(site)
    print(f"\n대지 정보:")
    for key, value in site_analysis.items():
        if key not in ['bbox', 'centroid']:
            print(f"  {key}: {value}")
    
    # 인접 도로 분석
    adjacent_roads = find_adjacent_roads(site, roads)
    print(f"\n인접 도로: {len(adjacent_roads)}개")
    for i, road in enumerate(adjacent_roads):
        print(f"  도로 {i+1}: 폭 {road['width']:.1f}m, 접도장 {road['contact_length']:.1f}m")
    
    # 주변 건물 분석
    neighbors = analyze_neighboring_buildings(site, buildings)
    print(f"\n주변 건물: {len(neighbors)}개")
    for i, building in enumerate(neighbors):
        print(f"  건물 {i+1}: {building['direction']}측, 거리 {building['distance']:.1f}m, 높이 {building.get('height', 0):.0f}m")
    
    # 결과 시각화
    visualize_site_analysis(site, site_analysis, adjacent_roads, neighbors)
    
    # 줌 익스텐트
    rs.ZoomExtents()