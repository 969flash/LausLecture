# Lecture 3-4 - Practice 4: 층별 건물 라인 생성
# 목표 면적 및 사선 제한을 반영한 층별 윤곽선 생성

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class FloorByFloorGenerator:
    def __init__(self, site_boundary, building_params, buildable_volume):
        self.site_boundary = site_boundary
        self.params = building_params
        self.buildable_volume = buildable_volume
        self.site_area = rs.CurveArea(site_boundary)[0]
        self.floors = []
        
    def calculate_floor_requirements(self):
        """층별 요구사항 계산"""
        # 전체 목표 연면적
        target_gfa = self.site_area * self.params['floor_area_ratio']
        
        # 층별 용도 배분
        use_distribution = self.params.get('use_distribution', {})
        
        floor_requirements = []
        current_height = 0
        floor_num = 1
        
        while current_height < self.params['max_height'] and sum(req.get('area', 0) for req in floor_requirements) < target_gfa:
            # 층 높이
            if floor_num == 1:
                floor_height = self.params.get('first_floor_height', 4.5)
            else:
                floor_height = self.params.get('typical_floor_height', 3.5)
            
            # 용도 결정
            if floor_num == 1:
                use = 'commercial' if 'commercial' in use_distribution else 'residential'
            elif floor_num <= 3:
                use = 'commercial' if use_distribution.get('commercial', 0) > 0.3 else 'residential'
            else:
                use = 'residential'
            
            # 목표 면적
            remaining_gfa = target_gfa - sum(req.get('area', 0) for req in floor_requirements)
            if use == 'commercial':
                efficiency = 0.85  # 상업시설 효율
            else:
                efficiency = 0.80  # 주거시설 효율
            
            target_area = min(
                remaining_gfa,
                self.site_area * self.params['coverage_ratio'] * efficiency
            )
            
            floor_requirements.append({
                'floor': floor_num,
                'height': current_height,
                'floor_height': floor_height,
                'use': use,
                'target_area': target_area,
                'efficiency': efficiency
            })
            
            current_height += floor_height
            floor_num += 1
        
        return floor_requirements
    
    def generate_floor_outline(self, floor_info, base_outline=None):
        """개별 층 윤곽선 생성"""
        height = floor_info['height']
        target_area = floor_info['target_area']
        
        # 높이에서의 건축가능 영역 확인
        buildable_curve = self.get_buildable_curve_at_height(height)
        
        if not buildable_curve:
            return None
        
        # 기준 윤곽선 (이전 층 또는 건축가능 영역)
        if base_outline:
            reference_curve = rs.coercecurve(base_outline)
        else:
            reference_curve = buildable_curve
        
        # 목표 면적에 맞게 조정
        current_area = rs.CurveArea(buildable_curve)[0] if buildable_curve else 0
        
        if current_area > target_area:
            # 축소 필요
            scale_factor = math.sqrt(target_area / current_area)
            center = rs.CurveAreaCentroid(buildable_curve)[0]
            
            scaled_curve = rs.ScaleObject(
                rs.CopyObject(buildable_curve),
                center,
                [scale_factor, scale_factor, 1]
            )
            
            return scaled_curve
        else:
            # 건축가능 영역 전체 사용
            return rs.CopyObject(buildable_curve)
    
    def get_buildable_curve_at_height(self, height):
        """특정 높이에서의 건축가능 영역 커브"""
        if not self.buildable_volume:
            return None
        
        # 수평 평면 생성
        plane = rg.Plane(rg.Point3d(0, 0, height), rg.Vector3d.ZAxis)
        
        # 볼륨과 평면의 교선
        brep = self.buildable_volume
        curves = rg.Brep.CreateContourCurves(brep, plane)
        
        if curves and len(curves) > 0:
            # 가장 큰 커브 선택
            largest_curve = max(curves, key=lambda c: rg.AreaMassProperties.Compute(c).Area)
            curve_id = sc.doc.Objects.AddCurve(largest_curve)
            return curve_id
        
        return None
    
    def apply_setback_rules(self, floor_outline, floor_info):
        """층별 추가 셋백 규칙 적용"""
        # 고층부 추가 셋백
        if floor_info['floor'] > 5:
            additional_setback = (floor_info['floor'] - 5) * 0.5  # 5층 이상 층당 0.5m
            center = rs.CurveAreaCentroid(floor_outline)[0]
            
            setback_curve = rs.OffsetCurve(
                floor_outline,
                center,
                -additional_setback
            )
            
            if setback_curve:
                rs.DeleteObject(floor_outline)
                return setback_curve[0]
        
        return floor_outline
    
    def optimize_floor_layout(self, floor_outline, floor_info):
        """층 레이아웃 최적화"""
        use_type = floor_info['use']
        
        if use_type == 'residential':
            # 주거: 코어 위치 최적화
            return self.optimize_residential_layout(floor_outline)
        else:
            # 상업: 임대 효율 최적화
            return self.optimize_commercial_layout(floor_outline)
    
    def optimize_residential_layout(self, floor_outline):
        """주거 레이아웃 최적화"""
        # 중심 코어 방식
        center = rs.CurveAreaCentroid(floor_outline)[0]
        
        # 코어 크기 (전체의 15%)
        floor_area = rs.CurveArea(floor_outline)[0]
        core_area = floor_area * 0.15
        core_size = math.sqrt(core_area)
        
        # 코어 표시
        core_corner = rg.Point3d(
            center.X - core_size/2,
            center.Y - core_size/2,
            center.Z
        )
        
        core = rs.AddRectangle(core_corner, core_size, core_size)
        rs.SetUserText(core, "type", "core")
        
        return floor_outline, core
    
    def optimize_commercial_layout(self, floor_outline):
        """상업 레이아웃 최적화"""
        # 측면 코어 방식 (임대면적 극대화)
        bbox = rs.BoundingBox(floor_outline)
        
        # 코어 위치 (북측)
        core_width = 8
        core_depth = 6
        
        core_corner = rg.Point3d(
            bbox[0].X,
            bbox[3].Y - core_depth,
            bbox[0].Z
        )
        
        core = rs.AddRectangle(core_corner, core_width, core_depth)
        rs.SetUserText(core, "type", "core")
        
        return floor_outline, core
    
    def generate_all_floors(self):
        """전체 층 생성"""
        floor_requirements = self.calculate_floor_requirements()
        
        previous_outline = None
        floor_data = []
        
        for floor_info in floor_requirements:
            print(f"층 {floor_info['floor']} 생성 중 (높이: {floor_info['height']}m)")
            
            # 층 윤곽선 생성
            floor_outline = self.generate_floor_outline(floor_info, previous_outline)
            
            if floor_outline:
                # 셋백 규칙 적용
                floor_outline = self.apply_setback_rules(floor_outline, floor_info)
                
                # 레이아웃 최적화
                optimized_outline, core = self.optimize_floor_layout(floor_outline, floor_info)
                
                # 3D 위치로 이동
                rs.MoveObject(optimized_outline, (0, 0, floor_info['height']))
                if core:
                    rs.MoveObject(core, (0, 0, floor_info['height']))
                
                # 정보 저장
                actual_area = rs.CurveArea(optimized_outline)[0]
                floor_info['actual_area'] = actual_area
                floor_info['outline'] = optimized_outline
                floor_info['core'] = core
                
                floor_data.append(floor_info)
                previous_outline = rs.CopyObject(optimized_outline)
                rs.MoveObject(previous_outline, (0, 0, -floor_info['height']))
            else:
                print(f"  층 {floor_info['floor']} 생성 실패")
        
        return floor_data

