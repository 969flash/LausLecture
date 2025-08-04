# Lecture 5 - Practice 1: 공개공지 설계 자동화
# 법적 요구사항을 충족하는 공개공지 자동 배치 및 설계

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class PublicSpaceDesigner:
    def __init__(self, site_boundary, building_footprint, requirements):
        self.site_boundary = site_boundary
        self.building_footprint = building_footprint
        self.requirements = requirements
        self.site_area = rs.CurveArea(site_boundary)[0]
        
    def calculate_required_area(self):
        """필요 공개공지 면적 계산"""
        # 법적 의무 비율 (일반적으로 대지면적의 5~10%)
        min_ratio = self.requirements.get('min_ratio', 0.05)
        
        # 용적률 인센티브를 위한 추가 면적
        if self.requirements.get('incentive_eligible', False):
            target_ratio = self.requirements.get('target_ratio', 0.10)
        else:
            target_ratio = min_ratio
        
        self.required_area = self.site_area * target_ratio
        return self.required_area
    
    def find_optimal_locations(self):
        """공개공지 최적 위치 찾기"""
        locations = []
        
        # 1. 전면 도로변
        front_location = self.find_frontage_location()
        if front_location:
            locations.append({
                'type': 'frontage',
                'priority': 1,
                'geometry': front_location,
                'score': self.evaluate_location(front_location)
            })
        
        # 2. 코너 (가각전제)
        corner_locations = self.find_corner_locations()
        for corner in corner_locations:
            locations.append({
                'type': 'corner',
                'priority': 2,
                'geometry': corner,
                'score': self.evaluate_location(corner)
            })
        
        # 3. 건물 측면
        side_locations = self.find_side_locations()
        for side in side_locations:
            locations.append({
                'type': 'side',
                'priority': 3,
                'geometry': side,
                'score': self.evaluate_location(side)
            })
        
        # 점수순 정렬
        locations.sort(key=lambda x: x['score'], reverse=True)
        return locations
    
    def find_frontage_location(self):
        """전면 도로변 위치 찾기"""
        # 대지와 건물 사이 공간
        site_curve = rs.coercecurve(self.site_boundary)
        building_curve = rs.coercecurve(self.building_footprint)
        
        # 대지 남측 경계 (주도로 가정)
        bbox = rs.BoundingBox(self.site_boundary)
        south_edge_pts = [
            (bbox[0].X, bbox[0].Y, 0),
            (bbox[1].X, bbox[0].Y, 0)
        ]
        
        # 전면 공지 영역
        front_space_pts = []
        
        # 건물 전면선
        building_bbox = rs.BoundingBox(self.building_footprint)
        setback_depth = building_bbox[0].Y - bbox[0].Y
        
        if setback_depth > 3:  # 최소 3m 이상
            # 전면 공지 경계
            width = min(self.required_area / setback_depth, bbox[1].X - bbox[0].X)
            
            pts = [
                (bbox[0].X, bbox[0].Y, 0),
                (bbox[0].X + width, bbox[0].Y, 0),
                (bbox[0].X + width, building_bbox[0].Y, 0),
                (bbox[0].X, building_bbox[0].Y, 0),
                (bbox[0].X, bbox[0].Y, 0)
            ]
            
            return rs.AddPolyline(pts)
        
        return None
    
    def find_corner_locations(self):
        """코너 위치 찾기"""
        corners = []
        bbox = rs.BoundingBox(self.site_boundary)
        
        # 코너별 공개공지 가능 영역
        corner_size = math.sqrt(self.required_area / 2)  # 정사각형 가정
        
        # SW 코너
        sw_pts = [
            (bbox[0].X, bbox[0].Y, 0),
            (bbox[0].X + corner_size, bbox[0].Y, 0),
            (bbox[0].X + corner_size, bbox[0].Y + corner_size, 0),
            (bbox[0].X, bbox[0].Y + corner_size, 0),
            (bbox[0].X, bbox[0].Y, 0)
        ]
        
        sw_corner = rs.AddPolyline(sw_pts)
        if not self.check_building_conflict(sw_corner):
            corners.append(sw_corner)
        else:
            rs.DeleteObject(sw_corner)
        
        # SE 코너
        se_pts = [
            (bbox[1].X - corner_size, bbox[0].Y, 0),
            (bbox[1].X, bbox[0].Y, 0),
            (bbox[1].X, bbox[0].Y + corner_size, 0),
            (bbox[1].X - corner_size, bbox[0].Y + corner_size, 0),
            (bbox[1].X - corner_size, bbox[0].Y, 0)
        ]
        
        se_corner = rs.AddPolyline(se_pts)
        if not self.check_building_conflict(se_corner):
            corners.append(se_corner)
        else:
            rs.DeleteObject(se_corner)
        
        return corners
    
    def find_side_locations(self):
        """측면 위치 찾기"""
        sides = []
        
        # 건물과 대지 경계 사이 공간 분석
        building_bbox = rs.BoundingBox(self.building_footprint)
        site_bbox = rs.BoundingBox(self.site_boundary)
        
        # 서측 공간
        west_space = building_bbox[0].X - site_bbox[0].X
        if west_space > 5:  # 최소 5m
            depth = self.required_area / (building_bbox[3].Y - building_bbox[0].Y)
            if depth < west_space:
                pts = [
                    (building_bbox[0].X - depth, building_bbox[0].Y, 0),
                    (building_bbox[0].X, building_bbox[0].Y, 0),
                    (building_bbox[0].X, building_bbox[3].Y, 0),
                    (building_bbox[0].X - depth, building_bbox[3].Y, 0),
                    (building_bbox[0].X - depth, building_bbox[0].Y, 0)
                ]
                sides.append(rs.AddPolyline(pts))
        
        # 동측 공간
        east_space = site_bbox[1].X - building_bbox[1].X
        if east_space > 5:
            depth = self.required_area / (building_bbox[3].Y - building_bbox[0].Y)
            if depth < east_space:
                pts = [
                    (building_bbox[1].X, building_bbox[0].Y, 0),
                    (building_bbox[1].X + depth, building_bbox[0].Y, 0),
                    (building_bbox[1].X + depth, building_bbox[3].Y, 0),
                    (building_bbox[1].X, building_bbox[3].Y, 0),
                    (building_bbox[1].X, building_bbox[0].Y, 0)
                ]
                sides.append(rs.AddPolyline(pts))
        
        return sides
    
    def check_building_conflict(self, space_boundary):
        """건물과 충돌 확인"""
        space_curve = rs.coercecurve(space_boundary)
        building_curve = rs.coercecurve(self.building_footprint)
        
        # 교차 확인
        intersections = rg.Intersect.Intersection.CurveCurve(
            space_curve, building_curve, 0.01, 0.01
        )
        
        return intersections.Count > 0
    
    def evaluate_location(self, location):
        """위치 평가 점수"""
        score = 0
        
        # 면적 점수
        area = rs.CurveArea(location)[0]
        area_score = min(area / self.required_area * 50, 50)
        score += area_score
        
        # 접근성 점수 (도로 인접)
        # 남측(전면) 인접 확인
        bbox = rs.BoundingBox(location)
        site_bbox = rs.BoundingBox(self.site_boundary)
        
        if abs(bbox[0].Y - site_bbox[0].Y) < 1:
            score += 30  # 전면 도로 인접
        
        # 형태 점수 (정형성)
        perimeter = rs.CurveLength(location)
        compactness = 4 * math.pi * area / (perimeter * perimeter)
        score += compactness * 20
        
        return score
    
    def design_public_space(self, location_info):
        """공개공지 상세 설계"""
        boundary = location_info['geometry']
        space_type = location_info['type']
        
        elements = {
            'boundary': boundary,
            'trees': [],
            'benches': [],
            'paving': None,
            'features': []
        }
        
        # 포장 영역
        elements['paving'] = rs.CopyObject(boundary)
        
        # 조경 요소 배치
        if space_type == 'frontage':
            elements = self.design_frontage_space(elements)
        elif space_type == 'corner':
            elements = self.design_corner_space(elements)
        else:
            elements = self.design_side_space(elements)
        
        return elements
    
    def design_frontage_space(self, elements):
        """전면 공개공지 설계"""
        boundary = elements['boundary']
        bbox = rs.BoundingBox(boundary)
        
        # 가로수 배치 (6m 간격)
        tree_spacing = 6
        num_trees = int((bbox[1].X - bbox[0].X) / tree_spacing)
        
        for i in range(num_trees):
            x = bbox[0].X + (i + 0.5) * tree_spacing
            y = bbox[0].Y + 2  # 도로에서 2m
            
            tree = rs.AddCircle((x, y, 0), 1.5)  # 수관 반경 1.5m
            elements['trees'].append(tree)
            rs.SetUserText(tree, "type", "tree")
            rs.SetUserText(tree, "species", "느티나무")
        
        # 벤치 배치 (12m 간격)
        bench_spacing = 12
        num_benches = int((bbox[1].X - bbox[0].X) / bench_spacing)
        
        for i in range(num_benches):
            x = bbox[0].X + (i + 0.5) * bench_spacing
            y = (bbox[0].Y + bbox[3].Y) / 2
            
            bench = rs.AddRectangle((x-1, y-0.4, 0), 2, 0.8)
            elements['benches'].append(bench)
            rs.SetUserText(bench, "type", "bench")
        
        # 보행로
        walkway_pts = [
            (bbox[0].X, bbox[0].Y + 1, 0),
            (bbox[1].X, bbox[0].Y + 1, 0),
            (bbox[1].X, bbox[0].Y + 3, 0),
            (bbox[0].X, bbox[0].Y + 3, 0),
            (bbox[0].X, bbox[0].Y + 1, 0)
        ]
        walkway = rs.AddPolyline(walkway_pts)
        elements['features'].append(walkway)
        rs.SetUserText(walkway, "type", "walkway")
        
        return elements
    
    def design_corner_space(self, elements):
        """코너 공개공지 설계"""
        boundary = elements['boundary']
        center = rs.CurveAreaCentroid(boundary)[0]
        
        # 중앙 조형물
        feature = rs.AddCircle(center, 2)
        elements['features'].append(feature)
        rs.SetUserText(feature, "type", "sculpture")
        
        # 원형 수목 배치
        for angle in range(0, 360, 60):
            rad = math.radians(angle)
            x = center.X + 4 * math.cos(rad)
            y = center.Y + 4 * math.sin(rad)
            
            tree = rs.AddCircle((x, y, 0), 1)
            elements['trees'].append(tree)
            rs.SetUserText(tree, "type", "tree")
        
        # 원형 벤치
        circular_bench = rs.AddCircle(center, 5)
        elements['benches'].append(circular_bench)
        rs.SetUserText(circular_bench, "type", "circular_bench")
        
        return elements
    
    def design_side_space(self, elements):
        """측면 공개공지 설계"""
        boundary = elements['boundary']
        bbox = rs.BoundingBox(boundary)
        
        # 선형 녹지대
        green_strip_pts = [
            (bbox[0].X + 1, bbox[0].Y, 0),
            (bbox[1].X - 1, bbox[0].Y, 0),
            (bbox[1].X - 1, bbox[3].Y, 0),
            (bbox[0].X + 1, bbox[3].Y, 0),
            (bbox[0].X + 1, bbox[0].Y, 0)
        ]
        green_strip = rs.AddPolyline(green_strip_pts)
        elements['features'].append(green_strip)
        rs.SetUserText(green_strip, "type", "planting_strip")
        
        # 수목 열식
        tree_spacing = 5
        num_trees = int((bbox[3].Y - bbox[0].Y) / tree_spacing)
        
        for i in range(num_trees):
            x = (bbox[0].X + bbox[1].X) / 2
            y = bbox[0].Y + (i + 0.5) * tree_spacing
            
            tree = rs.AddCircle((x, y, 0), 0.8)
            elements['trees'].append(tree)
            rs.SetUserText(tree, "type", "tree")
        
        return elements
    
    def calculate_incentives(self, public_space_area):
        """용적률 인센티브 계산"""
        # 기본 인센티브율
        base_incentive = 0.2  # 20%
        
        # 면적 비율에 따른 가중치
        area_ratio = public_space_area / self.site_area
        
        if area_ratio >= 0.1:  # 10% 이상
            incentive_multiplier = 1.2
        elif area_ratio >= 0.07:  # 7% 이상
            incentive_multiplier = 1.0
        else:
            incentive_multiplier = 0.5
        
        # 최종 인센티브
        final_incentive = base_incentive * incentive_multiplier
        
        return {
            'incentive_rate': final_incentive,
            'additional_far': self.site_area * final_incentive,
            'conditions': self.get_incentive_conditions(area_ratio)
        }
    
    def get_incentive_conditions(self, area_ratio):
        """인센티브 조건"""
        conditions = []
        
        if area_ratio >= 0.05:
            conditions.append("24시간 공개")
            conditions.append("보행자 통행 가능")
        
        if area_ratio >= 0.07:
            conditions.append("휴게시설 설치")
            conditions.append("조경면적 50% 이상")
        
        if area_ratio >= 0.1:
            conditions.append("문화시설 연계")
            conditions.append("이벤트 공간 제공")
        
        return conditions

