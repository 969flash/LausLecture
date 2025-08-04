# Lecture 6 - Practice 2: Offset을 활용한 유사 필지 필터링
# 형태적 유사성을 기반으로 한 필지 분류 및 패턴 인식

import rhinoscriptsyntax as rs
import Rhino.Geometry as rg
import scriptcontext as sc
import math

class OffsetBasedFilter:
    def __init__(self, parcels):
        self.parcels = parcels
        self.offset_steps = [1, 2, 3, 5, 10]  # 다양한 오프셋 거리
        
    def create_offset_signature(self, parcel):
        """오프셋 시그니처 생성"""
        signature = {
            'original_area': rs.CurveArea(parcel)[0],
            'original_perimeter': rs.CurveLength(parcel),
            'offset_areas': [],
            'offset_perimeters': [],
            'area_reduction_rates': [],
            'shape_persistence': []
        }
        
        parcel_curve = rs.coercecurve(parcel)
        center = rs.CurveAreaCentroid(parcel)[0]
        
        for offset_dist in self.offset_steps:
            # 내부 오프셋
            offset_result = rs.OffsetCurve(parcel, center, -offset_dist)
            
            if offset_result and len(offset_result) > 0:
                offset_curve = offset_result[0]
                
                # 면적과 둘레 계산
                area_result = rs.CurveArea(offset_curve)
                if area_result:
                    offset_area = area_result[0]
                    signature['offset_areas'].append(offset_area)
                    
                    # 면적 감소율
                    reduction_rate = (signature['original_area'] - offset_area) / signature['original_area']
                    signature['area_reduction_rates'].append(reduction_rate)
                
                perimeter = rs.CurveLength(offset_curve)
                signature['offset_perimeters'].append(perimeter)
                
                # 형태 지속성 (오프셋 후에도 유지되는 정도)
                if rs.IsCurveClosed(offset_curve):
                    persistence = self.calculate_shape_persistence(parcel, offset_curve)
                    signature['shape_persistence'].append(persistence)
                else:
                    signature['shape_persistence'].append(0)
                
                # 임시 오프셋 삭제
                rs.DeleteObject(offset_curve)
            else:
                # 오프셋 실패 (형태가 사라짐)
                signature['offset_areas'].append(0)
                signature['offset_perimeters'].append(0)
                signature['area_reduction_rates'].append(1.0)
                signature['shape_persistence'].append(0)
        
        # 추가 특성 계산
        signature['complexity'] = self.calculate_complexity(signature)
        signature['regularity'] = self.calculate_regularity(signature)
        
        return signature
    
    def calculate_shape_persistence(self, original, offset):
        """형태 지속성 계산"""
        # Hausdorff 거리의 근사치
        original_curve = rs.coercecurve(original)
        offset_curve = rs.coercecurve(offset)
        
        # 샘플 포인트
        num_samples = 20
        max_deviation = 0
        
        for i in range(num_samples):
            t = i / float(num_samples - 1)
            
            # 원본 커브의 점
            orig_param = original_curve.Domain.ParameterAt(t)
            orig_point = original_curve.PointAt(orig_param)
            
            # 오프셋 커브의 가장 가까운 점
            result = offset_curve.ClosestPoint(orig_point)
            if result[0]:
                closest_point = offset_curve.PointAt(result[1])
                deviation = orig_point.DistanceTo(closest_point)
                max_deviation = max(max_deviation, deviation)
        
        # 정규화된 지속성 점수
        persistence = 1.0 - (max_deviation / 10.0)  # 10m를 최대 편차로 가정
        return max(0, min(1, persistence))
    
    def calculate_complexity(self, signature):
        """형태 복잡도 계산"""
        if not signature['area_reduction_rates']:
            return 0
        
        # 면적 감소율의 변화율
        rates = signature['area_reduction_rates']
        if len(rates) > 1:
            variations = []
            for i in range(1, len(rates)):
                variation = abs(rates[i] - rates[i-1])
                variations.append(variation)
            
            complexity = sum(variations) / len(variations)
        else:
            complexity = 0
        
        return complexity
    
    def calculate_regularity(self, signature):
        """형태 규칙성 계산"""
        # 면적 감소가 일정한 정도
        rates = signature['area_reduction_rates']
        
        if len(rates) > 2:
            # 선형 회귀의 R² 값 계산 (간단한 버전)
            mean_rate = sum(rates) / len(rates)
            
            # 변동
            ss_tot = sum((r - mean_rate) ** 2 for r in rates)
            
            # 선형 예측
            if len(rates) > 1:
                slope = (rates[-1] - rates[0]) / (len(rates) - 1)
                predicted = [rates[0] + slope * i for i in range(len(rates))]
                ss_res = sum((rates[i] - predicted[i]) ** 2 for i in range(len(rates)))
                
                if ss_tot > 0:
                    r_squared = 1 - (ss_res / ss_tot)
                    regularity = max(0, r_squared)
                else:
                    regularity = 1.0
            else:
                regularity = 1.0
        else:
            regularity = 0.5
        
        return regularity
    
    def calculate_similarity(self, sig1, sig2):
        """두 시그니처 간 유사도 계산"""
        similarity_scores = []
        
        # 1. 면적 감소율 패턴 유사도
        if sig1['area_reduction_rates'] and sig2['area_reduction_rates']:
            rate_similarity = self.compare_sequences(
                sig1['area_reduction_rates'],
                sig2['area_reduction_rates']
            )
            similarity_scores.append(rate_similarity * 0.4)  # 가중치 40%
        
        # 2. 형태 지속성 패턴 유사도
        if sig1['shape_persistence'] and sig2['shape_persistence']:
            persistence_similarity = self.compare_sequences(
                sig1['shape_persistence'],
                sig2['shape_persistence']
            )
            similarity_scores.append(persistence_similarity * 0.3)  # 가중치 30%
        
        # 3. 복잡도 유사도
        complexity_diff = abs(sig1['complexity'] - sig2['complexity'])
        complexity_similarity = 1 - min(complexity_diff * 2, 1)
        similarity_scores.append(complexity_similarity * 0.2)  # 가중치 20%
        
        # 4. 규칙성 유사도
        regularity_diff = abs(sig1['regularity'] - sig2['regularity'])
        regularity_similarity = 1 - regularity_diff
        similarity_scores.append(regularity_similarity * 0.1)  # 가중치 10%
        
        # 전체 유사도
        total_similarity = sum(similarity_scores)
        
        return total_similarity
    
    def compare_sequences(self, seq1, seq2):
        """두 시퀀스 비교"""
        # 길이 맞추기
        min_len = min(len(seq1), len(seq2))
        if min_len == 0:
            return 0
        
        # 평균 차이 계산
        differences = []
        for i in range(min_len):
            diff = abs(seq1[i] - seq2[i])
            differences.append(diff)
        
        # 정규화된 유사도
        avg_diff = sum(differences) / len(differences)
        similarity = 1 - min(avg_diff, 1)
        
        return similarity
    
    def cluster_parcels(self, similarity_threshold=0.7):
        """유사도 기반 필지 클러스터링"""
        # 모든 필지의 시그니처 생성
        signatures = []
        for i, parcel in enumerate(self.parcels):
            sig = self.create_offset_signature(parcel)
            signatures.append({
                'id': i,
                'parcel': parcel,
                'signature': sig
            })
        
        # 클러스터 생성
        clusters = []
        assigned = set()
        
        for i, data1 in enumerate(signatures):
            if i in assigned:
                continue
            
            # 새 클러스터 시작
            cluster = [data1]
            assigned.add(i)
            
            # 유사한 필지 찾기
            for j, data2 in enumerate(signatures):
                if j in assigned:
                    continue
                
                similarity = self.calculate_similarity(
                    data1['signature'],
                    data2['signature']
                )
                
                if similarity >= similarity_threshold:
                    cluster.append(data2)
                    assigned.add(j)
            
            clusters.append(cluster)
        
        return clusters, signatures
    
    def identify_parcel_types(self, clusters):
        """필지 유형 식별"""
        parcel_types = []
        
        for i, cluster in enumerate(clusters):
            # 클러스터 대표 특성 계산
            avg_complexity = sum(p['signature']['complexity'] for p in cluster) / len(cluster)
            avg_regularity = sum(p['signature']['regularity'] for p in cluster) / len(cluster)
            avg_area = sum(p['signature']['original_area'] for p in cluster) / len(cluster)
            
            # 유형 판정
            if avg_regularity > 0.8 and avg_complexity < 0.2:
                type_name = "정형 필지"
                description = "규칙적이고 단순한 형태"
            elif avg_regularity < 0.5 and avg_complexity > 0.5:
                type_name = "부정형 필지"
                description = "불규칙하고 복잡한 형태"
            elif avg_area < 200:
                type_name = "소형 필지"
                description = "면적 200m² 미만"
            elif avg_area > 1000:
                type_name = "대형 필지"
                description = "면적 1000m² 이상"
            else:
                type_name = "일반 필지"
                description = "중간 크기의 일반적 형태"
            
            parcel_types.append({
                'cluster_id': i,
                'type_name': type_name,
                'description': description,
                'count': len(cluster),
                'avg_complexity': avg_complexity,
                'avg_regularity': avg_regularity,
                'avg_area': avg_area
            })
        
        return parcel_types

