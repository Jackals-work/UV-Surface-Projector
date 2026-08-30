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