def visualize_public_space(site_boundary, building_footprint, public_space_elements, analysis_info):
    """공개공지 시각화"""
    # 레이어 생성
    layers = {
        "Site": (200, 200, 200),
        "Building": (150, 150, 150),
        "PublicSpace_Boundary": (0, 255, 0),
        "PublicSpace_Trees": (0, 150, 0),
        "PublicSpace_Furniture": (100, 50, 0),
        "PublicSpace_Features": (200, 200, 0)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 대지 및 건물
    rs.ObjectLayer(site_boundary, "Site")
    rs.ObjectLayer(building_footprint, "Building")
    rs.ObjectColor(building_footprint, (150, 150, 150))
    
    # 공개공지 요소
    if public_space_elements:
        # 경계
        rs.ObjectLayer(public_space_elements['boundary'], "PublicSpace_Boundary")
        rs.ObjectColor(public_space_elements['boundary'], (0, 255, 0))
        
        # 수목
        for tree in public_space_elements['trees']:
            rs.ObjectLayer(tree, "PublicSpace_Trees")
            rs.ObjectColor(tree, (0, 150, 0))
        
        # 벤치
        for bench in public_space_elements['benches']:
            rs.ObjectLayer(bench, "PublicSpace_Furniture")
            rs.ObjectColor(bench, (100, 50, 0))
        
        # 기타 시설
        for feature in public_space_elements['features']:
            rs.ObjectLayer(feature, "PublicSpace_Features")
            rs.ObjectColor(feature, (200, 200, 0))
    
    # 분석 정보
    if analysis_info:
        bbox = rs.BoundingBox(site_boundary)
        text_point = rg.Point3d(bbox[0].X, bbox[3].Y + 5, 0)
        
        info_text = f"""공개공지 분석
필요 면적: {analysis_info['required_area']:.2f}m²
제공 면적: {analysis_info['provided_area']:.2f}m²
인센티브: {analysis_info['incentive_rate']*100:.0f}%
추가 용적률: {analysis_info['additional_far']:.0f}m²"""
        
        rs.AddText(info_text, text_point, height=2.0)

def create_sample_project():
    """샘플 프로젝트 생성"""
    # 대지
    site = rs.AddRectangle((0, 0, 0), 60, 50)
    
    # 건물
    building = rs.AddRectangle((10, 15, 0), 40, 25)
    
    # 공개공지 요구사항
    requirements = {
        'min_ratio': 0.05,  # 최소 5%
        'target_ratio': 0.08,  # 목표 8%
        'incentive_eligible': True
    }
    
    return site, building, requirements

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 프로젝트 생성
    site, building, requirements = create_sample_project()
    
    print("=== 공개공지 설계 자동화 ===")
    
    # 공개공지 설계기
    designer = PublicSpaceDesigner(site, building, requirements)
    
    # 필요 면적 계산
    required_area = designer.calculate_required_area()
    print(f"\n필요 공개공지 면적: {required_area:.2f}m²")
    
    # 최적 위치 찾기
    locations = designer.find_optimal_locations()
    print(f"\n가능한 위치: {len(locations)}개")
    
    if locations:
        # 최적 위치 선택
        best_location = locations[0]
        print(f"선택된 위치: {best_location['type']} (점수: {best_location['score']:.1f})")
        
        # 상세 설계
        public_space = designer.design_public_space(best_location)
        
        # 인센티브 계산
        actual_area = rs.CurveArea(best_location['geometry'])[0]
        incentives = designer.calculate_incentives(actual_area)
        
        print(f"\n제공 면적: {actual_area:.2f}m²")
        print(f"인센티브율: {incentives['incentive_rate']*100:.0f}%")
        print(f"추가 용적률: {incentives['additional_far']:.0f}m²")
        
        # 분석 정보
        analysis_info = {
            'required_area': required_area,
            'provided_area': actual_area,
            'incentive_rate': incentives['incentive_rate'],
            'additional_far': incentives['additional_far']
        }
        
        # 시각화
        visualize_public_space(site, building, public_space, analysis_info)
        
        # 다른 위치 옵션 표시
        for i, location in enumerate(locations[1:3]):  # 상위 3개
            rs.ObjectColor(location['geometry'], (255, 200, 200))
            center = rs.CurveAreaCentroid(location['geometry'])[0]
            rs.AddTextDot(f"옵션{i+2}", center)
    
    # 줌 익스텐트
    rs.ZoomExtents()