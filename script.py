import bpy
import math


# ============================================================
# UV CURVE -> MESH
# Blender 4.x
# ============================================================

OUTPUT_NAME = "UV_Curve_Project"

# ------------------------------------------------------------
# الإعدادات
# ------------------------------------------------------------

# عكس V
FLIP_V = False

# ملء مساحة UV بالكامل
FIT_TO_UV = True

# الحفاظ على نسبة العرض/الارتفاع
KEEP_ASPECT = True

# إضافة هامش داخل UV
UV_MARGIN = 0.0

# إذا كانت Curve خارج UV
USE_NEAREST_TRIANGLE = True

UV_TOLERANCE = 0.000001

# عدد العينات للـ Bezier
CURVE_SAMPLES = 100

# سمك الناتج
# 0 = بدون سمك
BEVEL_DEPTH = 0.0

BEVEL_RESOLUTION = 3


# ============================================================
# BARYCENTRIC
# ============================================================

def barycentric_2d(p, a, b, c):

    px, py = p

    ax, ay = a
    bx, by = b
    cx, cy = c

    v0x = bx - ax
    v0y = by - ay

    v1x = cx - ax
    v1y = cy - ay

    v2x = px - ax
    v2y = py - ay

    den = (
        v0x * v1y -
        v1x * v0y
    )

    if abs(den) < 1e-12:
        return None

    inv = 1.0 / den

    w2 = (
        v2x * v1y -
        v1x * v2y
    ) * inv

    w3 = (
        v0x * v2y -
        v0y * v2x
    ) * inv

    w1 = 1.0 - w2 - w3

    return w1, w2, w3


def barycentric_3d(weights, a, b, c):

    w1, w2, w3 = weights

    return (
        a * w1 +
        b * w2 +
        c * w3
    )


# ============================================================
# DISTANCE
# ============================================================

def point_segment_distance(p, a, b):

    px, py = p

    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    length_sq = dx * dx + dy * dy

    if length_sq < 1e-15:

        return math.hypot(
            px - ax,
            py - ay
        )

    t = (
        (px - ax) * dx +
        (py - ay) * dy
    ) / length_sq

    t = max(
        0.0,
        min(1.0, t)
    )

    qx = ax + dx * t
    qy = ay + dy * t

    return math.hypot(
        px - qx,
        py - qy
    )


def triangle_distance(p, a, b, c):

    bary = barycentric_2d(
        p,
        a,
        b,
        c
    )

    if bary:

        w1, w2, w3 = bary

        if (
            w1 >= 0 and
            w2 >= 0 and
            w3 >= 0
        ):
            return 0.0

    return min(

        point_segment_distance(
            p, a, b
        ),

        point_segment_distance(
            p, b, c
        ),

        point_segment_distance(
            p, c, a
        )
    )


# ============================================================
# UV TRIANGLES
# ============================================================

def build_uv_triangles(mesh_obj):

    mesh = mesh_obj.data

    if not mesh.uv_layers:

        raise RuntimeError(
            "الـ Mesh لا يحتوي على UV Map."
        )

    uv_layer = mesh.uv_layers.active

    if uv_layer is None:

        raise RuntimeError(
            "لا يوجد UV Map فعال."
        )

    mesh.calc_loop_triangles()

    triangles = []

    for tri in mesh.loop_triangles:

        if len(tri.loops) != 3:
            continue

        uv_points = []
        positions = []

        for loop_index in tri.loops:

            loop = mesh.loops[loop_index]

            uv = uv_layer.data[
                loop_index
            ].uv

            u = float(uv.x)
            v = float(uv.y)

            if FLIP_V:
                v = 1.0 - v

            uv_points.append(
                (u, v)
            )

            vertex = mesh.vertices[
                loop.vertex_index
            ]

            positions.append(
                vertex.co.copy()
            )

        triangles.append(
            {
                "uv": uv_points,
                "pos": positions
            }
        )

    return triangles


# ============================================================
# UV BOUNDS
# ============================================================

def get_uv_bounds(triangles):

    min_u = float("inf")
    max_u = float("-inf")

    min_v = float("inf")
    max_v = float("-inf")

    for tri in triangles:

        for u, v in tri["uv"]:

            min_u = min(min_u, u)
            max_u = max(max_u, u)

            min_v = min(min_v, v)
            max_v = max(max_v, v)

    return (
        min_u,
        max_u,
        min_v,
        max_v
    )


# ============================================================
# CURVE POINTS
# ============================================================

