# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
from typing import List, Tuple, Any, Optional

import utils
import importlib

importlib.reload(utils)


if __name__ == "__main__":
    # 파일 경로 설정
    shp_path = os.path.join(os.path.dirname(__file__), "AL_D194_11680_20250123.shp")

    # SHP 파일 읽기
    shapes, records, fields = utils.read_shp_file(shp_path)

    # Parcel 객체 생성
    parcels = utils.get_parcels_from_shapes(shapes, records, fields)

    # 필지 분류
    lots, roads = utils.classify_parcels(parcels)
    print(f"대지: {len(lots)}개, 도로: {len(roads)}개")

    # 지목별 카운트
    jimok_counter = {}
    for parcel in parcels:
        jimok = parcel.jimok
        if jimok in jimok_counter:
            jimok_counter[jimok] += 1
        else:
            jimok_counter[jimok] = 1

    total_count = len(parcels)
    sorted_jimok = sorted(jimok_counter.items(), key=lambda x: x[1], reverse=True)

    # 결과 출력
    print(f"\n전체 필지: {total_count:,}개")
    print(f"\n지목별 분포:")
    print("-" * 40)

    for jimok, count in sorted_jimok:
        percentage = (count / total_count) * 100
        print(f"{jimok:10s}: {count:6,}개 ({percentage:5.2f}%)")

    print("-" * 40)
    print(f"총 지목 종류: {len(jimok_counter)}개")

    # 주요 지목 TOP 5
    print("\n주요 지목 TOP 5:")
    for i, (jimok, count) in enumerate(sorted_jimok[:5]):
        percentage = (count / total_count) * 100
        print(f"{i+1}. {jimok}: {count:,}개 ({percentage:.1f}%)")

    # Grasshopper 출력용 변수
    all_lot_crvs = [lot.region for lot in lots]
    road_crvs = [road.region for road in roads]
