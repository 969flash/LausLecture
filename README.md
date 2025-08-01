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

## Practice 1) 서울시의 필지 데이터의 전처리 작업

## Practice 2) 서울시의 필지 중 맹지를 탐색해보자.

## Practice 3) 서울시의 필지  중 자루형 필지를 탐색해보자.


---

# Lecture #3: GIS 기반 건축 설계 자동화

Practice 1) 서울시 내 가로주택 정비사업시행이 가능한 블록?
---

# Lecture #4: 기타 요소 설계 자동화

## Practice 1) 공개공지 설계 자동화


---

# Lecture #5: GIS 데이터 분석 응용

## Practice 1) Isovist를 활용한 보행자 시각 분석

## Practice 2) Offset을 활용한 유사 필지 필터링

---


