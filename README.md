# LausLecture

# Rhino의 파이썬 API를 활용한 설계 자동화

## Rhino?
- .NET Core 기반의 크로스플랫폼 툴 (윈도우와 맥에서 사용 가능)

---

## Python 기반으로 사용 가능한 3가지 API

### 1. [RhinoCommon](https://developer.rhino3d.com/api/rhinocommon/)
- Rhino의 공식 .NET 기반 API
- 3D 지오메트리 및 객체를 생성하고 조작하는 저수준의 강력한 함수 제공

### 2. [RhinoScriptContext (rhinoscriptsyntax)](https://developer.rhino3d.com/api/RhinoScriptSyntax/)
- RhinoCommon을 래핑한 파이썬 라이브러리
- 직관적인 함수 사용으로 빠른 3D 작업 가능

### 3. Grasshopper (GhPythonlib)
- 공식 문서 없음
- Grasshopper 컴포넌트를 파이썬 스크립트에서 직접 활용 가능
- RhinoCommon 기반 기능을 파이썬으로 호출하여 비주얼 프로그래밍 확장

---

## 객체 구조 (Object Structure)

```plaintext
RhinoDoc
├── Objects (List<RhinoObject>)
│   └── RhinoObject
│       ├── Attributes : ObjectAttributes
│       │   ├── Name
│       │   ├── LayerIndex
│       │   ├── ColorSource
│       │   └── UserStrings
│       └── Geometry : GeometryBase
│           ├── Point
│           ├── Curve
│           │   ├── LineCurve
│           │   ├── PolylineCurve
│           │   ├── ArcCurve
│           │   └── NurbsCurve
│           ├── Surface
│           │   └── NurbsSurface
│           ├── Brep
│           └── Mesh
├── Layers (List<Layer>)
├── Materials (List<Material>)
├── Views (List<View>)
└── 기타 구성요소
```

---

# Lecture #1: Rhino Python 개발환경 및 기초 객체 활용

## Practice 1) Rhino Python 개발 환경 세팅

## Practice 2) Rhino Python 기본 객체 활용

## Practice 3) GitHub 활용 및 프로젝트 관리

---

# Lecture #2: Rhino Python을 이용한 GIS 데이터 분석

## Practice 1) 서울시 필지 데이터 전처리
- 결측치 처리
- Offset을 활용하여 필지 간 틈과 겹침 제거
- 꼬인 커브 제거
- 커브 단순화

## Practice 2) 서울시 맹지 탐색
- 도로와 닿아있지 않은 필지 골라내기

## Practice 3) 서울시 자루형 필지 탐색
- 도로와 닿아있지만 자루형 형태의 필지 분류

## Practice 4) 가로주택정비사업 가능한 블록 탐색
- 면적 1만 m² 미만
- 공공시설로 둘러싸인 블록
- 폭 4m 초과 도로 관통 금지

---

# Lecture #3~4: GIS 기반 건축 설계 자동화

## Practice 1) 지오메트리 정보 전처리

## Practice 2) 건축 가능 영역 생성
- 사선 제한 반영
- 높이 제한 반영

## Practice 3) 건물 라인 생성
- 용도 반영
- 건폐율 및 용적률 반영
- 대지 안 공지 및 기타 규제 고려

## Practice 4) 층별 건물 라인 생성
- 목표 면적 반영
- 건축 가능 영역 반영 (사선 제한, 높이 제한)

---

# Lecture #5: 기타 요소 설계 자동화

## Practice 1) 공개공지 설계 자동화

## Practice 2) 주차장 설계 자동화

---

# Lecture #6: GIS 데이터 분석 응용

## Practice 1) Isovist를 활용한 보행자 시각 분석

## Practice 2) Offset을 활용한 유사 필지 필터링

---

> 해당 문서는 자동화 설계를 위한 Rhino + Python 기반 스터디용 프로젝트 구성 파일입니다. 각 Lecture와 Practice는 개별 스크립트/노트북 또는 `.gh/.py` 모듈로 구성될 수 있으며, GitHub 프로젝트 폴더 구조에 따라 정리 예정입니다.

