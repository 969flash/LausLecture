# Lecture 5 - Practice 2: 주차장 설계 자동화
# 법정 주차대수를 충족하는 효율적인 주차장 레이아웃 자동 생성

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class ParkingDesigner:
    def __init__(self, parking_area, requirements):
        self.parking_area = parking_area
        self.requirements = requirements
        self.area_bbox = rs.BoundingBox(parking_area)
        
        # 표준 주차면 크기
        self.standard_width = requirements.get('stall_width', 2.5)
        self.standard_length = requirements.get('stall_length', 5.0)
        self.compact_width = requirements.get('compact_width', 2.3)
        self.compact_length = requirements.get('compact_length', 4.5)
        
        # 통로 폭
        self.aisle_width = {
            0: 3.5,    # 평행주차
            30: 4.0,   # 30도
            45: 5.0,   # 45도
            60: 5.5,   # 60도
            90: 6.0    # 90도 직각주차
        }
    
    def calculate_required_stalls(self, building_gfa, use_type):
        """법정 주차대수 계산"""
        # 용도별 주차기준 (서울시 기준 예시)
        parking_standards = {
            'residential': 85,      # 85m²당 1대
            'commercial': 100,      # 100m²당 1대
            'office': 120,          # 120m²당 1대
            'retail': 60,           # 60m²당 1대
            'mixed': 100            # 평균
        }
        
        standard = parking_standards.get(use_type, 100)
        required_stalls = math.ceil(building_gfa / standard)
        
        # 장애인 주차 (전체의 3% 이상)
        handicap_stalls = max(1, math.ceil(required_stalls * 0.03))
        
        # 경차/친환경차 우대 (전체의 10%)
        compact_stalls = math.floor(required_stalls * 0.1)
        
        return {
            'total': required_stalls,
            'standard': required_stalls - handicap_stalls - compact_stalls,
            'handicap': handicap_stalls,
            'compact': compact_stalls
        }
    
    def determine_optimal_angle(self):
        """최적 주차 각도 결정"""
        width = self.area_bbox[1].X - self.area_bbox[0].X
        depth = self.area_bbox[3].Y - self.area_bbox[0].Y
        area = width * depth
        
        # 면적과 형태에 따른 각도 선택
        if area < 500:  # 소규모
            return 90  # 직각주차
        elif width < 20 or depth < 20:  # 좁은 형태
            return 45  # 경사주차
        else:
            # 효율성 분석
            angles = [90, 60, 45]
            best_angle = 90
            best_efficiency = 0
            
            for angle in angles:
                efficiency = self.calculate_parking_efficiency(angle)
                if efficiency > best_efficiency:
                    best_efficiency = efficiency
                    best_angle = angle
            
            return best_angle
    
    def calculate_parking_efficiency(self, angle):
        """주차 각도별 효율성 계산"""
        if angle == 90:
            stall_width = self.standard_width
            stall_depth = self.standard_length
        else:
            angle_rad = math.radians(angle)
            stall_width = self.standard_width / math.sin(angle_rad)
            stall_depth = self.standard_length * math.sin(angle_rad)
        
        aisle = self.aisle_width[angle]
        module_depth = stall_depth * 2 + aisle  # 양면 주차
        
        # 가능한 주차면 수 추정
        width = self.area_bbox[1].X - self.area_bbox[0].X
        depth = self.area_bbox[3].Y - self.area_bbox[0].Y
        
        num_modules = int(depth / module_depth)
        stalls_per_module = int(width / stall_width) * 2  # 양면
        
        total_stalls = num_modules * stalls_per_module
        area_per_stall = (width * depth) / total_stalls if total_stalls > 0 else float('inf')
        
        return 1 / area_per_stall if area_per_stall > 0 else 0
    
    def generate_parking_layout(self, angle=None):
        """주차장 레이아웃 생성"""
        if angle is None:
            angle = self.determine_optimal_angle()
        
        print(f"선택된 주차 각도: {angle}도")
        
        if angle == 90:
            return self.generate_perpendicular_parking()
        elif angle == 0:
            return self.generate_parallel_parking()
        else:
            return self.generate_angled_parking(angle)
    
    def generate_perpendicular_parking(self):
        """직각 주차 레이아웃"""
        layout = {
            'stalls': [],
            'aisles': [],
            'markings': []
        }
        
        # 주차 모듈 크기
        stall_width = self.standard_width
        stall_length = self.standard_length
        aisle_width = self.aisle_width[90]
        module_depth = stall_length * 2 + aisle_width
        
        # 시작 위치
        start_x = self.area_bbox[0].X + 1  # 1m 여유
        start_y = self.area_bbox[0].Y + 1
        
        # 주차 모듈 배치
        current_y = start_y
        module_count = 0
        
        while current_y + module_depth < self.area_bbox[3].Y - 1:
            # 통로
            aisle = rs.AddRectangle(
                (start_x, current_y + stall_length, 0),
                self.area_bbox[1].X - self.area_bbox[0].X - 2,
                aisle_width
            )
            layout['aisles'].append(aisle)
            
            # 하단 주차면
            current_x = start_x
            while current_x + stall_width < self.area_bbox[1].X - 1:
                stall = self.create_parking_stall(
                    (current_x, current_y, 0),
                    stall_width,
                    stall_length,
                    'standard'
                )
                layout['stalls'].append(stall)
                current_x += stall_width
            
            # 상단 주차면
            current_x = start_x
            while current_x + stall_width < self.area_bbox[1].X - 1:
                stall = self.create_parking_stall(
                    (current_x, current_y + stall_length + aisle_width, 0),
                    stall_width,
                    stall_length,
                    'standard'
                )
                layout['stalls'].append(stall)
                current_x += stall_width
            
            current_y += module_depth
            module_count += 1
        
        # 장애인 주차 배치 (입구 근처)
        self.add_handicap_stalls(layout)
        
        # 주차선 표시
        self.add_parking_markings(layout)
        
        return layout
    
    def generate_angled_parking(self, angle):
        """경사 주차 레이아웃"""
        layout = {
            'stalls': [],
            'aisles': [],
            'markings': []
        }
        
        angle_rad = math.radians(angle)
        
        # 경사 주차면 크기
        stall_parallel = self.standard_width / math.sin(angle_rad)
        stall_perpendicular = self.standard_length * math.sin(angle_rad)
        aisle_width = self.aisle_width[angle]
        
        # 모듈 깊이
        module_depth = stall_perpendicular * 2 + aisle_width
        
        # 시작 위치
        start_x = self.area_bbox[0].X + 2
        start_y = self.area_bbox[0].Y + 2
        
        current_y = start_y
        
        while current_y + module_depth < self.area_bbox[3].Y - 2:
            # 통로
            aisle = rs.AddRectangle(
                (start_x, current_y + stall_perpendicular, 0),
                self.area_bbox[1].X - self.area_bbox[0].X - 4,
                aisle_width
            )
            layout['aisles'].append(aisle)
            
            # 하단 주차면 (왼쪽 기울기)
            current_x = start_x
            while current_x + stall_parallel < self.area_bbox[1].X - 2:
                pts = self.calculate_angled_stall_points(
                    (current_x, current_y, 0),
                    angle,
                    self.standard_width,
                    self.standard_length
                )
                stall = rs.AddPolyline(pts)
                layout['stalls'].append(stall)
                rs.SetUserText(stall, "type", "standard")
                
                current_x += self.standard_width / math.sin(angle_rad)
            
            # 상단 주차면 (오른쪽 기울기)
            current_x = start_x
            while current_x + stall_parallel < self.area_bbox[1].X - 2:
                pts = self.calculate_angled_stall_points(
                    (current_x, current_y + stall_perpendicular + aisle_width + stall_perpendicular, 0),
                    -angle,  # 반대 방향
                    self.standard_width,
                    self.standard_length
                )
                stall = rs.AddPolyline(pts)
                layout['stalls'].append(stall)
                rs.SetUserText(stall, "type", "standard")
                
                current_x += self.standard_width / math.sin(angle_rad)
            
            current_y += module_depth
        
        return layout
    
    def calculate_angled_stall_points(self, origin, angle, width, length):
        """경사 주차면 좌표 계산"""
        angle_rad = math.radians(angle)
        
        # 주차면 4개 모서리
        pts = [
            origin,
            (origin[0] + width * math.cos(angle_rad + math.pi/2),
             origin[1] + width * math.sin(angle_rad + math.pi/2), 0),
            (origin[0] + width * math.cos(angle_rad + math.pi/2) + length * math.cos(angle_rad),
             origin[1] + width * math.sin(angle_rad + math.pi/2) + length * math.sin(angle_rad), 0),
            (origin[0] + length * math.cos(angle_rad),
             origin[1] + length * math.sin(angle_rad), 0),
            origin
        ]
        
        return pts
    
    def create_parking_stall(self, origin, width, length, stall_type):
        """주차면 생성"""
        stall = rs.AddRectangle(origin, width, length)
        rs.SetUserText(stall, "type", stall_type)
        
        # 타입별 속성
        if stall_type == "handicap":
            rs.SetUserText(stall, "width", str(width + 1.0))  # 장애인 주차는 더 넓음
        elif stall_type == "compact":
            rs.SetUserText(stall, "width", str(self.compact_width))
        
        return stall
    
    def add_handicap_stalls(self, layout):
        """장애인 주차 구역 추가"""
        # 첫 번째 주차면들을 장애인 주차로 변경
        num_handicap = self.requirements.get('handicap_stalls', 2)
        
        for i in range(min(num_handicap, len(layout['stalls']))):
            stall = layout['stalls'][i]
            rs.SetUserText(stall, "type", "handicap")
            
            # 옆에 해칭 구역 추가
            bbox = rs.BoundingBox(stall)
            hatching = rs.AddRectangle(
                (bbox[1].X, bbox[0].Y, 0),
                1.2,  # 해칭 폭
                bbox[3].Y - bbox[0].Y
            )
            rs.SetUserText(hatching, "type", "hatching")
            layout['markings'].append(hatching)
    
    def add_parking_markings(self, layout):
        """주차 표시 추가"""
        for stall in layout['stalls']:
            stall_type = rs.GetUserText(stall, "type")
            
            # 주차면 번호
            center = rs.CurveAreaCentroid(stall)[0]
            
            if stall_type == "handicap":
                # 장애인 심볼
                symbol = rs.AddCircle(center, 0.5)
                layout['markings'].append(symbol)
            
            # 휠스토퍼 위치
            bbox = rs.BoundingBox(stall)
            if bbox:
                stopper_y = bbox[0].Y + 0.5
                stopper = rs.AddLine(
                    (bbox[0].X + 0.3, stopper_y, 0),
                    (bbox[1].X - 0.3, stopper_y, 0)
                )
                layout['markings'].append(stopper)
    
    def add_circulation_arrows(self, layout):
        """차량 동선 화살표 추가"""
        for aisle in layout['aisles']:
            center = rs.CurveAreaCentroid(aisle)[0]
            
            # 화살표 (간단한 표시)
            arrow_pts = [
                (center.X - 2, center.Y, 0),
                (center.X + 2, center.Y, 0),
                (center.X + 1, center.Y + 0.5, 0),
                (center.X + 2, center.Y, 0),
                (center.X + 1, center.Y - 0.5, 0)
            ]
            arrow = rs.AddPolyline(arrow_pts[:-2])
            layout['markings'].append(arrow)
    
    def analyze_parking_efficiency(self, layout):
        """주차장 효율성 분석"""
        # 주차면 수 계산
        stall_counts = {
            'standard': 0,
            'handicap': 0,
            'compact': 0
        }
        
        for stall in layout['stalls']:
            stall_type = rs.GetUserText(stall, "type")
            if stall_type in stall_counts:
                stall_counts[stall_type] += 1
        
        total_stalls = sum(stall_counts.values())
        
        # 면적 효율성
        parking_area = rs.CurveArea(self.parking_area)[0]
        area_per_stall = parking_area / total_stalls if total_stalls > 0 else 0
        
        # 통로 면적
        aisle_area = sum(rs.CurveArea(aisle)[0] for aisle in layout['aisles'])
        aisle_ratio = aisle_area / parking_area if parking_area > 0 else 0
        
        return {
            'total_stalls': total_stalls,
            'stall_counts': stall_counts,
            'area_per_stall': area_per_stall,
            'aisle_ratio': aisle_ratio,
            'efficiency': total_stalls / (parking_area / 30) if parking_area > 0 else 0  # 30m²/대 기준
        }

