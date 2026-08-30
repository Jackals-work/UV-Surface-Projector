# UV Surface Projector Pro

**Blender Add-on — UV-Based Surface Projection**

---

## 🇸🇦 العربية

### 📌 نظرة عامة

**UV Surface Projector Pro** هي إضافة لـ Blender تسمح بإسقاط العناصر المحددة على سطح Mesh اعتمادًا على خريطة الـ **UV** الخاصة بالعنصر النشط.

تعتمد الإضافة على نظام بسيط:

* **العنصر النشط Active Object = Target**
* **بقية العناصر المحددة = Sources**
* يدعم المصدر:

  * Curves
  * Meshes
* يتم تحويل إحداثيات المصدر إلى مساحة UV الخاصة بالـ Target.
* بعدها يتم تحويل نقاط الـ UV إلى مواقع حقيقية على سطح الـ Mesh.

الإضافة مناسبة بشكل خاص للعمل مع:

* النقوش والزخارف
* الشعارات
* الخطوط والمنحنيات
* تصميمات المجوهرات
* الإسقاط على الأسطح المنحنية
* تجهيز عناصر للطباعة ثلاثية الأبعاد
* إسقاط Mesh أو Curve على سطح له UV

---

## ✨ المميزات

### 🎯 Active Object = Target

لا تحتاج إلى اختيار Target من قائمة منفصلة.

العنصر الذي يكون **Active** هو الـ Target تلقائيًا.

مثال:

```text
Target
  ↓
Mesh النشط

Sources
  ↓
Curve
Mesh
Curve
Mesh
```

يمكن تحديد عدة Sources في نفس الوقت.

---

### 🔄 Multiple Sources

يمكن معالجة عدة عناصر دفعة واحدة.

مثال:

```text
Target      ← Active Mesh

Source 01   ← Curve
Source 02   ← Curve
Source 03   ← Mesh
Source 04   ← Mesh
```

سيتم تنفيذ الإسقاط على جميع العناصر المحددة التي تطابق نوع المصدر المختار.

---

# ⚙️ Source

قسم **Source** يحدد نوع العناصر التي سيتم اعتبارها Sources.

### Auto

```text
Curve + Mesh
```

يستخدم جميع الـ Curves والـ Meshes المحددة باستثناء الـ Target.

### Curve

```text
Curve فقط
```

### Mesh

```text
Mesh فقط
```

---

# 🛠 Projection / Cut

يحتوي هذا القسم على إعدادات الإسقاط وتعديل الـ Mesh.

### Cut / Modify Source

عند تفعيل هذا الخيار يمكن تعديل الـ Source Mesh مباشرة أثناء الإسقاط.

بالنسبة إلى Curves، يتم إنشاء Curve جديدة على سطح الـ Target.

### Preserve Edges

يحاول الحفاظ على Topology الخاصة بالمصدر وتقليل عمليات دمج الـ Vertices غير الضرورية.

---

# 🗺 UV Projection

هذا هو الجزء الأساسي من الإضافة.

### Clip Outside UV

عند تفعيله:

يتم حذف الأجزاء التي تقع خارج مناطق الـ UV الفعلية.

```text
داخل UV Island
      ↓
    يبقى

خارج UV Island
      ↓
   يتم قصه
```

### Keep Aspect Ratio

يحافظ على نسبة العرض إلى الارتفاع للمصدر أثناء تحويله إلى مساحة UV.

بدون هذا الخيار يمكن أن يتم تمديد المصدر أفقيًا أو عموديًا.

---

### Flip V

يقلب محور V الخاص بالـ UV.

```text
V

1 ─────────
  │
  │
0 ─────────
```

عند تفعيل **Flip V**:

```text
V

0 ─────────
  │
  │
1 ─────────
```

يستخدم هذا الخيار عند اختلاف اتجاه UV بين المصدر وطريقة الإسقاط المطلوبة.

---

### Nearest Triangle

يستخدم أقرب UV Triangle عندما تكون النقطة خارج المثلث مباشرة أو قريبة جدًا من حدوده.

يساعد ذلك في التعامل مع النقاط القريبة من حدود الـ UV.

---

# 📏 Edge Margin

يمكن استخدام Margin لمنع الإسقاط من الوصول إلى أطراف الـ UV Islands.

### Enable Edge Margin

عند تعطيله:

```text
Margin = 0
```

أي أنه **لا يتم خصم أي مسافة من الأطراف**.

وهذا مهم جدًا عندما تريد استخدام كامل مساحة الـ UV.

---

## أنواع Margin

### UV

القيمة تكون بوحدات UV.

مثال:

```text
0.002
```

يعني:

```text
U Margin = 0.002
V Margin = 0.002
```

---

### Percent

القيمة كنسبة مئوية من مساحة الـ UV.

مثال:

```text
1
```

يعني:

```text
1%
```

---

### Millimeters

يمكن إدخال المسافة بالـ mm.

مثال:

```text
2 mm
```

تحاول الإضافة تقدير المسافة المقابلة في UV اعتمادًا على أبعاد الـ Target.

---

# 📐 Curve Settings

تحتوي على إعدادات الـ Curve الناتجة.

### Curve Samples

عدد النقاط المستخدمة لتحويل الـ Bezier Curve إلى نقاط أثناء الإسقاط.

قيمة أكبر:

```text
دقة أعلى
```

ولكن:

```text
نقاط أكثر
+
معالجة أبطأ
```

القيمة الافتراضية:

```text
150
```

---

### Bevel Depth

يحدد سمك الـ Curve الناتجة.

إذا كانت:

```text
0
```

