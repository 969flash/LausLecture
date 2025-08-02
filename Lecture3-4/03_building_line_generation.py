# Lecture 3-4 - Practice 3: 건물 라인 생성
# 용도, 건폐율, 용적률 및 규제를 반영한 건물 외곽선 생성

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class BuildingLineGenerator:
    def __init__(self, site_boundary, building_params):
        self.site_boundary = site_boundary
        self.params = building_params
        self.site_area = rs.CurveArea(site_boundary)[0]
        self.site_centroid = rs.CurveAreaCentroid(site_boundary)[0]
        
    def calculate_required_area(self):
        """필요 건축면적 계산"""
        # 건폐율 기준 최대 건축면적
        max_building_area = self.site_area * self.params['coverage_ratio']
        
        # 용적률 기준 필요 연면적
        target_gfa = self.site_area * self.params['floor_area_ratio']
        
        # 예상 층수로 필요 건축면적 계산
        estimated_floors = min(
            self.params.get('max_floors', 10),
            int(self.params.get('max_height', 30) / self.params.get('floor_height', 3.5))
        )
        
        required_area = target_gfa / estimated_floors
        
        # 건폐율 한계 내에서 조정
        self.building_area = min(required_area, max_building_area)
        self.floors = math.ceil(target_gfa / self.building_area)
        
        return self.building_area, self.floors
    
    def apply_setbacks(self):
        """법정 이격거리 적용"""
        setbacks = self.params.get('setbacks', {})
        
        # 용도별 기본 이격거리
        use_type = self.params.get('use_type', 'residential')
        if use_type == 'residential':
            default_setback = max(setbacks.get('residential', 2.0), 2.0)
        elif use_type == 'commercial':
            default_setback = max(setbacks.get('commercial', 3.0), 3.0)
        else:  # mixed-use
            default_setback = max(setbacks.get('mixed', 2.5), 2.5)
        
        # 대지경계선에서 이격
        offset_curve = rs.OffsetCurve(
            self.site_boundary,
            self.site_centroid,
            -default_setback
        )
        
        if offset_curve:
            self.buildable_boundary = offset_curve[0]
            self.buildable_area = rs.CurveArea(self.buildable_boundary)[0]
            return True
        
        return False
    
    def generate_building_footprint(self):
        """건물 외곽선 생성"""
        building_type = self.params.get('building_type', 'rectangular')
        
        if building_type == 'rectangular':
            return self.generate_rectangular_footprint()
        elif building_type == 'L_shaped':
            return self.generate_l_shaped_footprint()
        elif building_type == 'courtyard':
            return self.generate_courtyard_footprint()
        else:
            return self.generate_fitted_footprint()
    
    def generate_rectangular_footprint(self):
        """직사각형 건물 외곽선"""
        # 건축가능 영역의 바운딩 박스
        bbox = rs.BoundingBox(self.buildable_boundary)
        if not bbox:
            return None
        
        # 중심점
        center_pt = rg.Point3d(
            (bbox[0].X + bbox[1].X) / 2,
            (bbox[0].Y + bbox[3].Y) / 2,
            0
        )
        
        # 목표 면적에 맞는 크기 계산
        bbox_width = bbox[1].X - bbox[0].X
        bbox_depth = bbox[3].Y - bbox[0].Y
        aspect_ratio = bbox_width / bbox_depth
        
        # 건물 크기 계산
        building_depth = math.sqrt(self.building_area / aspect_ratio)
        building_width = building_depth * aspect_ratio
        
        # 크기 조정 (건축가능 영역 내)
        if building_width > bbox_width * 0.9:
            building_width = bbox_width * 0.9
            building_depth = self.building_area / building_width
        
        if building_depth > bbox_depth * 0.9:
            building_depth = bbox_depth * 0.9
            building_width = self.building_area / building_depth
        
        # 건물 외곽선 생성
        corner1 = rg.Point3d(
            center_pt.X - building_width/2,
            center_pt.Y - building_depth/2,
            0
        )
        
        footprint = rs.AddRectangle(corner1, building_width, building_depth)
        
        # 건축가능 영역 내부 확인
        if self.is_within_buildable_area(footprint):
            return footprint
        else:
            # 위치 조정
            return self.adjust_position(footprint)
    
    def generate_l_shaped_footprint(self):
        """L자형 건물 외곽선"""
        bbox = rs.BoundingBox(self.buildable_boundary)
        if not bbox:
            return None
        
        # L자 비율 (전체의 60%를 메인, 40%를 날개)
        main_ratio = 0.6
        wing_ratio = 0.4
        
        # 메인 부분
        main_area = self.building_area * main_ratio
        wing_area = self.building_area * wing_ratio
        
        # 크기 계산
        main_width = bbox[1].X - bbox[0].X - 10
        main_depth = main_area / main_width
        
        wing_width = main_width * 0.5
        wing_depth = wing_area / wing_width
        
        # L자 점들
        pts = [
            (bbox[0].X + 5, bbox[0].Y + 5, 0),
            (bbox[0].X + 5 + main_width, bbox[0].Y + 5, 0),
            (bbox[0].X + 5 + main_width, bbox[0].Y + 5 + wing_depth, 0),
            (bbox[0].X + 5 + wing_width, bbox[0].Y + 5 + wing_depth, 0),
            (bbox[0].X + 5 + wing_width, bbox[0].Y + 5 + main_depth, 0),
            (bbox[0].X + 5, bbox[0].Y + 5 + main_depth, 0),
            (bbox[0].X + 5, bbox[0].Y + 5, 0)
        ]
        
        footprint = rs.AddPolyline(pts)
        
        if self.is_within_buildable_area(footprint):
            return footprint
        else:
            return self.adjust_position(footprint)
    
    def generate_courtyard_footprint(self):
        """중정형 건물 외곽선"""
        # 외부 사각형
        outer = self.generate_rectangular_footprint()
        if not outer:
            return None
        
        # 중정 크기 (전체의 20%)
        courtyard_ratio = 0.2
        outer_bbox = rs.BoundingBox(outer)
        
        courtyard_width = (outer_bbox[1].X - outer_bbox[0].X) * courtyard_ratio
        courtyard_depth = (outer_bbox[3].Y - outer_bbox[0].Y) * courtyard_ratio
        
        # 중정 중심
        center_pt = rg.Point3d(
            (outer_bbox[0].X + outer_bbox[1].X) / 2,
            (outer_bbox[0].Y + outer_bbox[3].Y) / 2,
            0
        )
        
        # 중정 생성
        courtyard_corner = rg.Point3d(
            center_pt.X - courtyard_width/2,
            center_pt.Y - courtyard_depth/2,
            0
        )
        
        courtyard = rs.AddRectangle(courtyard_corner, courtyard_width, courtyard_depth)
        
        # Boolean 차집합으로 중정형 생성
        result = rs.CurveBooleanDifference(outer, courtyard)
        
        if result:
            rs.DeleteObjects([outer, courtyard])
            return result[0]
        
        return outer
    
    def generate_fitted_footprint(self):
        """대지 형태에 맞춘 건물 외곽선"""
        # 건축가능 영역을 스케일 조정
        scale_factor = math.sqrt(self.building_area / self.buildable_area)
        
        # 중심점 기준 스케일
        scaled = rs.ScaleObject(
            rs.CopyObject(self.buildable_boundary),
            self.site_centroid,
            [scale_factor, scale_factor, 1]
        )
        
        return scaled
    
    def is_within_buildable_area(self, footprint):
        """건물이 건축가능 영역 내에 있는지 확인"""
        footprint_curve = rs.coercecurve(footprint)
        buildable_curve = rs.coercecurve(self.buildable_boundary)
        
        # 샘플 포인트로 확인
        for i in range(10):
            t = i / 9.0
            param = footprint_curve.Domain.ParameterAt(t)
            point = footprint_curve.PointAt(param)
            
            # 점이 건축가능 영역 내부에 있는지 확인
            if buildable_curve.Contains(point) != rg.PointContainment.Inside:
                return False
        
        return True
    
    def adjust_position(self, footprint):
        """건물 위치 조정"""
        # 건축가능 영역 중심으로 이동
        footprint_center = rs.CurveAreaCentroid(footprint)[0]
        buildable_center = rs.CurveAreaCentroid(self.buildable_boundary)[0]
        
        translation = buildable_center - footprint_center
        adjusted = rs.MoveObject(footprint, translation)
        
        return adjusted
    
    def add_building_info(self, footprint):
        """건물 정보 추가"""
        if not footprint:
            return
        
        # 속성 추가
        rs.SetUserText(footprint, "use_type", self.params.get('use_type', 'residential'))
        rs.SetUserText(footprint, "floors", str(self.floors))
        rs.SetUserText(footprint, "height", str(self.floors * self.params.get('floor_height', 3.5)))
        rs.SetUserText(footprint, "building_area", str(rs.CurveArea(footprint)[0]))
        rs.SetUserText(footprint, "gfa", str(rs.CurveArea(footprint)[0] * self.floors))