def visualize_offset_analysis(clusters, parcel_types, selected_parcels=None):
    """오프셋 분석 결과 시각화"""
    # 레이어 생성
    layers = {
        "Parcels_Original": (200, 200, 200),
        "Parcels_Cluster1": (255, 100, 100),
        "Parcels_Cluster2": (100, 255, 100),
        "Parcels_Cluster3": (100, 100, 255),
        "Parcels_Cluster4": (255, 255, 100),
        "Parcels_Other": (150, 150, 150),
        "Offset_Analysis": (0, 0, 0),
        "Selected_Offsets": (255, 0, 255)
    }
    
    for layer_name, color in layers.items():
        if not rs.IsLayer(layer_name):
            rs.AddLayer(layer_name, color)
    
    # 클러스터별 색상
    cluster_colors = [
        (255, 100, 100),  # 빨강
        (100, 255, 100),  # 초록
        (100, 100, 255),  # 파랑
        (255, 255, 100),  # 노랑
        (255, 100, 255),  # 마젠타
        (100, 255, 255)   # 시안
    ]
    
    # 클러스터별 필지 표시
    for i, cluster in enumerate(clusters):
        if i < 4:
            layer_name = f"Parcels_Cluster{i+1}"
        else:
            layer_name = "Parcels_Other"
        
        color = cluster_colors[i % len(cluster_colors)]
        
        for data in cluster:
            parcel = data['parcel']
            rs.ObjectLayer(parcel, layer_name)
            rs.ObjectColor(parcel, color)
            
            # 중심점에 정보 표시
            center = rs.CurveAreaCentroid(parcel)[0]
            info = f"C{i+1}"
            if i < len(parcel_types):
                info += f"\n{parcel_types[i]['type_name']}"
            
            text_dot = rs.AddTextDot(info, center)
            rs.ObjectLayer(text_dot, "Offset_Analysis")
    
    # 선택된 필지의 오프셋 시각화
    if selected_parcels:
        offset_distances = [1, 2, 3, 5]
        
        for parcel in selected_parcels[:3]:  # 처음 3개만
            center = rs.CurveAreaCentroid(parcel)[0]
            
            for i, dist in enumerate(offset_distances):
                offset_result = rs.OffsetCurve(parcel, center, -dist)
                
                if offset_result:
                    offset_curve = offset_result[0]
                    rs.ObjectLayer(offset_curve, "Selected_Offsets")
                    
                    # 투명도 효과를 위한 색상 변화
                    gray_value = 50 + i * 50
                    rs.ObjectColor(offset_curve, (gray_value, 0, gray_value))