فسيتم إنشاء Curve بدون سمك إضافي.

---

### Bevel Resolution

يحدد دقة الـ Bevel للـ Curve.

---

# 🧩 UV Boundary

زر:

```text
UV Boundary
```

يقوم بإنشاء نسخة مسطحة من حدود الـ UV Islands.

هذه النسخة تحتوي على:

```text
Edges فقط
```

ولا تحتوي على Faces.

يتم إنشاء النتيجة داخل Collection:

```text
UV_Flat_Comparison
```

ويمكن استخدام هذه النتيجة لمقارنة:

```text
UV Layout
```

مع:

```text
Surface / Real World Shape
```

---

# 🧹 Clear

### Clear

يحذف نتيجة:

```text
UV Boundary
```

### Clear Results

يحذف النتائج الموجودة داخل:

```text
UV_Projector_Results
```

ولا يقوم بحذف الـ Target الأصلي.

---

# 📦 Collections

الإضافة تنشئ Collection تلقائيًا للنتائج:

```text
UV_Projector_Results
```

تستخدم لتخزين Curves الناتجة من الإسقاط.

كما تنشئ:

```text
UV_Flat_Comparison
```

لتخزين نسخة حدود الـ UV.

---

# 🚀 طريقة الاستخدام

## الخطوة 1 — تجهيز Target

حدد Mesh يحتوي على UV Map.

مثال:

```text
Object A
```

ثم اجعله:

```text
Active Object
```

---

## الخطوة 2 — تحديد Sources

مع إبقاء الـ Target Active، حدد العناصر التي تريد إسقاطها.

مثال:

```text
Target     ← Active

Curve 01
Curve 02
Mesh 01
Mesh 02
```

---

## الخطوة 3 — فتح الإضافة

من:

```text
3D Viewport
    ↓
N
    ↓
UV Projector
```

---

## الخطوة 4 — اختيار Source Type

اختر:

```text
Auto
```

أو:

```text
Curve
```

أو:

```text
Mesh
```

---

## الخطوة 5 — ضبط UV Projection

اختر الإعدادات المناسبة:

```text
Clip Outside UV
Keep Aspect Ratio
Flip V
Nearest Triangle
```

---

## الخطوة 6 — Margin اختياري

إذا كنت تريد الإسقاط حتى حدود الـ UV:

```text
Enable Edge Margin = OFF
```

إذا أردت ترك مسافة:

```text
Enable Edge Margin = ON
```

ثم اختر:

```text
UV
Percent
Millimeters
```

---

## الخطوة 7 — تنفيذ الإسقاط

اضغط:

```text
Project / Cut
```

---

# 🎯 مثال عملي

لنفترض أن لديك:

```text
Target:
Ring Mesh

Source:
Logo Curve
```

الترتيب:

```text
Ring Mesh
   +
Logo Curve
```

اجعل:

```text
Ring Mesh = Active
```

ثم:

```text
Source Type = Curve
Keep Aspect Ratio = ON
Clip Outside UV = ON
Margin = OFF
```

ثم:

```text
Project / Cut
```

ستنشئ الإضافة Curve جديدة موضوعة على سطح الحلقة وفقًا لخريطة الـ UV.

---

# ⚠️ ملاحظات مهمة

### 1. Target يجب أن يكون Mesh

العنصر النشط يجب أن يكون:

```text
MESH
```

---

### 2. Target يجب أن يحتوي على UV

بدون UV Map لن تعمل عملية الإسقاط.

---

### 3. يجب وجود Source

يجب تحديد عنصر أو أكثر بالإضافة إلى Target.

---

### 4. Active Object مهم

العنصر النشط هو دائمًا:

```text
TARGET
```

أما العناصر المحددة الأخرى فهي:

```text
SOURCES
```

---

### 5. Mesh Sources

عند استخدام Mesh كمصدر، يتم تعديل الـ Mesh المصدر نفسه.

يفضل عمل نسخة احتياطية قبل العمليات الكبيرة.

---

# 📁 بنية الإضافة

يمكن وضع الإضافة كملف Python واحد:

```text
uv_surface_projector_pro.py
```

أو تثبيتها كـ Blender Add-on.

---

# 💻 المتطلبات

* Blender 4.0 أو أحدث
* Python المدمج مع Blender
* Mesh Target يحتوي على UV Map

لا تحتاج الإضافة إلى مكتبات خارجية.

المكتبات المستخدمة من Blender:

```python
bpy
bmesh
math
mathutils
```

---

# 🐛 الأخطاء الشائعة

### Target لا يحتوي على UV

الرسالة:

```text
العنصر النشط لا يحتوي على UV Map.
```

الحل:

أنشئ UV Map للـ Target من:

```text
UV Editing
```

أو:

```text
U → Unwrap
```

---

### لا يوجد Source

الرسالة:

```text
حدد Target كعنصر Active ثم حدد معه العناصر الأخرى كمصادر.
```

الحل:

حدد Target + مصدر واحد على الأقل.

---

### المصدر خارج UV

إذا كان:

```text
Clip Outside UV = ON
```

فالأجزاء الواقعة خارج الـ UV Islands قد يتم حذفها.

---

# 🔒 مبدأ العمل

الإضافة لا تعتمد على إسقاط Ray التقليدي فقط.

بل تستخدم:

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

وبذلك يمكن تحويل نقطة UV إلى موقع فعلي على سطح الـ Target.

---

# 📜 الترخيص

هذا المشروع تم تطويره بواسطة:

**Simple Code**

يمكن تعديل الكود وتطويره حسب احتياجات المشروع.

---

# 🇬🇧 English

# UV Surface Projector Pro

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