def create_sample_building_params():
    """샘플 건물 파라미터 생성"""
    params_list = [
        {
            'name': '주거용 건물',
            'use_type': 'residential',
            'building_type': 'rectangular',
            'coverage_ratio': 0.6,
            'floor_area_ratio': 2.0,
            'max_floors': 7,
            'max_height': 25,
            'floor_height': 3.2,
            'setbacks': {'residential': 2.0}
        },
        {
            'name': '상업용 건물',
            'use_type': 'commercial',
            'building_type': 'L_shaped',
            'coverage_ratio': 0.7,
            'floor_area_ratio': 3.0,
            'max_floors': 10,
            'max_height': 40,
            'floor_height': 4.0,
            'setbacks': {'commercial': 3.0}
        },
        {
            'name': '주상복합 건물',
            'use_type': 'mixed',
            'building_type': 'courtyard',
            'coverage_ratio': 0.65,
            'floor_area_ratio': 2.5,
            'max_floors': 15,
            'max_height': 50,
            'floor_height': 3.5,
            'setbacks': {'mixed': 2.5}
        }
    ]
    
    return params_list

def visualize_building_lines(site_boundary, building_footprints):
    """건물 라인 시각화"""
    # 레이어 생성
    layers = {
        "Site": (200, 200, 200),
        "Building_Residential": (255, 200, 100),
        "Building_Commercial": (100, 200, 255),
        "Building_Mixed": (200, 100, 255)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 대지
    rs.ObjectLayer(site_boundary, "Site")
    
    # 건물별 표시
    for footprint in building_footprints:
        if footprint:
            use_type = rs.GetUserText(footprint, "use_type")
            
            if use_type == "residential":
                rs.ObjectLayer(footprint, "Building_Residential")
                color = (255, 200, 100)
            elif use_type == "commercial":
                rs.ObjectLayer(footprint, "Building_Commercial")
                color = (100, 200, 255)
            else:
                rs.ObjectLayer(footprint, "Building_Mixed")
                color = (200, 100, 255)
            
            rs.ObjectColor(footprint, color)
            
            # 정보 표시
            center = rs.CurveAreaCentroid(footprint)[0]
            floors = rs.GetUserText(footprint, "floors")
            area = rs.GetUserText(footprint, "building_area")
            
            info = f"{use_type}\n{floors}F\n{float(area):.0f}m²"
            rs.AddTextDot(info, center)

def create_sample_sites():
    """다양한 대지 샘플 생성"""
    sites = []
    
    # 정형 대지
    site1 = rs.AddRectangle((0, 0, 0), 50, 40)
    sites.append(site1)
    
    # 부정형 대지
    site2_pts = [
        (60, 0, 0), (110, 5, 0), (108, 38, 0),
        (65, 42, 0), (60, 0, 0)
    ]
    site2 = rs.AddPolyline(site2_pts)
    sites.append(site2)
    
    # 코너 대지
    site3_pts = [
        (120, 0, 0), (170, 0, 0), (170, 25, 0),
        (145, 40, 0), (120, 40, 0), (120, 0, 0)
    ]
    site3 = rs.AddPolyline(site3_pts)
    sites.append(site3)
    
    return sites

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 대지 생성
    sites = create_sample_sites()
    
    # 건물 파라미터
    building_params = create_sample_building_params()
    
    print("=== 건물 라인 생성 ===")
    
    all_footprints = []
    
    # 각 대지에 다른 용도 건물 생성
    for i, (site, params) in enumerate(zip(sites, building_params)):
        print(f"\n{params['name']} 생성 중...")
        
        # 건물 라인 생성기
        generator = BuildingLineGenerator(site, params)
        
        # 필요 면적 계산
        area, floors = generator.calculate_required_area()
        print(f"  필요 건축면적: {area:.2f}m², 층수: {floors}")
        
        # 이격거리 적용
        if generator.apply_setbacks():
            # 건물 외곽선 생성
            footprint = generator.generate_building_footprint()
            
            if footprint:
                # 건물 정보 추가
                generator.add_building_info(footprint)
                all_footprints.append(footprint)
                
                # 실제 건축면적
                actual_area = rs.CurveArea(footprint)[0]
                print(f"  실제 건축면적: {actual_area:.2f}m²")
                print(f"  건폐율: {actual_area/generator.site_area*100:.1f}%")
                print(f"  용적률: {actual_area*floors/generator.site_area*100:.1f}%")
    
    # 시각화
    visualize_building_lines(sites, all_footprints)
    
    # 줌 익스텐트
    rs.ZoomExtents()