def bezier_point(
    p0,
    p1,
    p2,
    p3,
    t
):

    u = 1.0 - t

    return (
        p0 * (u ** 3)
        +
        p1 * (3 * u * u * t)
        +
        p2 * (3 * u * t * t)
        +
        p3 * (t ** 3)
    )


def get_bezier_points(spline):

    points = spline.bezier_points

    count = len(points)

    if count < 2:
        return []

    result = []

    if spline.use_cyclic_u:

        segments = count

    else:

        segments = count - 1

    for i in range(segments):

        p0 = points[i]

        if i + 1 < count:

            p3 = points[i + 1]

        else:

            p3 = points[0]

        p0_co = p0.co.copy()
        p3_co = p3.co.copy()

        p1_co = p0.handle_right.copy()
        p2_co = p3.handle_left.copy()

        samples = max(
            4,
            CURVE_SAMPLES // max(
                1,
                segments
            )
        )

        for s in range(samples):

            if i > 0 and s == 0:
                continue

            t = s / samples

            result.append(
                bezier_point(
                    p0_co,
                    p1_co,
                    p2_co,
                    p3_co,
                    t
                )
            )

    if not spline.use_cyclic_u:

        result.append(
            points[-1].co.copy()
        )

    return result


def get_curve_points(curve_obj):

    result = []

    curve = curve_obj.data

    for index, spline in enumerate(
        curve.splines
    ):

        try:

            if spline.type == "BEZIER":

                points = get_bezier_points(
                    spline
                )

            elif spline.type == "POLY":

                points = [
                    p.co.xyz.copy()
                    for p in spline.points
                ]

            elif spline.type == "NURBS":

                points = [
                    p.co.xyz.copy()
                    for p in spline.points
                ]

            else:

                print(
                    f"[SKIP] Spline {index}: "
                    f"{spline.type}"
                )

                continue

            if len(points) >= 2:

                result.append(
                    {
                        "index": index,
                        "points": points,
                        "cyclic": spline.use_cyclic_u
                    }
                )

        except Exception as e:

            print(
                f"[ERROR] Spline {index}: {e}"
            )

    return result


# ============================================================
# CURVE BOUNDS
# ============================================================

def get_curve_bounds(splines):

    min_x = float("inf")
    max_x = float("-inf")

    min_y = float("inf")
    max_y = float("-inf")

    for spline in splines:

        for co in spline["points"]:

            min_x = min(
                min_x,
                co.x
            )

            max_x = max(
                max_x,
                co.x
            )

            min_y = min(
                min_y,
                co.y
            )

            max_y = max(
                max_y,
                co.y
            )

    return (
        min_x,
        max_x,
        min_y,
        max_y
    )


# ============================================================
# NORMALIZE CURVE TO UV
# ============================================================

def normalize_curve_to_uv(
    splines,
    uv_bounds
):

    (
        curve_min_x,
        curve_max_x,
        curve_min_y,
        curve_max_y
    ) = get_curve_bounds(
        splines
    )

    (
        uv_min_u,
        uv_max_u,
        uv_min_v,
        uv_max_v
    ) = uv_bounds

    curve_width = (
        curve_max_x -
        curve_min_x
    )

    curve_height = (
        curve_max_y -
        curve_min_y
    )

    uv_width = (
        uv_max_u -
        uv_min_u
    )

    uv_height = (
        uv_max_v -
        uv_min_v
    )

    if abs(curve_width) < 1e-12:

        raise RuntimeError(
            "عرض الـ Curve = صفر."
        )

    if abs(curve_height) < 1e-12:

        raise RuntimeError(
            "ارتفاع الـ Curve = صفر."
        )

    if abs(uv_width) < 1e-12:

        raise RuntimeError(
            "عرض UV = صفر."
        )

    if abs(uv_height) < 1e-12:

        raise RuntimeError(
            "ارتفاع UV = صفر."
        )

    # --------------------------------------------------------
    # مساحة UV المتاحة بعد الهامش
    # --------------------------------------------------------

    target_min_u = (
        uv_min_u +
        uv_width * UV_MARGIN
    )

    target_max_u = (
        uv_max_u -
        uv_width * UV_MARGIN
    )

    target_min_v = (
        uv_min_v +
        uv_height * UV_MARGIN
    )

    target_max_v = (
        uv_max_v -
        uv_height * UV_MARGIN
    )

    target_width = (
        target_max_u -
        target_min_u
    )

    target_height = (
        target_max_v -
        target_min_v
    )

    # --------------------------------------------------------
    # Scale
    # --------------------------------------------------------

    scale_u = (
        target_width /
        curve_width
    )

    scale_v = (
        target_height /
        curve_height
    )

    if KEEP_ASPECT:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    # --------------------------------------------------------
    # الحجم النهائي
    # --------------------------------------------------------

    final_width = (
        curve_width *
        scale_u
    )

    final_height = (
        curve_height *
        scale_v
    )

    # --------------------------------------------------------
    # توسيط داخل UV
    # --------------------------------------------------------

    center_u = (
        target_min_u +
        target_max_u
    ) / 2.0

    center_v = (
        target_min_v +
        target_max_v
    ) / 2.0

    curve_center_x = (
        curve_min_x +
        curve_max_x
    ) / 2.0

    curve_center_y = (
        curve_min_y +
        curve_max_y
    ) / 2.0

    result = []

    for spline in splines:

        new_points = []

        for co in spline["points"]:

            u = (
                center_u +
                (co.x - curve_center_x)
                * scale_u
            )

            v = (
                center_v +
                (co.y - curve_center_y)
                * scale_v
            )

            new_points.append(
                (u, v)
            )

        result.append(
            {
                "index": spline["index"],
                "points": new_points,
                "cyclic": spline["cyclic"]
            }
        )

    return result