def create_floor_mass_model(floor_data):
    """층별 데이터로 매스 모델 생성"""
    masses = []
    
    for i, floor in enumerate(floor_data):
        if i < len(floor_data) - 1:
            # 다음 층까지 압출
            height = floor_data[i+1]['height'] - floor['height']
        else:
            # 마지막 층
            height = floor['floor_height']
        
        # 매스 생성
        curve = rs.coercecurve(floor['outline'])
        
        extrusion = rg.Extrusion.Create(
            curve,
            height,
            True
        )
        
        if extrusion:
            brep = extrusion.ToBrep()
            mass_id = sc.doc.Objects.AddBrep(brep)
            
            # 용도별 색상
            if floor['use'] == 'commercial':
                rs.ObjectColor(mass_id, (100, 200, 255))
            else:
                rs.ObjectColor(mass_id, (255, 200, 100))
            
            masses.append(mass_id)
    
    return masses

def visualize_floor_analysis(floor_data, site_boundary):
    """층별 분석 시각화"""
    # 레이어 생성
    layers = {
        "Site": (200, 200, 200),
        "Floor_Outlines": (0, 0, 0),
        "Floor_Cores": (255, 0, 0),
        "Floor_Mass": (150, 150, 150),
        "Analysis_Text": (0, 0, 0)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 대지
    rs.ObjectLayer(site_boundary, "Site")
    
    # 층별 정보
    total_gfa = 0
    
    for floor in floor_data:
        if floor.get('outline'):
            rs.ObjectLayer(floor['outline'], "Floor_Outlines")
            
            # 층 정보 텍스트
            center = rs.CurveAreaCentroid(floor['outline'])[0]
            info = f"{floor['floor']}F ({floor['use']})\n{floor['actual_area']:.0f}m²"
            text_dot = rs.AddTextDot(info, center)
            rs.ObjectLayer(text_dot, "Analysis_Text")
            
            total_gfa += floor['actual_area']
        
        if floor.get('core'):
            rs.ObjectLayer(floor['core'], "Floor_Cores")
            rs.ObjectColor(floor['core'], (255, 0, 0))
    
    # 전체 분석 정보
    site_area = rs.CurveArea(site_boundary)[0]
    
    bbox = rs.BoundingBox(site_boundary)
    text_point = rg.Point3d(bbox[0].X, bbox[3].Y + 10, 0)
    
    analysis_text = f"""층별 건물 분석
총 층수: {len(floor_data)}층
총 연면적: {total_gfa:.0f}m²
실현 용적률: {total_gfa/site_area*100:.1f}%
평균 층면적: {total_gfa/len(floor_data):.0f}m²"""
    
    rs.AddText(analysis_text, text_point, height=3.0)

def create_sample_buildable_volume(site_boundary):
    """샘플 건축가능 볼륨 생성 (간단한 버전)"""
    # 이격거리 적용
    center = rs.CurveAreaCentroid(site_boundary)[0]
    buildable_boundary = rs.OffsetCurve(site_boundary, center, -3.0)[0]
    
    # 기본 높이로 압출
    curve = rs.coercecurve(buildable_boundary)
    max_height = 50
    
    # 사선 제한 적용 (간단한 테이퍼)
    bottom_curve = curve
    top_curve = rs.ScaleObject(
        rs.CopyObject(buildable_boundary),
        center,
        [0.7, 0.7, 1]
    )
    rs.MoveObject(top_curve, (0, 0, max_height))
    
    # Loft로 볼륨 생성
    loft_curves = [bottom_curve, top_curve]
    loft_surface = rs.AddLoftSrf(loft_curves)
    
    if loft_surface:
        # Brep으로 변환
        brep = rs.coercebrep(loft_surface[0])
        rs.DeleteObject(loft_surface[0])
        rs.DeleteObject(top_curve)
        return brep
    
    return None

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 대지
    site = rs.AddRectangle((0, 0, 0), 40, 50)
    
    # 건물 파라미터
    building_params = {
        'floor_area_ratio': 3.5,
        'coverage_ratio': 0.6,
        'max_height': 50,
        'max_floors': 15,
        'first_floor_height': 4.5,
        'typical_floor_height': 3.3,
        'use_distribution': {
            'commercial': 0.2,
            'residential': 0.8
        }
    }
    
    print("=== 층별 건물 라인 생성 ===")
    
    # 건축가능 볼륨 생성
    buildable_volume = create_sample_buildable_volume(site)
    
    if buildable_volume:
        # 층별 생성기
        generator = FloorByFloorGenerator(site, building_params, buildable_volume)
        
        # 전체 층 생성
        floor_data = generator.generate_all_floors()
        
        print(f"\n생성된 층수: {len(floor_data)}")
        
        # 매스 모델 생성
        masses = create_floor_mass_model(floor_data)
        
        # 분석 시각화
        visualize_floor_analysis(floor_data, site)
        
        # 3D 뷰 설정
        rs.Command("_SetView _World _Perspective", False)
        rs.ZoomExtents()
    else:
        print("건축가능 볼륨 생성 실패")