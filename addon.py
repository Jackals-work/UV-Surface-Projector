bl_info = {
    "name": "UV Surface Projector",
    "author": "Simple Code",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > UV Projector",
    "description": "Projects Curves and flat Mesh/Planes onto a Mesh using its UV map",
    "category": "Object",
}


import bpy
import math

from mathutils import Vector
from bpy.props import (
    PointerProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty,
)


# ============================================================
# CONSTANTS
# ============================================================

OUTPUT_COLLECTION_NAME = "UV_Projector_Results"


# ============================================================
# MATH
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


def point_segment_distance(p, a, b):

    px, py = p

    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    length_sq = dx * dx + dy * dy

    if length_sq < 1e-15:
        return math.hypot(px - ax, py - ay)

    t = (
        (px - ax) * dx +
        (py - ay) * dy
    ) / length_sq

    t = max(0.0, min(1.0, t))

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
        point_segment_distance(p, a, b),
        point_segment_distance(p, b, c),
        point_segment_distance(p, c, a),
    )


# ============================================================
# TARGET UV
# ============================================================

def build_uv_triangles(mesh_obj):

    mesh = mesh_obj.data

    if not mesh.uv_layers:
        raise RuntimeError(
            "Target Mesh does not contain a UV map."
        )

    uv_layer = mesh.uv_layers.active

    if uv_layer is None:
        raise RuntimeError(
            "No active UV map."
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

            uv_points.append(
                (
                    float(uv.x),
                    float(uv.y)
                )
            )

            vertex = mesh.vertices[
                loop.vertex_index
            ]

            positions.append(
                vertex.co.copy()
            )

        triangles.append({
            "uv": uv_points,
            "pos": positions
        })

    return triangles


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
# UV -> 3D
# ============================================================

def uv_to_position(
    uv_point,
    triangles,
    use_nearest=True
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
                w1 >= -0.000001 and
                w2 >= -0.000001 and
                w3 >= -0.000001
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

        if use_nearest:

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

    best_q = None
    best_d = float("inf")

    edges = [
        (uv[0], uv[1]),
        (uv[1], uv[2]),
        (uv[2], uv[0]),
    ]

    for a, b in edges:

        ax, ay = a
        bx, by = b

        dx = bx - ax
        dy = by - ay

        length_sq = dx * dx + dy * dy

        if length_sq < 1e-15:

            q = a

        else:

            t = (
                (uv_point[0] - ax) * dx +
                (uv_point[1] - ay) * dy
            ) / length_sq

            t = max(0.0, min(1.0, t))

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
# CURVE
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
        + p1 * (3 * u * u * t)
        + p2 * (3 * u * t * t)
        + p3 * (t ** 3)
    )


def sample_bezier(
    spline,
    samples
):

    points = spline.bezier_points

    count = len(points)

    if count < 2:
        return []

    result = []

    segments = (
        count
        if spline.use_cyclic_u
        else count - 1
    )

    samples_per_segment = max(
        4,
        samples // max(1, segments)
    )

    for i in range(segments):

        p0 = points[i]

        p3 = (
            points[i + 1]
            if i + 1 < count
            else points[0]
        )

        co0 = p0.co.copy()
        co3 = p3.co.copy()

        h1 = p0.handle_right.copy()
        h2 = p3.handle_left.copy()

        for s in range(samples_per_segment):

            if i > 0 and s == 0:
                continue

            t = s / samples_per_segment

            result.append(
                bezier_point(
                    co0,
                    h1,
                    h2,
                    co3,
                    t
                )
            )

    if not spline.use_cyclic_u:

        result.append(
            points[-1].co.copy()
        )

    return result


def get_curve_splines(
    obj,
    samples
):

    result = []

    curve = obj.data

    for index, spline in enumerate(
        curve.splines
    ):

        try:

            if spline.type == "BEZIER":

                points = sample_bezier(
                    spline,
                    samples
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

                continue

            if len(points) >= 2:

                result.append({
                    "index": index,
                    "points": points,
                    "cyclic": spline.use_cyclic_u
                })

        except Exception as e:

            print(
                f"[UV Projector] "
                f"Curve spline {index} failed: {e}"
            )

    return result


# ============================================================
# SOURCE BOUNDS
# ============================================================

def get_points_bounds(
    splines
):

    min_x = float("inf")
    max_x = float("-inf")

    min_y = float("inf")
    max_y = float("-inf")

    for spline in splines:

        for co in spline["points"]:

            min_x = min(min_x, co.x)
            max_x = max(max_x, co.x)

            min_y = min(min_y, co.y)
            max_y = max(max_y, co.y)

    return (
        min_x,
        max_x,
        min_y,
        max_y
    )


def normalize_points(
    splines,
    uv_bounds,
    keep_aspect,
    margin
):

    (
        source_min_x,
        source_max_x,
        source_min_y,
        source_max_y
    ) = get_points_bounds(splines)

    (
        uv_min_u,
        uv_max_u,
        uv_min_v,
        uv_max_v
    ) = uv_bounds

    source_width = (
        source_max_x -
        source_min_x
    )

    source_height = (
        source_max_y -
        source_min_y
    )

    if abs(source_width) < 1e-12:
        raise RuntimeError(
            "Source width is zero."
        )

    if abs(source_height) < 1e-12:
        raise RuntimeError(
            "Source height is zero."
        )

    uv_width = (
        uv_max_u -
        uv_min_u
    )

    uv_height = (
        uv_max_v -
        uv_min_v
    )

    target_min_u = (
        uv_min_u +
        uv_width * margin
    )

    target_max_u = (
        uv_max_u -
        uv_width * margin
    )

    target_min_v = (
        uv_min_v +
        uv_height * margin
    )

    target_max_v = (
        uv_max_v -
        uv_height * margin
    )

    target_width = (
        target_max_u -
        target_min_u
    )

    target_height = (
        target_max_v -
        target_min_v
    )

    scale_u = (
        target_width /
        source_width
    )

    scale_v = (
        target_height /
        source_height
    )

    if keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    source_center_x = (
        source_min_x +
        source_max_x
    ) / 2.0

    source_center_y = (
        source_min_y +
        source_max_y
    ) / 2.0

    target_center_u = (
        target_min_u +
        target_max_u
    ) / 2.0

    target_center_v = (
        target_min_v +
        target_max_v
    ) / 2.0

    result = []

    for spline in splines:

        new_points = []

        for co in spline["points"]:

            u = (
                target_center_u +
                (co.x - source_center_x)
                * scale_u
            )

            v = (
                target_center_v +
                (co.y - source_center_y)
                * scale_v
            )

            new_points.append(
                (u, v)
            )

        result.append({
            "index": spline["index"],
            "points": new_points,
            "cyclic": spline["cyclic"]
        })

    return result


# ============================================================
# COLLECTION
# ============================================================

def get_output_collection():

    collection = bpy.data.collections.get(
        OUTPUT_COLLECTION_NAME
    )

    if collection is None:

        collection = bpy.data.collections.new(
            OUTPUT_COLLECTION_NAME
        )

        bpy.context.scene.collection.children.link(
            collection
        )

    return collection


def move_to_collection(
    obj,
    collection
):

    for c in list(obj.users_collection):

        c.objects.unlink(obj)

    collection.objects.link(obj)


# ============================================================
# CREATE CURVE OUTPUT
# ============================================================

def create_curve_output(
    target,
    mapped,
    props,
    source_name
):

    curve_data = bpy.data.curves.new(
        f"UV_{source_name}",
        "CURVE"
    )

    curve_data.dimensions = "3D"

    curve_data.resolution_u = 12

    if props.bevel_depth > 0:

        curve_data.bevel_depth = (
            props.bevel_depth
        )

        curve_data.bevel_resolution = (
            props.bevel_resolution
        )

    output = bpy.data.objects.new(
        f"UV_{source_name}",
        curve_data
    )

    collection = get_output_collection()

    collection.objects.link(output)

    output.matrix_world = (
        target.matrix_world.copy()
    )

    for data in mapped:

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
# CREATE MESH OUTPUT FROM PLANE
# ============================================================

def create_plane_output(
    target,
    source,
    props
):

    mesh = source.data

    if not mesh.vertices:
        raise RuntimeError(
            "Source mesh has no vertices."
        )

    # --------------------------------------------------------
    # Source vertices
    # --------------------------------------------------------

    source_points = []

    for v in mesh.vertices:

        co = source.matrix_world @ v.co

        source_points.append(
            co.copy()
        )

    min_x = min(
        p.x for p in source_points
    )

    max_x = max(
        p.x for p in source_points
    )

    min_y = min(
        p.y for p in source_points
    )

    max_y = max(
        p.y for p in source_points
    )

    width = max_x - min_x
    height = max_y - min_y

    if width < 1e-12:
        raise RuntimeError(
            "Plane width is zero."
        )

    if height < 1e-12:
        raise RuntimeError(
            "Plane height is zero."
        )

    # --------------------------------------------------------
    # Target UV
    # --------------------------------------------------------

    triangles = build_uv_triangles(
        target
    )

    uv_bounds = get_uv_bounds(
        triangles
    )

    (
        uv_min_u,
        uv_max_u,
        uv_min_v,
        uv_max_v
    ) = uv_bounds

    uv_width = uv_max_u - uv_min_u
    uv_height = uv_max_v - uv_min_v

    target_min_u = (
        uv_min_u +
        uv_width * props.uv_margin
    )

    target_max_u = (
        uv_max_u -
        uv_width * props.uv_margin
    )

    target_min_v = (
        uv_min_v +
        uv_height * props.uv_margin
    )

    target_max_v = (
        uv_max_v -
        uv_height * props.uv_margin
    )

    target_width = (
        target_max_u -
        target_min_u
    )

    target_height = (
        target_max_v -
        target_min_v
    )

    scale_u = target_width / width
    scale_v = target_height / height

    if props.keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    center_x = (
        min_x + max_x
    ) / 2.0

    center_y = (
        min_y + max_y
    ) / 2.0

    center_u = (
        target_min_u +
        target_max_u
    ) / 2.0

    center_v = (
        target_min_v +
        target_max_v
    ) / 2.0

    # --------------------------------------------------------
    # Map vertices
    # --------------------------------------------------------

    new_vertices = []

    failed = 0

    for p in source_points:

        u = (
            center_u +
            (p.x - center_x)
            * scale_u
        )

        v = (
            center_v +
            (p.y - center_y)
            * scale_v
        )

        if props.flip_v:

            v = 1.0 - v

        position, exact = uv_to_position(
            (u, v),
            triangles,
            props.use_nearest
        )

        if position is None:

            failed += 1

            new_vertices.append(
                (0, 0, 0)
            )

        else:

            new_vertices.append(
                tuple(position)
            )

    # --------------------------------------------------------
    # Faces
    # --------------------------------------------------------

    new_faces = []

    for poly in mesh.polygons:

        verts = list(poly.vertices)

        if len(verts) >= 3:

            new_faces.append(
                verts
            )

    # --------------------------------------------------------
    # Create
    # --------------------------------------------------------

    new_mesh = bpy.data.meshes.new(
        f"UV_{source.name}"
    )

    new_mesh.from_pydata(
        new_vertices,
        [],
        new_faces
    )

    new_mesh.update()

    output = bpy.data.objects.new(
        f"UV_{source.name}",
        new_mesh
    )

    collection = get_output_collection()

    collection.objects.link(output)

    output.matrix_world = (
        target.matrix_world.copy()
    )

    return output, failed


# ============================================================
# PROPERTIES
# ============================================================

class UVProjectorProperties(
    bpy.types.PropertyGroup
):

    target: PointerProperty(
        name="Target Mesh",
        type=bpy.types.Object
    )

    flip_v: BoolProperty(
        name="Flip V",
        default=False
    )

    keep_aspect: BoolProperty(
        name="Keep Aspect Ratio",
        default=True
    )

    uv_margin: FloatProperty(
        name="UV Margin",
        default=0.0,
        min=0.0,
        max=0.45
    )

    use_nearest: BoolProperty(
        name="Nearest Triangle",
        default=True
    )

    curve_samples: IntProperty(
        name="Curve Samples",
        default=100,
        min=4,
        max=5000
    )

    bevel_depth: FloatProperty(
        name="Bevel Depth",
        default=0.0,
        min=0.0
    )

    bevel_resolution: IntProperty(
        name="Bevel Resolution",
        default=3,
        min=0,
        max=16
    )

    source_type: EnumProperty(
        name="Source Type",
        items=[
            (
                "AUTO",
                "Auto",
                "Use selected Curve or Mesh"
            ),
            (
                "CURVE",
                "Curve",
                "Use selected Curves"
            ),
            (
                "PLANE",
                "Plane / Mesh",
                "Use selected Mesh objects"
            ),
        ],
        default="AUTO"
    )


# ============================================================
# OPERATOR
# ============================================================

class UVPROJECTOR_OT_project(
    bpy.types.Operator
):

    bl_idname = "uv_projector.project"

    bl_label = "Project to UV Surface"

    bl_description = (
        "Project selected Curves and Planes "
        "onto the Target Mesh using UV"
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(self, context):

        props = context.scene.uv_projector

        target = props.target

        if target is None:

            self.report(
                {"ERROR"},
                "اختر Target Mesh"
            )

            return {"CANCELLED"}

        if target.type != "MESH":

            self.report(
                {"ERROR"},
                "Target يجب أن يكون Mesh"
            )

            return {"CANCELLED"}

        if not target.data.uv_layers:

            self.report(
                {"ERROR"},
                "Target Mesh لا يحتوي على UV"
            )

            return {"CANCELLED"}

        # ----------------------------------------------------
        # Target triangles
        # ----------------------------------------------------

        try:

            triangles = build_uv_triangles(
                target
            )

            uv_bounds = get_uv_bounds(
                triangles
            )

        except Exception as e:

            self.report(
                {"ERROR"},
                str(e)
            )

            return {"CANCELLED"}

        # ----------------------------------------------------
        # Sources
        # ----------------------------------------------------

        sources = []

        for obj in context.selected_objects:

            if obj == target:
                continue

            if props.source_type == "CURVE":

                if obj.type == "CURVE":
                    sources.append(obj)

            elif props.source_type == "PLANE":

                if obj.type == "MESH":
                    sources.append(obj)

            else:

                if obj.type in {
                    "CURVE",
                    "MESH"
                }:

                    sources.append(obj)

        if not sources:

            self.report(
                {"ERROR"},
                "حدد Curve أو Plane/Mesh مع Target"
            )

            return {"CANCELLED"}

        success = 0
        failed = 0

        print("")
        print("=" * 70)
        print("UV SURFACE PROJECTOR")
        print("=" * 70)

        print(
            "Target:",
            target.name
        )

        for source in sources:

            print(
                f"\nProcessing: {source.name}"
            )

            try:

                # ==========================================
                # CURVE
                # ==========================================

                if source.type == "CURVE":

                    splines = get_curve_splines(
                        source,
                        props.curve_samples
                    )

                    if not splines:

                        raise RuntimeError(
                            "Curve has no valid splines."
                        )

                    normalized = normalize_points(
                        splines,
                        uv_bounds,
                        props.keep_aspect,
                        props.uv_margin
                    )

                    mapped = []

                    for spline in normalized:

                        output_points = []

                        for uv in spline["points"]:

                            u, v = uv

                            if props.flip_v:

                                v = 1.0 - v

                            position, exact = (
                                uv_to_position(
                                    (u, v),
                                    triangles,
                                    props.use_nearest
                                )
                            )

                            if position is not None:

                                output_points.append(
                                    position
                                )

                            else:

                                failed += 1

                        if len(output_points) >= 2:

                            mapped.append({
                                "points": output_points,
                                "cyclic": spline["cyclic"]
                            })

                    if not mapped:

                        raise RuntimeError(
                            "No points could be projected."
                        )

                    output = create_curve_output(
                        target,
                        mapped,
                        props,
                        source.name
                    )

                    success += 1

                    print(
                        f"[OK] Curve -> {output.name}"
                    )

                # ==========================================
                # MESH / PLANE
                # ==========================================

                elif source.type == "MESH":

                    output, mesh_failed = (
                        create_plane_output(
                            target,
                            source,
                            props
                        )
                    )

                    failed += mesh_failed

                    success += 1

                    print(
                        f"[OK] Mesh -> {output.name}"
                    )

            except Exception as e:

                failed += 1

                print(
                    f"[FAILED] {source.name}: {e}"
                )

                continue

        # ----------------------------------------------------
        # Finish
        # ----------------------------------------------------

        print("")
        print("=" * 70)

        print(
            "Finished"
        )

        print(
            "Successful:",
            success
        )

        print(
            "Failed points:",
            failed
        )

        print("=" * 70)

        self.report(
            {"INFO"},
            f"تمت المعالجة: {success} عنصر"
        )

        return {"FINISHED"}


# ============================================================
# CLEAR OUTPUT
# ============================================================

class UVPROJECTOR_OT_clear(
    bpy.types.Operator
):

    bl_idname = "uv_projector.clear"

    bl_label = "Clear Results"

    bl_description = (
        "Delete all UV Projector results"
    )

    def execute(self, context):

        collection = bpy.data.collections.get(
            OUTPUT_COLLECTION_NAME
        )

        if collection is None:

            self.report(
                {"INFO"},
                "لا توجد نتائج"
            )

            return {"FINISHED"}

        objects = list(
            collection.objects
        )

        for obj in objects:

            bpy.data.objects.remove(
                obj,
                do_unlink=True
            )

        self.report(
            {"INFO"},
            "تم حذف النتائج"
        )

        return {"FINISHED"}


# ============================================================
# PANEL
# ============================================================

class UVPROJECTOR_PT_panel(
    bpy.types.Panel
):

    bl_label = "UV Surface Projector"

    bl_idname = "UVPROJECTOR_PT_panel"

    bl_space_type = "VIEW_3D"

    bl_region_type = "UI"

    bl_category = "UV Projector"

    def draw(self, context):

        layout = self.layout

        props = context.scene.uv_projector

        # ----------------------------------------------------
        # Target
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Target Surface",
            icon="MESH_DATA"
        )

        box.prop(
            props,
            "target"
        )

        # ----------------------------------------------------
        # Source
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Source",
            icon="OBJECT_DATA"
        )

        box.prop(
            props,
            "source_type",
            expand=True
        )

        box.label(
            text=(
                "حدد Curve أو Plane/Mesh "
                "مع الـ Target"
            )
        )

        # ----------------------------------------------------
        # UV
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="UV Settings",
            icon="UV"
        )

        box.prop(
            props,
            "keep_aspect"
        )

        box.prop(
            props,
            "flip_v"
        )

        box.prop(
            props,
            "uv_margin"
        )

        box.prop(
            props,
            "use_nearest"
        )

        # ----------------------------------------------------
        # Curve
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Curve Settings",
            icon="CURVE_DATA"
        )

        box.prop(
            props,
            "curve_samples"
        )

        box.prop(
            props,
            "bevel_depth"
        )

        box.prop(
            props,
            "bevel_resolution"
        )

        # ----------------------------------------------------
        # Buttons
        # ----------------------------------------------------

        layout.separator()

        row = layout.row()

        row.scale_y = 1.5

        row.operator(
            "uv_projector.project",
            icon="MOD_SHRINKWRAP"
        )

        row = layout.row()

        row.operator(
            "uv_projector.clear",
            icon="TRASH"
        )


# ============================================================
# REGISTER
# ============================================================

classes = (
    UVProjectorProperties,
    UVPROJECTOR_OT_project,
    UVPROJECTOR_OT_clear,
    UVPROJECTOR_PT_panel,
)


def register():

    for cls in classes:

        bpy.utils.register_class(cls)

    bpy.types.Scene.uv_projector = (
        PointerProperty(
            type=UVProjectorProperties
        )
    )


def unregister():

    del bpy.types.Scene.uv_projector

    for cls in reversed(classes):

        bpy.utils.unregister_class(cls)


if __name__ == "__main__":

    register()
