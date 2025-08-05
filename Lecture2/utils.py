# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
from typing import List, Tuple, Any, Optional
import ghpythonlib.components as ghcomp


class Parcel:
    """기본 필지 클래스"""

    def __init__(
        self,
        curve_crv: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve],
    ):
        self.region = curve_crv  # 외부 경계 커브
        self.hole_regions = (
            hole_regions if hole_regions is not None else []
        )  # 내부 구멍들
        self.pnu = pnu
        self.jimok = jimok
        self.record = record

    def preprocess_curve(self) -> bool:
        """커브 전처리 (invalid 제거, 자체교차 제거, 단순화)"""
        if not self.region or not self.region.IsValid:
            return False

        # 자체교차 확인
        intersection_events = geo.Intersect.Intersection.CurveSelf(self.region, 0.001)
        if intersection_events:
            simplified = self.region.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
            if simplified:
                self.region = simplified
            else:
                return False

        # 일반 단순화
        simplified = self.region.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
        if simplified:
            self.region = simplified

        # 내부 구멍들도 처리
        valid_holes = []
        for hole in self.hole_regions:
            if hole and hole.IsValid:
                simplified_hole = hole.Simplify(geo.CurveSimplifyOptions.All, 0.1, 1.0)
                if simplified_hole:
                    valid_holes.append(simplified_hole)
                else:
                    valid_holes.append(hole)
        self.hole_regions = valid_holes

        return True


class Road(Parcel):
    """도로 클래스"""

    pass


class Lot(Parcel):
    """대지 클래스"""

    def __init__(
        self,
        curve_crv: geo.Curve,
        pnu: str,
        jimok: str,
        record: List[Any],
        hole_regions: List[geo.Curve] = None,
    ):
        super().__init__(curve_crv, pnu, jimok, record, hole_regions)
        self.is_flag_lot = False  # 자루형 토지 여부
        self.has_road_access = False  # 도로 접근 여부


def read_shp_file(file_path: str) -> Tuple[List[Any], List[Any], List[str]]:
    """shapefile을 읽어서 shapes와 records를 반환"""
    try:
        sf = shapefile.Reader(file_path, encoding="utf-8")
    except:
        try:
            sf = shapefile.Reader(file_path, encoding="cp949")
        except:
            sf = shapefile.Reader(file_path)

    shapes = sf.shapes()
    records = sf.records()
    fields = [field[0] for field in sf.fields[1:]]
    return shapes, records, fields
