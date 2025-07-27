# Lecture 6 - Practice 1: Isovist를 활용한 보행자 시각 분석
# 도시 공간에서의 가시영역 분석 및 시각적 연결성 평가

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class IsovistAnalyzer:
    def __init__(self, obstacles, analysis_points=None):
        self.obstacles = obstacles  # 건물, 벽 등 시각적 장애물
        self.analysis_points = analysis_points or []
        self.eye_height = 1.6  # 평균 눈높이 (m)
        
    def create_isovist_2d(self, viewpoint, max_distance=100):
        """2D Isovist 생성 (평면)"""
        # 시선 광선 생성
        num_rays = 360  # 1도 간격
        rays = []
        
        for i in range(num_rays):
            angle = math.radians(i)
            direction = rg.Vector3d(
                math.cos(angle),
                math.sin(angle),
                0
            )
            
            ray = rg.Ray3d(viewpoint, direction)
            rays.append(ray)
        
        # 각 광선과 장애물의 교차점 찾기
        visibility_points = []
        
        for ray in rays:
            closest_point = None
            min_distance = max_distance
            
            # 모든 장애물과의 교차 확인
            for obstacle in self.obstacles:
                curve = rs.coercecurve(obstacle)
                
                # 광선과 커브의 교차점
                intersections = rg.Intersect.Intersection.RayShoot(
                    ray,
                    [curve],
                    1  # 하나의 반사만
                )
                
                if intersections:
                    for t in intersections:
                        point = ray.PointAt(t)
                        distance = viewpoint.DistanceTo(point)
                        
                        if distance < min_distance:
                            min_distance = distance
                            closest_point = point
            
            # 교차점이 없으면 최대 거리 점 사용
            if closest_point is None:
                closest_point = ray.PointAt(max_distance)
            
            visibility_points.append(closest_point)
        
        # 가시영역 폴리곤 생성
        visibility_points.append(visibility_points[0])  # 닫기
        isovist_curve = rs.AddPolyline(visibility_points)
        
        # 부드럽게 만들기
        if isovist_curve:
            smooth_curve = rs.RebuildCurve(isovist_curve, 3, 100)
            rs.DeleteObject(isovist_curve)
            return smooth_curve
        
        return isovist_curve
    
    def create_isovist_3d(self, viewpoint, max_distance=100):
        """3D Isovist 생성 (반구형)"""
        # 시선 광선 생성 (반구형)
        rays = []
        
        # 수평 각도 (방위각)
        azimuth_steps = 36  # 10도 간격
        # 수직 각도 (고도각)
        altitude_steps = 9  # 10도 간격, 0~90도
        
        for i in range(azimuth_steps):
            azimuth = math.radians(i * 360 / azimuth_steps)
            
            for j in range(altitude_steps + 1):
                altitude = math.radians(j * 90 / altitude_steps)
                
                # 구면 좌표를 직교 좌표로 변환
                direction = rg.Vector3d(
                    math.cos(altitude) * math.cos(azimuth),
                    math.cos(altitude) * math.sin(azimuth),
                    math.sin(altitude)
                )
                
                ray = rg.Ray3d(viewpoint, direction)
                rays.append(ray)
        
        # 가시 점들 수집
        visibility_mesh_points = []
        
        for ray in rays:
            closest_point = None
            min_distance = max_distance
            
            # 장애물과의 교차 확인
            for obstacle in self.obstacles:
                # 3D 장애물 처리 (Brep으로 가정)
                if rs.IsBrep(obstacle):
                    brep = rs.coercebrep(obstacle)
                    intersections = rg.Intersect.Intersection.RayShoot(
                        ray,
                        [brep],
                        1
                    )
                    
                    if intersections:
                        for t in intersections:
                            point = ray.PointAt(t)
                            distance = viewpoint.DistanceTo(point)
                            
                            if distance < min_distance:
                                min_distance = distance
                                closest_point = point
            
            if closest_point is None:
                closest_point = ray.PointAt(max_distance)
            
            visibility_mesh_points.append(closest_point)
        
        # 메시 생성
        # 여기서는 점군으로 표현 (실제로는 Delaunay 삼각분할 등 필요)
        return visibility_mesh_points
    
    def analyze_isovist_properties(self, isovist_curve):
        """Isovist 속성 분석"""
        if not isovist_curve:
            return None
        
        properties = {}
        
        # 면적
        area_result = rs.CurveArea(isovist_curve)
        if area_result:
            properties['area'] = area_result[0]
            properties['centroid'] = area_result[1]
        
        # 둘레
        properties['perimeter'] = rs.CurveLength(isovist_curve)
        
        # 형태 지수
        if properties.get('area') and properties.get('perimeter'):
            # Compactness (원형도)
            properties['compactness'] = 4 * math.pi * properties['area'] / (properties['perimeter'] ** 2)
            
            # 평균 반경
            properties['mean_radius'] = properties['area'] / properties['perimeter']
        
        # 최대/최소 반경
        if properties.get('centroid'):
            curve = rs.coercecurve(isovist_curve)
            distances = []
            
            for i in range(100):
                t = i / 99.0
                param = curve.Domain.ParameterAt(t)
                point = curve.PointAt(param)
                distance = properties['centroid'].DistanceTo(point)
                distances.append(distance)
            
            properties['max_radius'] = max(distances)
            properties['min_radius'] = min(distances)
            properties['radius_variance'] = max(distances) - min(distances)
        
        return properties
    
    def create_visibility_graph(self, points, max_distance=50):
        """가시성 그래프 생성"""
        visibility_graph = []
        
        for i, point1 in enumerate(points):
            for j, point2 in enumerate(points):
                if i >= j:  # 중복 제거
                    continue
                
                # 두 점 사이 가시성 확인
                if self.check_visibility(point1, point2, max_distance):
                    line = rs.AddLine(point1, point2)
                    visibility_graph.append({
                        'line': line,
                        'start': point1,
                        'end': point2,
                        'distance': point1.DistanceTo(point2)
                    })
        
        return visibility_graph
    
    def check_visibility(self, point1, point2, max_distance):
        """두 점 사이의 가시성 확인"""
        distance = point1.DistanceTo(point2)
        
        if distance > max_distance:
            return False
        
        # 시선 생성
        line = rg.Line(point1, point2)
        
        # 장애물과의 교차 확인
        for obstacle in self.obstacles:
            curve = rs.coercecurve(obstacle)
            
            # 선과 커브의 교차
            intersections = rg.Intersect.Intersection.CurveLine(
                curve,
                line,
                0.01,
                0.01
            )
            
            if intersections.Count > 0:
                # 교차점이 선분 내부에 있는지 확인
                for intersection in intersections:
                    t = line.ClosestParameter(intersection.PointA)
                    if 0.01 < t < 0.99:  # 양 끝점 제외
                        return False
        
        return True
    
    def calculate_integration(self, visibility_graph, point):
        """통합도 계산 (Space Syntax)"""
        # 점에서 다른 모든 점까지의 최단 경로 깊이 계산
        # 여기서는 간단히 직접 연결된 점의 수로 근사
        connections = 0
        total_distance = 0
        
        for edge in visibility_graph:
            if edge['start'] == point or edge['end'] == point:
                connections += 1
                total_distance += edge['distance']
        
        if connections > 0:
            mean_depth = total_distance / connections
            integration = 1 / mean_depth if mean_depth > 0 else 0
        else:
            integration = 0
        
        return integration, connections
    
    def create_isovist_field(self, grid_spacing=5, boundary=None):
        """Isovist 필드 생성 (여러 점에서의 분석)"""
        if not boundary:
            # 전체 영역의 경계 계산
            all_points = []
            for obstacle in self.obstacles:
                bbox_points = rs.BoundingBox(obstacle)
                all_points.extend(bbox_points)
            
            bbox = rs.BoundingBox(all_points)
        else:
            bbox = rs.BoundingBox(boundary)
        
        # 그리드 점 생성
        grid_points = []
        x = bbox[0].X
        while x <= bbox[1].X:
            y = bbox[0].Y
            while y <= bbox[3].Y:
                point = rg.Point3d(x, y, self.eye_height)
                
                # 장애물 내부가 아닌지 확인
                if not self.is_inside_obstacle(point):
                    grid_points.append(point)
                
                y += grid_spacing
            x += grid_spacing
        
        # 각 점에서 isovist 분석
        isovist_data = []
        
        for point in grid_points:
            isovist = self.create_isovist_2d(point, max_distance=30)
            
            if isovist:
                properties = self.analyze_isovist_properties(isovist)
                
                isovist_data.append({
                    'point': point,
                    'isovist': isovist,
                    'properties': properties
                })
                
                # 메모리 관리를 위해 일부만 표시
                if len(isovist_data) > 20:
                    rs.DeleteObject(isovist)
        
        return isovist_data
    
    def is_inside_obstacle(self, point):
        """점이 장애물 내부에 있는지 확인"""
        for obstacle in self.obstacles:
            curve = rs.coercecurve(obstacle)
            if curve and curve.IsClosed:
                containment = curve.Contains(point)
                if containment == rg.PointContainment.Inside:
                    return True
        return False