# ============================================================
# UV -> 3D
# ============================================================

def uv_to_position(
    uv_point,
    triangles
):

    best_distance = float("inf")
    best_triangle = None

    for tri in triangles:

        uv = tri["uv"]

        a = uv[0]
        b = uv[1]
        c = uv[2]

        weights = barycentric_2d(
            uv_point,
            a,
            b,
            c
        )

        if weights:

            w1, w2, w3 = weights

            if (
                w1 >= -UV_TOLERANCE and
                w2 >= -UV_TOLERANCE and
                w3 >= -UV_TOLERANCE
            ):

                return (
                    barycentric_3d(
                        weights,
                        tri["pos"][0],
                        tri["pos"][1],
                        tri["pos"][2]
                    ),
                    True
                )

        if USE_NEAREST_TRIANGLE:

            distance = triangle_distance(
                uv_point,
                a,
                b,
                c
            )

            if distance < best_distance:

                best_distance = distance
                best_triangle = tri

    if best_triangle is None:

        return None, False

    uv = best_triangle["uv"]
    pos = best_triangle["pos"]

    # --------------------------------------------------------
    # أقرب نقطة على أحد أضلاع المثلث
    # --------------------------------------------------------

    best_q = None
    best_d = float("inf")

    edges = [

        (uv[0], uv[1]),
        (uv[1], uv[2]),
        (uv[2], uv[0])

    ]

    for a, b in edges:

        ax, ay = a
        bx, by = b

        dx = bx - ax
        dy = by - ay

        length_sq = (
            dx * dx +
            dy * dy
        )

        if length_sq < 1e-15:

            q = a

        else:

            t = (
                (uv_point[0] - ax) * dx +
                (uv_point[1] - ay) * dy
            ) / length_sq

            t = max(
                0.0,
                min(1.0, t)
            )

            q = (
                ax + dx * t,
                ay + dy * t
            )

        d = math.hypot(
            uv_point[0] - q[0],
            uv_point[1] - q[1]
        )

        if d < best_d:

            best_d = d
            best_q = q

    weights = barycentric_2d(
        best_q,
        uv[0],
        uv[1],
        uv[2]
    )

    if weights is None:

        return None, False

    return (
        barycentric_3d(
            weights,
            pos[0],
            pos[1],
            pos[2]
        ),
        False
    )


# ============================================================
# CREATE OUTPUT
# ============================================================

def create_output(
    mesh_obj,
    mapped_splines
):

    curve_data = bpy.data.curves.new(
        OUTPUT_NAME,
        "CURVE"
    )

    curve_data.dimensions = "3D"

    curve_data.resolution_u = 12

    if BEVEL_DEPTH > 0:

        curve_data.bevel_depth = (
            BEVEL_DEPTH
        )

        curve_data.bevel_resolution = (
            BEVEL_RESOLUTION
        )

    output = bpy.data.objects.new(
        OUTPUT_NAME,
        curve_data
    )

    bpy.context.collection.objects.link(
        output
    )

    output.matrix_world = (
        mesh_obj.matrix_world.copy()
    )

    for data in mapped_splines:

        points = data["points"]

        if len(points) < 2:
            continue

        spline = curve_data.splines.new(
            "POLY"
        )

        spline.points.add(
            len(points) - 1
        )

        for i, co in enumerate(points):

            spline.points[i].co = (
                co.x,
                co.y,
                co.z,
                1.0
            )

        spline.use_cyclic_u = (
            data["cyclic"]
        )

    return output


