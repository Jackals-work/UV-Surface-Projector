# 🇬🇧 English

# UV Surface Projector

**Blender Add-on — UV-Based Surface Projection**

---

## 📌 Overview

**UV Surface Projector Pro** is a Blender add-on for projecting selected objects onto a Mesh surface using the **UV map of the active object**.

The workflow is simple:

* **Active Object = Target**
* **Other Selected Objects = Sources**
* Supports:

  * Curves
  * Meshes
* Source coordinates are normalized into the Target UV space.
* UV coordinates are then converted into real surface positions.

The add-on is useful for:

* Engravings
* Decorative patterns
* Logos
* Curves
* Jewelry design
* Curved surfaces
* 3D-print preparation
* Mesh projection
* Curve projection

---

# ✨ Features

## 🎯 Active Object = Target

The active object is automatically treated as the Target.

No separate Target selector is required.

Example:

```text
Target
  ↓
Active Mesh

Sources
  ↓
Curve
Mesh
Curve
Mesh
```

Multiple sources can be selected at the same time.

---

# 🔄 Multiple Sources

The add-on can process multiple Sources in one operation.

Example:

```text
Target      ← Active Mesh

Source 01   ← Curve
Source 02   ← Curve
Source 03   ← Mesh
Source 04   ← Mesh
```

---

# ⚙️ Source

Controls which selected objects are treated as Sources.

### Auto

```text
Curve + Mesh
```

Uses all selected Curves and Meshes except the Target.

### Curve

```text
Curves only
```

### Mesh

```text
Meshes only
```

---

# 🛠 Projection / Cut

Contains projection and source modification settings.

### Cut / Modify Source

When enabled, Mesh Sources are modified directly.

Curves are converted into projected surface curves.

### Preserve Edges

Attempts to preserve source topology and avoid unnecessary aggressive vertex welding.

---

# 🗺 UV Projection

This is the core of the add-on.

### Clip Outside UV

When enabled, source parts outside the actual UV islands are removed.

```text
Inside UV Island
      ↓
   Kept

Outside UV Island
      ↓
   Clipped
```

---

### Keep Aspect Ratio

Maintains the original width/height ratio while fitting the source into the UV area.

---

### Flip V

Flips the V coordinate of the UV space.

Useful when the source and Target use different V orientations.

---

### Nearest Triangle

Finds the nearest UV triangle for points that are close to UV boundaries.

This can improve handling of points near UV island edges.

---

# 📏 Edge Margin

The Edge Margin feature creates a safe distance from UV boundaries.

### Enable Edge Margin

When disabled:

```text
Margin = 0
```

No edge distance is removed.

This allows the source to use the full available UV area.

---

## Margin Modes

### UV

Uses UV units.

Example:

```text
0.002
```

---

### Percent

Uses a percentage of the UV dimensions.

Example:

```text
1
```

means:

```text
1%
```

---

### Millimeters

Allows the margin to be specified in millimeters.

The add-on estimates the corresponding UV distance from the Target dimensions.

---

# 📐 Curve Settings

Controls the generated surface curves.

### Curve Samples

Controls the number of samples used when converting Bezier curves into projected points.

Higher values:

```text
Higher accuracy
```

but also:

```text
More points
+
Slower processing
```

Default:

```text
150
```

---

### Bevel Depth

Controls the thickness of generated curves.

```text
0
```

means no additional bevel thickness.

---

### Bevel Resolution

Controls the smoothness of the curve bevel.

---

# 🧩 UV Boundary

The:

```text
UV Boundary
```

button creates a flat representation of the UV island boundaries.

The result contains:

```text
Edges only
```

No faces are created.

The result is stored in:

```text
UV_Flat_Comparison
```

This can be used to compare the UV layout with the real-world surface shape.

---

# 🧹 Clear

### Clear

Removes the generated UV Boundary.

### Clear Results

Removes generated projection results from:

```text
UV_Projector_Results
```

The original Target is not deleted.

---

# 📦 Collections

The add-on automatically creates:

```text
UV_Projector_Results
```

for projected curve results.

It also creates:

```text
UV_Flat_Comparison
```

for UV boundary visualization.

---

# 🚀 Usage

## Step 1 — Prepare the Target

Select a Mesh that contains a UV Map.

Make sure it is the:

```text
Active Object
```

---

## Step 2 — Select Sources

While keeping the Target active, select the objects you want to project.

Example:

```text
Target     ← Active

Curve 01
Curve 02
Mesh 01
Mesh 02
```

---

## Step 3 — Open the Add-on

Go to:

```text
3D Viewport
    ↓
N
    ↓
UV Projector
```

---

## Step 4 — Select Source Type

Choose:

```text
Auto
```

or:

```text
Curve
```

or:

```text
Mesh
```

---

## Step 5 — Configure UV Projection

Available options:

```text
Clip Outside UV
Keep Aspect Ratio
Flip V
Nearest Triangle
```

---

## Step 6 — Configure Margin

For full UV usage:

```text
Enable Edge Margin = OFF
```

For a safe distance:

```text
Enable Edge Margin = ON
```

Then choose:

```text
UV
Percent
Millimeters
```

---

## Step 7 — Project

Click:

```text
Project / Cut
```

---

# 🎯 Practical Example

Suppose you have:

```text
Target:
Ring Mesh

Source:
Logo Curve
```

Set:

```text
Ring Mesh = Active
Source Type = Curve
Keep Aspect Ratio = ON
Clip Outside UV = ON
Edge Margin = OFF
```

Then click:

```text
Project / Cut
```

The add-on creates a new curve positioned on the ring surface according to its UV layout.

---

# ⚠️ Important Notes

### 1. Target must be a Mesh

The active object must be:

```text
MESH
```

---

### 2. Target must have UVs

The projection system requires a UV Map.

---

### 3. At least one Source is required

You must select the Target and one or more Sources.

---

### 4. Active Object matters

The active object is always:

```text
TARGET
```

All other selected compatible objects are:

```text
SOURCES
```

---

### 5. Mesh Sources are modified

Mesh Sources are modified directly during projection.

It is recommended to keep a backup or duplicate of important source meshes.

---

# 🐛 Common Errors

### Target has no UV

Error:

```text
The active object has no UV Map.
```

Solution:

Create a UV Map for the Target using Blender's UV tools.

---

### No Source

Error:

```text
Select the Target as the Active Object and select other objects as Sources.
```

Solution:

Select at least one additional Curve or Mesh.

---

### Source is outside the UV

When:

```text
Clip Outside UV = ON
```

parts outside the UV islands may be removed.

---

# 🔒 How It Works

The projection process follows this general pipeline:

```text
Source Coordinates
        ↓
Normalize
        ↓
UV Space
        ↓
UV Triangles
        ↓
Barycentric Coordinates
        ↓
Target Surface Position
        ↓
World Coordinates
```

This allows UV coordinates to be converted into actual positions on the Target surface.

---

# 💻 Requirements

* Blender 4.0 or newer
* Blender's built-in Python
* A Mesh Target with a UV Map

No external Python packages are required.

Main Blender modules used:

```python
bpy
bmesh
math
mathutils
```

---

# 📜 License

Developed by:

**Simple Code**

The source code can be modified and extended according to project requirements.

---

## Version

```text
UV Surface Projector Pro
Version: 3.0.1
Blender: 4.0+
```

---

## Author

**Simple Code**

UV Surface Projector Pro