def visualize_isovist_analysis(isovists, visibility_graph=None, analysis_type="area"):
    """Isovist 분석 결과 시각화"""
    # 레이어 생성
    layers = {
        "Obstacles": (100, 100, 100),
        "Isovist_Curves": (200, 200, 255),
        "Isovist_Points": (255, 0, 0),
        "Visibility_Graph": (0, 255, 0),
        "Analysis_Values": (0, 0, 0)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # Isovist 시각화
    if isovists:
        # 값 범위 계산
        values = []
        for data in isovists:
            if data['properties']:
                value = data['properties'].get(analysis_type, 0)
                values.append(value)
        
        if values:
            min_val = min(values)
            max_val = max(values)
            range_val = max_val - min_val if max_val > min_val else 1
            
            # 각 isovist 표시
            for i, data in enumerate(isovists):
                if data['properties']:
                    value = data['properties'].get(analysis_type, 0)
                    
                    # 정규화 (0~1)
                    normalized = (value - min_val) / range_val
                    
                    # 색상 그라데이션 (파랑 -> 빨강)
                    color = (
                        int(255 * normalized),
                        0,
                        int(255 * (1 - normalized))
                    )
                    
                    # 점 표시
                    pt = rs.AddPoint(data['point'])
                    rs.ObjectLayer(pt, "Isovist_Points")
                    rs.ObjectColor(pt, color)
                    
                    # 값 표시
                    if i % 5 == 0:  # 5개마다 하나씩
                        text = rs.AddTextDot(f"{value:.1f}", data['point'])
                        rs.ObjectLayer(text, "Analysis_Values")
                    
                    # Isovist 커브 (일부만)
                    if i < 10 and data.get('isovist'):
                        rs.ObjectLayer(data['isovist'], "Isovist_Curves")
                        rs.ObjectColor(data['isovist'], color)
    
    # 가시성 그래프
    if visibility_graph:
        for edge in visibility_graph[:50]:  # 처음 50개만
            if edge.get('line'):
                rs.ObjectLayer(edge['line'], "Visibility_Graph")
                rs.ObjectColor(edge['line'], (0, 255, 0))

def create_sample_urban_space():
    """샘플 도시 공간 생성"""
    obstacles = []
    
    # 건물들
    buildings = [
        rs.AddRectangle((10, 10, 0), 15, 20),
        rs.AddRectangle((30, 15, 0), 20, 15),
        rs.AddRectangle((10, 40, 0), 12, 18),
        rs.AddRectangle((55, 10, 0), 18, 25),
        rs.AddRectangle((30, 35, 0), 15, 20),
        rs.AddRectangle((50, 45, 0), 20, 15)
    ]
    
    obstacles.extend(buildings)
    
    # 분석 포인트 (교차로, 광장 등)
    analysis_points = [
        rg.Point3d(25, 30, 1.6),  # 교차로
        rg.Point3d(45, 25, 1.6),  # 도로 중간
        rg.Point3d(65, 40, 1.6),  # 공터
        rg.Point3d(5, 35, 1.6),   # 골목
        rg.Point3d(40, 10, 1.6)   # 도로변
    ]
    
    return obstacles, analysis_points

def analyze_urban_visibility_metrics(isovist_data):
    """도시 가시성 지표 분석"""
    print("\n=== 도시 공간 가시성 분석 ===")
    
    if not isovist_data:
        print("분석할 데이터가 없습니다.")
        return
    
    # 전체 통계
    areas = [d['properties']['area'] for d in isovist_data if d['properties']]
    perimeters = [d['properties']['perimeter'] for d in isovist_data if d['properties']]
    compactness = [d['properties']['compactness'] for d in isovist_data if d['properties']]
    
    print(f"\n가시영역 면적:")
    print(f"  평균: {sum(areas)/len(areas):.2f} m²")
    print(f"  최대: {max(areas):.2f} m²")
    print(f"  최소: {min(areas):.2f} m²")
    
    print(f"\n형태 지수:")
    print(f"  평균 compactness: {sum(compactness)/len(compactness):.3f}")
    
    # 공간 유형 분류
    space_types = {
        'open': 0,      # 개방형 (면적 > 500m²)
        'medium': 0,    # 중간형 (200-500m²)
        'enclosed': 0   # 폐쇄형 (< 200m²)
    }
    
    for data in isovist_data:
        area = data['properties']['area']
        if area > 500:
            space_types['open'] += 1
        elif area > 200:
            space_types['medium'] += 1
        else:
            space_types['enclosed'] += 1
    
    print(f"\n공간 유형 분포:")
    total = len(isovist_data)
    for space_type, count in space_types.items():
        print(f"  {space_type}: {count}개 ({count/total*100:.1f}%)")

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 도시 공간 생성
    obstacles, analysis_points = create_sample_urban_space()
    
    # Isovist 분석기
    analyzer = IsovistAnalyzer(obstacles, analysis_points)
    
    print("=== Isovist 분석 시작 ===")
    
    # 1. 개별 지점 Isovist 분석
    print("\n1. 주요 지점 Isovist 분석")
    
    for i, point in enumerate(analysis_points):
        isovist = analyzer.create_isovist_2d(point, max_distance=50)
        
        if isovist:
            properties = analyzer.analyze_isovist_properties(isovist)
            
            print(f"\n지점 {i+1}:")
            print(f"  가시영역 면적: {properties['area']:.2f} m²")
            print(f"  평균 가시거리: {properties['mean_radius']:.2f} m")
            print(f"  형태 지수: {properties['compactness']:.3f}")
            
            # 점 표시
            pt = rs.AddPoint(point)
            rs.ObjectColor(pt, (255, 0, 0))
            rs.AddTextDot(f"P{i+1}", point)
    
    # 2. Isovist 필드 분석
    print("\n2. Isovist 필드 분석")
    isovist_field = analyzer.create_isovist_field(grid_spacing=8)
    
    # 3. 가시성 그래프
    print("\n3. 가시성 그래프 생성")
    visibility_graph = analyzer.create_visibility_graph(analysis_points, max_distance=40)
    print(f"가시성 연결: {len(visibility_graph)}개")
    
    # 4. 통합도 분석
    print("\n4. 공간 통합도 분석")
    for i, point in enumerate(analysis_points):
        integration, connections = analyzer.calculate_integration(visibility_graph, point)
        print(f"지점 {i+1}: 통합도 {integration:.3f}, 연결 수 {connections}")
    
    # 시각화
    visualize_isovist_analysis(isovist_field, visibility_graph, "area")
    
    # 도시 가시성 지표 분석
    analyze_urban_visibility_metrics(isovist_field)
    
    # 장애물 표시
    for obstacle in obstacles:
        rs.ObjectLayer(obstacle, "Obstacles")
        rs.ObjectColor(obstacle, (100, 100, 100))
    
    # 줌 익스텐트
    rs.ZoomExtents()