# ============================================================
# MAIN
# ============================================================

def main():

    mesh_obj = None
    curve_obj = None

    for obj in bpy.context.selected_objects:

        if obj.type == "MESH":

            mesh_obj = obj

        elif obj.type == "CURVE":

            curve_obj = obj

    if mesh_obj is None:

        raise RuntimeError(
            "حدد Mesh يحتوي على UV."
        )

    if curve_obj is None:

        raise RuntimeError(
            "حدد Curve."
        )

    print("")
    print("=" * 70)
    print("UV CURVE PROJECT")
    print("=" * 70)

    print(
        "Mesh:",
        mesh_obj.name
    )

    print(
        "Curve:",
        curve_obj.name
    )

    # --------------------------------------------------------
    # Build UV
    # --------------------------------------------------------

    print(
        "جاري قراءة UV..."
    )

    triangles = build_uv_triangles(
        mesh_obj
    )

    print(
        "عدد UV triangles:",
        len(triangles)
    )

    if not triangles:

        raise RuntimeError(
            "لم يتم العثور على UV triangles."
        )

    uv_bounds = get_uv_bounds(
        triangles
    )

    print(
        "UV Bounds:",
        uv_bounds
    )

    # --------------------------------------------------------
    # Curve
    # --------------------------------------------------------

    print(
        "جاري قراءة Curve..."
    )

    source_splines = get_curve_points(
        curve_obj
    )

    print(
        "عدد Splines:",
        len(source_splines)
    )

    if not source_splines:

        raise RuntimeError(
            "Curve لا تحتوي على Splines."
        )

    curve_bounds = get_curve_bounds(
        source_splines
    )

    print(
        "Curve Bounds:",
        curve_bounds
    )

    # --------------------------------------------------------
    # Normalize
    # --------------------------------------------------------

    print(
        "جاري ضبط حجم Curve مع UV..."
    )

    normalized = normalize_curve_to_uv(
        source_splines,
        uv_bounds
    )

    # --------------------------------------------------------
    # UV -> 3D
    # --------------------------------------------------------

    mapped = []

    total = 0
    success = 0
    failed = 0

    print(
        "جاري إسقاط Curve على Mesh..."
    )

    for spline_data in normalized:

        spline_index = (
            spline_data["index"]
        )

        new_points = []

        for point_index, uv in enumerate(
            spline_data["points"]
        ):

            total += 1

            try:

                position, exact = (
                    uv_to_position(
                        uv,
                        triangles
                    )
                )

                if position is None:

                    failed += 1

                    print(
                        f"[FAIL] "
                        f"Spline={spline_index} "
                        f"Point={point_index} "
                        f"UV={uv}"
                    )

                    continue

                new_points.append(
                    position
                )

                success += 1

                if not exact:

                    print(
                        f"[WARNING] "
                        f"Spline={spline_index} "
                        f"Point={point_index} "
                        f"خارج UV"
                    )

            except Exception as e:

                failed += 1

                print(
                    f"[ERROR] "
                    f"Spline={spline_index} "
                    f"Point={point_index}: {e}"
                )

        if len(new_points) >= 2:

            mapped.append(
                {
                    "points": new_points,
                    "cyclic": spline_data["cyclic"]
                }
            )

    # --------------------------------------------------------
    # Delete old output
    # --------------------------------------------------------

    old = bpy.data.objects.get(
        OUTPUT_NAME
    )

    if old:

        bpy.data.objects.remove(
            old,
            do_unlink=True
        )

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    if not mapped:

        raise RuntimeError(
            "لم يتم إنشاء Curve."
        )

    output = create_output(
        mesh_obj,
        mapped
    )

    # --------------------------------------------------------
    # Select output
    # --------------------------------------------------------

    bpy.ops.object.select_all(
        action="DESELECT"
    )

    output.select_set(True)

    bpy.context.view_layer.objects.active = (
        output
    )

    # --------------------------------------------------------
    # Report
    # --------------------------------------------------------

    print("")
    print("=" * 70)
    print("اكتمل بنجاح")
    print("=" * 70)

    print(
        "Total:",
        total
    )

    print(
        "Success:",
        success
    )

    print(
        "Failed:",
        failed
    )

    print(
        "Output:",
        output.name
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

try:

    main()

except Exception as e:

    print("")
    print("=" * 70)
    print("SCRIPT FAILED")
    print("=" * 70)

    print(
        type(e).__name__,
        ":",
        str(e)
    )

    print("=" * 70)
