# r: pyshp

import Rhino.Geometry as geo
import shapefile
import os
import zipfile
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


def get_curve_from_points(
    points: List[Tuple[float, float]], start_idx: int, end_idx: int
) -> Optional[geo.PolylineCurve]:
    """점 리스트에서 특정 구간의 커브를 생성"""
    # 최소 3개의 점이 필요
    if end_idx - start_idx < 3:
        return None

    # 시작과 끝 점이 동일하지 않으면(닫혀있지 않으면) None 반환
    first_pt = points[start_idx]
    last_pt = points[end_idx - 1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        return None

    curve_points = [
        geo.Point3d(points[i][0], points[i][1], 0) for i in range(start_idx, end_idx)
    ]

    curve_crv = geo.PolylineCurve(curve_points)
    return curve_crv if curve_crv and curve_crv.IsValid else None


def get_part_indices(shape: Any) -> List[Tuple[int, int]]:
    """shape의 각 파트의 시작과 끝 인덱스를 반환"""
    if not hasattr(shape, "parts") or len(shape.parts) <= 1:
        return [(0, len(shape.points))]

    parts = list(shape.parts) + [len(shape.points)]
    return [(parts[i], parts[i + 1]) for i in range(len(shape.parts))]


def get_curves_from_shape(
    shape: Any,
) -> Tuple[Optional[geo.PolylineCurve], List[geo.PolylineCurve]]:
    """shape에서 외부 경계와 내부 구멍 커브들을 추출"""
    boundary_region = None
    hole_regions = []

    part_indices = get_part_indices(shape)

    for i, (start_idx, end_idx) in enumerate(part_indices):
        curve_crv = get_curve_from_points(shape.points, start_idx, end_idx)
        if curve_crv:
            if i == 0:
                boundary_region = curve_crv
            else:
                hole_regions.append(curve_crv)

    # 단일 폴리곤이고 닫혀있지 않은 경우 처리
    if boundary_region is None and len(part_indices) == 1:
        points = [geo.Point3d(pt[0], pt[1], 0) for pt in shape.points]
        if len(points) >= 3:
            if points[0].DistanceTo(points[-1]) > 0.001:
                points.append(points[0])
            curve_crv = geo.PolylineCurve(points)
            if curve_crv and curve_crv.IsValid:
                boundary_region = curve_crv

    return boundary_region, hole_regions


def get_field_value(
    record: List[Any], fields: List[str], field_name: str, default: str = "Unknown"
) -> str:
    """레코드에서 특정 필드값을 안전하게 추출"""
    try:
        index = fields.index(field_name)
        return record[index]
    except (ValueError, IndexError):
        return default


def create_parcel_from_shape(
    shape: Any, record: List[Any], fields: List[str]
) -> Optional[Parcel]:
    """shape에서 Parcel 객체 생성"""
    boundary_region, hole_regions = get_curves_from_shape(shape)

    if not boundary_region or not boundary_region.IsValid:
        return None

    pnu = get_field_value(record, fields, "A1")  # 구 PNU
    jimok = get_field_value(record, fields, "A11")  # 구 JIMOK

    if jimok == "도로":
        parcel = Road(boundary_region, pnu, jimok, record, hole_regions)
    else:
        parcel = Lot(boundary_region, pnu, jimok, record, hole_regions)

    return parcel if parcel.preprocess_curve() else None


def get_parcels_from_shapes(
    shapes: List[Any], records: List[Any], fields: List[str]
) -> List[Parcel]:
    """모든 shape에서 Parcel 객체들을 생성"""
    parcels = []

    for shape, record in zip(shapes, records):
        parcel = create_parcel_from_shape(shape, record, fields)
        if parcel:
            parcels.append(parcel)

    return parcels


def classify_parcels(parcels: List[Parcel]) -> Tuple[List[Lot], List[Road]]:
    """Parcel 리스트를 Lot과 Road로 분류"""
    lots = []
    roads = []

    for parcel in parcels:
        if isinstance(parcel, Road):
            roads.append(parcel)
        else:
            lots.append(parcel)

    return lots, roads


# ================ GeometryUtils 함수들 ================


def get_point_from_shape(pts: List) -> geo.Point3d:
    """단일 포인트 정보만 갖고있는 리스트를 Point3d로 변환"""
    pts = list(pts)
    if len(pts) == 2:
        pts.append(0)
    return geo.Point3d(*pts)


def get_vertices(curve: geo.Curve) -> List[geo.Point3d]:
    """커브의 정점들을 추출"""
    vertices = [curve.PointAt(curve.SpanDomain(i)[0]) for i in range(curve.SpanCount)]
    if not curve.IsClosed:
        vertices.append(curve.PointAtEnd)
    return vertices


def get_projected_pt_on_mesh(pt: geo.Point3d, mesh: geo.Mesh) -> Optional[geo.Point3d]:
    """점을 메시에 투영"""
    for direction in [geo.Vector3d(0, 0, -1), geo.Vector3d(0, 0, 1)]:
        ray = geo.Ray3d(pt, direction)
        t = geo.Intersect.Intersection.MeshRay(mesh, ray)
        if t >= 0:
            return ray.PointAt(t)
    return None


# ================ Shape type mapping ================

SHAPE_TYPES = {
    "point": [
        1,  # POINT
        8,  # MULTIPOINT
        11,  # POINTS
        18,  # MULTIPOINTZ
        21,  # POINTM
        28,  # MULTIPOINTM
    ],
    "polyline": [
        3,  # POLYLINE
        5,  # POLYGON
        13,  # POLYLINES
        15,  # POLYGONZ
        23,  # POLYLINEM
        25,  # POLYGONM
        31,  # MULTIPATCH
    ],
}


def find_shape_type(shape_type_id: int) -> Optional[str]:
    """Shape type ID로부터 type 이름을 찾기"""
    for key, values in SHAPE_TYPES.items():
        if shape_type_id in values:
            return key
    return None


# ================ Shapefile 파싱 함수들 ================


def parse_geometry(shape: Any, shape_type: str) -> List[Any]:
    """shape 객체를 geometry로 파싱"""
    if shape_type == "point":
        return [get_point_from_shape(pt) for pt in shape.points]
    elif shape_type == "polyline":
        parts = [
            shape.points[
                shape.parts[i] : (
                    shape.parts[i + 1] if i + 1 < len(shape.parts) else None
                )
            ]
            for i in range(len(shape.parts))
        ]
        return [
            geo.PolylineCurve([get_point_from_shape(pt) for pt in part])
            for part in parts
        ]
    return []


def read_shapefile_from_reader(sf: shapefile.Reader, encoding: str = "utf-8") -> Tuple:
    """shapefile.Reader 객체에서 데이터 읽기"""
    result_geom = []
    result_fields = []
    result_field_names = []
    result_records = []

    shape_type = find_shape_type(sf.shapeType)

    # Extract field names
    for field in sf.fields:
        if field[0] != "DeletionFlag":
            _field = field[0]
            if isinstance(_field, bytes):
                _field = _field.decode(encoding, errors="replace")
            result_field_names.append(_field)
            result_fields.append(field)

    # Extract geometry and records
    for shape, record in zip(sf.shapes(), sf.records()):
        geom = parse_geometry(shape, shape_type)
        result_geom.append(geom)
        _record = []
        for rec in record:
            if isinstance(rec, bytes):
                _record.append(rec.decode(encoding, errors="replace"))
            else:
                _record.append(rec)
        result_records.append(_record)

    return (
        shape_type,
        result_geom,
        result_fields,
        result_field_names,
        result_records,
    )


# ================ Contour 처리 함수들 ================


def create_contour_curves(
    contour_geometry_records: List[Tuple],
) -> List[geo.PolylineCurve]:
    """contour geometry와 record로부터 3D 커브 생성"""
    contour_crvs = []
    for contour_geom, contour_record in contour_geometry_records:
        contour_crvs.append(
            geo.PolylineCurve(
                [
                    geo.Point3d(
                        contour_geom[0].Point(pt_count).X,
                        contour_geom[0].Point(pt_count).Y,
                        contour_record[1],
                    )
                    for pt_count in range(contour_geom[0].SpanCount)
                ]
            )
        )
    return contour_crvs


def create_points_for_mesh(
    contour_curves: List[geo.Curve], resolution: float
) -> List[geo.Point3d]:
    """contour 커브들로부터 메시 생성용 점들 생성"""
    points = []
    for curve in contour_curves:
        params = curve.DivideByLength(resolution, True)
        if params:
            points.extend([curve.PointAt(param) for param in params])
    return points


# ================ Building 처리 함수들 ================


def create_building_breps(
    building_geometry_records: List[Tuple], mesh_terrain: geo.Mesh
) -> List[geo.Brep]:
    """건물 geometry와 record로부터 Brep 생성"""
    breps = []
    for geom, record in building_geometry_records:
        base_curve = geom[0]
        height = record[5] * 3.5
        vertices = get_vertices(base_curve)

        projected_pts = [get_projected_pt_on_mesh(pt, mesh_terrain) for pt in vertices]
        projected_pts = list(filter(None, projected_pts))

        if projected_pts:
            min_z = min(pt.Z for pt in projected_pts)
            base_curve.Translate(geo.Vector3d(0, 0, min_z - vertices[0].Z))
            breps.append(geo.Extrusion.Create(base_curve, -height, True))
    return breps


# ================ ZIP/Shapefile 처리 함수들 ================


def read_shapefiles_from_zip(
    zip_paths: List[str], file_prefixes: List[str]
) -> List[shapefile.Reader]:
    """ZIP 파일들에서 shapefile 읽기"""
    readers = []
    zip_files = [zipfile.ZipFile(zip_path, "r") for zip_path in zip_paths]

    for zip_file in zip_files:
        for prefix in file_prefixes:
            try:
                readers.append(
                    shapefile.Reader(
                        shp=zip_file.open(f"{prefix}.shp"),
                        shx=zip_file.open(f"{prefix}.shx"),
                        dbf=zip_file.open(f"{prefix}.dbf"),
                        prj=zip_file.open(f"{prefix}.prj"),
                    )
                )
            except KeyError:
                continue

    # Close zip files
    for zip_file in zip_files:
        zip_file.close()

    return readers


# ================ ShpData 클래스 ================


class ShpData:
    """Shapefile 데이터를 저장하는 클래스"""

    def __init__(
        self,
        shape_type: str,
        geometry: List,
        fields: List,
        field_names: List[str],
        records: List,
    ):
        self.shape_type = shape_type
        self.geometry = geometry
        self.fields = fields
        self.field_names = field_names
        self.records = records


def extract_data_from_shapefiles(shapefiles: List[shapefile.Reader]) -> ShpData:
    """여러 shapefile에서 데이터 추출하여 ShpData로 통합"""
    all_geometry = []
    all_fields = []
    all_field_names = []
    all_records = []
    shape_type = None

    for sf in shapefiles:
        result = read_shapefile_from_reader(sf)
        if shape_type is None:
            shape_type = result[0]
        all_geometry.extend(result[1])
        all_fields.extend(result[2])
        all_field_names.extend(result[3])
        all_records.extend(result[4])

    return ShpData(shape_type, all_geometry, all_fields, all_field_names, all_records)
