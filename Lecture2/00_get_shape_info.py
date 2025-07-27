# r: pyshp

import shapefile
import os
from collections import Counter
from typing import List, Tuple, Dict, Any


# =============================================================================
# 1. SHP 파일에서 데이터 읽어오기
# =============================================================================
def read_shp_file(file_path: str) -> Tuple[List[Any], List[Any], List[str]]:
    """shapefile을 읽어서 shapes와 records를 반환"""
    # 간단하게 utf-8로 먼저 시도, 실패시 cp949
    try:
        sf = shapefile.Reader(file_path, encoding="utf-8")
    except:
        try:
            sf = shapefile.Reader(file_path, encoding="cp949")
        except:
            sf = shapefile.Reader(file_path)  # 인코딩 없이

    shapes = sf.shapes()
    records = sf.records()
    fields = [field[0] for field in sf.fields[1:]]  # 필드명 리스트
    return shapes, records, fields


# =============================================================================
# 2. 지목 정보 분석
# =============================================================================
def analyze_jimok_distribution(
    records: List[Any], fields: List[str]
) -> Tuple[Dict[str, int], int]:
    """지목별 분포를 분석하여 반환"""
    
    # JIMOK 필드의 인덱스 찾기
    jimok_index = fields.index("JIMOK") if "JIMOK" in fields else -1
    
    if jimok_index == -1:
        print("JIMOK 필드를 찾을 수 없습니다.")
        return {}, 0
    
    # 지목별 카운트
    jimok_counter = Counter()
    
    for record in records:
        jimok = record[jimok_index] if jimok_index >= 0 else "Unknown"
        jimok_counter[jimok] += 1
    
    total_count = sum(jimok_counter.values())
    
    return dict(jimok_counter), total_count


# =============================================================================
# 3. 결과 출력 및 정리
# =============================================================================
def print_jimok_analysis(jimok_distribution: Dict[str, int], total_count: int):
    """지목 분석 결과를 보기 좋게 출력"""
    
    print("\n" + "="*60)
    print("지목별 분포 분석 결과")
    print("="*60)
    print(f"\n총 필지 수: {total_count:,}개")
    print("\n지목별 상세 분포:")
    print("-"*40)
    
    # 빈도순으로 정렬
    sorted_jimok = sorted(jimok_distribution.items(), key=lambda x: x[1], reverse=True)
    
    for jimok, count in sorted_jimok:
        percentage = (count / total_count) * 100
        print(f"{jimok:10s}: {count:6,}개 ({percentage:5.2f}%)")
    
    print("-"*40)
    print(f"총 지목 종류: {len(jimok_distribution)}개")
    
    # 주요 지목 요약
    print("\n주요 지목 TOP 5:")
    print("-"*40)
    for i, (jimok, count) in enumerate(sorted_jimok[:5]):
        percentage = (count / total_count) * 100
        print(f"{i+1}. {jimok}: {count:,}개 ({percentage:.1f}%)")
    
    return sorted_jimok


# =============================================================================
# 메인 실행 코드
# =============================================================================
if __name__ == "__main__":
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "11680.shp")
    
    # 1. SHP 파일 읽기
    print("[1] SHP 파일 읽기 중...")
    shapes, records, fields = read_shp_file(shp_path)
    print(f"    - 총 {len(shapes)}개의 shape 로드 완료")
    
    # 2. 지목 분석
    print("\n[2] 지목 정보 분석 중...")
    jimok_distribution, total_count = analyze_jimok_distribution(records, fields)
    
    # 3. 결과 출력
    sorted_jimok_list = print_jimok_analysis(jimok_distribution, total_count)
    
    # 4. Grasshopper에서 사용할 수 있도록 데이터 준비
    # 지목 이름 리스트
    jimok_names = [item[0] for item in sorted_jimok_list]
    # 지목별 개수 리스트
    jimok_counts = [item[1] for item in sorted_jimok_list]
    # 지목별 비율 리스트
    jimok_percentages = [(count / total_count * 100) for count in jimok_counts]
    
    print("\n[Grasshopper 출력용 데이터 준비 완료]")
    print(f"- jimok_names: {len(jimok_names)}개 지목")
    print(f"- jimok_counts: 각 지목별 개수")
    print(f"- jimok_percentages: 각 지목별 비율(%)")