def create_sample_parcels():
    """다양한 형태의 샘플 필지 생성"""
    parcels = []
    
    # 정형 필지 (사각형)
    for i in range(3):
        x = i * 25
        rect = rs.AddRectangle((x, 0, 0), 20, 15)
        parcels.append(rect)
    
    # 정형 필지 (정사각형)
    for i in range(3):
        x = i * 25
        square = rs.AddRectangle((x, 20, 0), 15, 15)
        parcels.append(square)
    
    # L자형 필지
    for i in range(2):
        x = 80 + i * 30
        l_pts = [
            (x, 0, 0), (x+15, 0, 0), (x+15, 10, 0),
            (x+8, 10, 0), (x+8, 20, 0), (x, 20, 0), (x, 0, 0)
        ]
        l_shape = rs.AddPolyline(l_pts)
        parcels.append(l_shape)
    
    # 부정형 필지
    irregular_pts1 = [
        (0, 40, 0), (18, 42, 0), (20, 55, 0),
        (8, 58, 0), (2, 52, 0), (0, 40, 0)
    ]
    parcels.append(rs.AddPolyline(irregular_pts1))
    
    irregular_pts2 = [
        (30, 40, 0), (45, 38, 0), (48, 52, 0),
        (42, 58, 0), (35, 56, 0), (30, 45, 0), (30, 40, 0)
    ]
    parcels.append(rs.AddPolyline(irregular_pts2))
    
    # 복잡한 형태
    complex_pts = []
    for i in range(20):
        angle = i * math.pi * 2 / 20
        r = 10 + 3 * math.sin(angle * 3)
        x = 80 + r * math.cos(angle)
        y = 50 + r * math.sin(angle)
        complex_pts.append((x, y, 0))
    complex_pts.append(complex_pts[0])
    parcels.append(rs.AddPolyline(complex_pts))
    
    return parcels

