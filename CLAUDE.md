# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Rhino Python educational project focused on design automation using Rhino's Python APIs. The project consists of 6 lectures covering GIS data analysis, architectural design automation, and various computational design techniques.

## Key Technologies

### Rhino Python APIs

1. **RhinoCommon** - Low-level .NET-based API for 3D geometry manipulation
2. **rhinoscriptsyntax** - Python wrapper around RhinoCommon for intuitive scripting
3. **GhPythonlib** - Grasshopper component integration in Python scripts

### Object Model
```
RhinoDoc
├── Objects (List<RhinoObject>)
│   └── RhinoObject
│       ├── Attributes (Name, LayerIndex, ColorSource, UserStrings)
│       └── Geometry (Point, Curve, Surface, Brep, Mesh)
├── Layers
├── Materials
└── Views
```

## Project Structure

The project is organized into 6 lectures:
- **Lecture 1**: Rhino Python development environment and basic objects
- **Lecture 2**: GIS data analysis (parcel preprocessing, landlocked detection, flag-lot analysis)
- **Lecture 3-4**: GIS-based architectural design automation (buildable areas, building lines)
- **Lecture 5**: Design automation for public spaces and parking
- **Lecture 6**: Advanced GIS analysis (Isovist, offset filtering)

## Development Guidelines

### Working with Rhino Python
- Scripts can be developed as `.py` files for Rhino Python Editor or `.gh` files for Grasshopper
- Consider both RhinoCommon and rhinoscriptsyntax based on complexity needs
- Test scripts within Rhino environment for geometry visualization

### GIS Data Processing Focus Areas
- Seoul parcel data preprocessing (gaps, overlaps, twisted curves)
- Regulatory compliance checks (setbacks, building coverage, floor area ratio)
- Urban analysis (landlocked parcels, street block analysis)

### Common Operations
- Curve offset for parcel boundary adjustments
- Intersection detection for regulatory compliance
- Area and distance calculations for urban metrics
- Layer management for organizing different data types