def visualize_parking_layout(parking_area, layout, analysis):
    """주차장 레이아웃 시각화"""
    # 레이어 생성
    layers = {
        "Parking_Area": (240, 240, 240),
        "Parking_Stalls": (200, 200, 200),
        "Parking_Handicap": (100, 150, 255),
        "Parking_Compact": (255, 200, 100),
        "Parking_Aisles": (180, 180, 180),
        "Parking_Markings": (50, 50, 50)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 주차장 영역
    rs.ObjectLayer(parking_area, "Parking_Area")
    
    # 주차면
    for stall in layout['stalls']:
        stall_type = rs.GetUserText(stall, "type")
        
        if stall_type == "handicap":
            rs.ObjectLayer(stall, "Parking_Handicap")
            rs.ObjectColor(stall, (100, 150, 255))
        elif stall_type == "compact":
            rs.ObjectLayer(stall, "Parking_Compact")
            rs.ObjectColor(stall, (255, 200, 100))
        else:
            rs.ObjectLayer(stall, "Parking_Stalls")
            rs.ObjectColor(stall, (200, 200, 200))
    
    # 통로
    for aisle in layout['aisles']:
        rs.ObjectLayer(aisle, "Parking_Aisles")
        rs.ObjectColor(aisle, (180, 180, 180))
    
    # 표시
    for marking in layout['markings']:
        rs.ObjectLayer(marking, "Parking_Markings")
        rs.ObjectColor(marking, (50, 50, 50))
    
    # 분석 정보
    bbox = rs.BoundingBox(parking_area)
    text_point = rg.Point3d(bbox[0].X, bbox[3].Y + 5, 0)
    
    info_text = f"""주차장 분석
총 주차면: {analysis['total_stalls']}대
- 일반: {analysis['stall_counts']['standard']}대
- 장애인: {analysis['stall_counts']['handicap']}대
- 경형: {analysis['stall_counts']['compact']}대

면적당 주차대수: {analysis['area_per_stall']:.1f}m²/대
통로 비율: {analysis['aisle_ratio']*100:.1f}%
효율성: {analysis['efficiency']*100:.1f}%"""
    
    rs.AddText(info_text, text_point, height=2.0)

def create_sample_parking_areas():
    """샘플 주차장 영역 생성"""
    areas = []
    
    # 지하 주차장 (정형)
    area1 = rs.AddRectangle((0, 0, 0), 50, 30)
    areas.append(area1)
    
    # 지상 주차장 (부정형)
    area2_pts = [
        (60, 0, 0), (110, 0, 0), (115, 25, 0),
        (100, 35, 0), (65, 30, 0), (60, 0, 0)
    ]
    area2 = rs.AddPolyline(area2_pts)
    areas.append(area2)
    
    return areas

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 주차장 영역 생성
    parking_areas = create_sample_parking_areas()
    
    print("=== 주차장 설계 자동화 ===")
    
    # 건물 정보 (예시)
    building_gfa = 5000  # 연면적 5000m²
    use_type = 'office'  # 업무시설
    
    for i, parking_area in enumerate(parking_areas):
        print(f"\n주차장 {i+1} 설계")
        
        # 주차 요구사항
        designer = ParkingDesigner(parking_area, {})
        required = designer.calculate_required_stalls(building_gfa, use_type)
        
        print(f"법정 주차대수: {required['total']}대")
        print(f"- 일반: {required['standard']}대")
        print(f"- 장애인: {required['handicap']}대")
        print(f"- 경형: {required['compact']}대")
        
        # 요구사항 업데이트
        designer.requirements.update(required)
        
        # 주차장 레이아웃 생성
        layout = designer.generate_parking_layout()
        
        # 차량 동선 추가
        designer.add_circulation_arrows(layout)
        
        # 효율성 분석
        analysis = designer.analyze_parking_efficiency(layout)
        
        print(f"\n실제 주차면: {analysis['total_stalls']}대")
        print(f"면적 효율: {analysis['area_per_stall']:.1f}m²/대")
        
        # 시각화
        visualize_parking_layout(parking_area, layout, analysis)
        
        # 위치 이동 (보기 쉽게)
        if i > 0:
            move_vector = (0, 50 * i, 0)
            all_objects = layout['stalls'] + layout['aisles'] + layout['markings'] + [parking_area]
            rs.MoveObjects(all_objects, move_vector)
    
    # 줌 익스텐트
    rs.ZoomExtents()