def print_analysis_summary(clusters, parcel_types, signatures):
    """분석 결과 요약 출력"""
    print("\n=== 오프셋 기반 필지 분류 결과 ===")
    
    print(f"\n총 필지 수: {len(signatures)}")
    print(f"클러스터 수: {len(clusters)}")
    
    print("\n클러스터별 정보:")
    for i, (cluster, ptype) in enumerate(zip(clusters, parcel_types)):
        print(f"\n클러스터 {i+1}: {ptype['type_name']}")
        print(f"  필지 수: {ptype['count']}")
        print(f"  설명: {ptype['description']}")
        print(f"  평균 면적: {ptype['avg_area']:.2f} m²")
        print(f"  복잡도: {ptype['avg_complexity']:.3f}")
        print(f"  규칙성: {ptype['avg_regularity']:.3f}")
    
    # 대표 시그니처 출력
    print("\n대표 시그니처 (첫 번째 클러스터):")
    if clusters and clusters[0]:
        sig = clusters[0][0]['signature']
        print(f"  면적 감소율: {[f'{r:.2f}' for r in sig['area_reduction_rates']]}")
        print(f"  형태 지속성: {[f'{p:.2f}' for p in sig['shape_persistence']]}")

if __name__ == "__main__":
    # 뷰포트 초기화
    rs.Command("_SelAll _Delete", False)
    
    # 샘플 필지 생성
    parcels = create_sample_parcels()
    
    print("=== Offset을 활용한 유사 필지 필터링 ===")
    
    # 오프셋 기반 필터
    filter = OffsetBasedFilter(parcels)
    
    # 필지 클러스터링
    print("\n필지 분석 중...")
    clusters, signatures = filter.cluster_parcels(similarity_threshold=0.6)
    
    # 필지 유형 식별
    parcel_types = filter.identify_parcel_types(clusters)
    
    # 결과 요약
    print_analysis_summary(clusters, parcel_types, signatures)
    
    # 시각화
    selected_parcels = [cluster[0]['parcel'] for cluster in clusters[:3]]
    visualize_offset_analysis(clusters, parcel_types, selected_parcels)
    
    # 유사도 매트릭스 (일부)
    print("\n유사도 매트릭스 (처음 5개):")
    print("     ", end="")
    for i in range(min(5, len(signatures))):
        print(f"  P{i+1} ", end="")
    print()
    
    for i in range(min(5, len(signatures))):
        print(f"P{i+1}  ", end="")
        for j in range(min(5, len(signatures))):
            if i == j:
                sim = 1.0
            else:
                sim = filter.calculate_similarity(
                    signatures[i]['signature'],
                    signatures[j]['signature']
                )
            print(f"{sim:5.2f}", end="")
        print()
    
    # 줌 익스텐트
    rs.ZoomExtents()