
bl_info = {
    "name": "UV Surface Projector Pro",
    "author": "Simple Code",
    "version": (2, 4, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > UV Projector",
    "description": (
        "Projects and cuts Curves and Mesh/Planes onto a UV-mapped "
        "target with accurate UV flat comparison"
    ),
    "category": "Object",
}


import bpy
import math
import traceback
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
UV_FLAT_COLLECTION_NAME = "UV_Flat_Comparison"


# ============================================================
# COLLECTION HELPERS
# ============================================================

def get_output_collection():
    col = bpy.data.collections.get(
        OUTPUT_COLLECTION_NAME
    )

    if col is None:
        col = bpy.data.collections.new(
            OUTPUT_COLLECTION_NAME
        )

        bpy.context.scene.collection.children.link(col)

    return col


def get_uv_flat_collection():
    col = bpy.data.collections.get(
        UV_FLAT_COLLECTION_NAME
    )

    if col is None:
        col = bpy.data.collections.new(
            UV_FLAT_COLLECTION_NAME
        )

        bpy.context.scene.collection.children.link(col)

    return col


def clear_collection_objects(collection_name):
    col = bpy.data.collections.get(collection_name)

    if not col:
        return

    for obj in list(col.objects):
        bpy.data.objects.remove(
            obj,
            do_unlink=True
        )


# ============================================================
# GEOMETRY HELPERS
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
        v2y * v1x
    ) * inv

    w3 = (
        v0x * v2y -
        v0y * v2x
    ) * inv

    w1 = 1.0 - w2 - w3

    return (
        w1,
        w2,
        w3
    )


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

    length_sq = (
        dx * dx +
        dy * dy
    )

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
        if all(
            w >= 0
            for w in bary
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
        ),
    )


# ============================================================
# UV TRIANGLES
# ============================================================

def build_uv_triangles(
    obj,
    flip_v=False
):
    mesh = obj.data

    if not mesh.uv_layers:
        raise RuntimeError(
            "Target Mesh لا يحتوي على UV."
        )

    uv_layer = mesh.uv_layers.active

    if uv_layer is None:
        raise RuntimeError(
            "لا يوجد Active UV Layer."
        )

    mesh.calc_loop_triangles()

    triangles = []

    for tri in mesh.loop_triangles:

        if len(tri.loops) != 3:
            continue

        uv = []
        pos = []

        for loop_index in tri.loops:

            uv_value = (
                uv_layer.data[
                    loop_index
                ].uv
            )

            u = float(
                uv_value.x
            )

            v = float(
                uv_value.y
            )

            if flip_v:
                v = 1.0 - v

            uv.append(
                (u, v)
            )

            vertex_index = (
                mesh.loops[
                    loop_index
                ].vertex_index
            )

            pos.append(
                mesh.vertices[
                    vertex_index
                ].co.copy()
            )

        triangles.append({
            "uv": uv,
            "pos": pos,
        })

    if not triangles:
        raise RuntimeError(
            "لم يتم العثور على مثلثات UV."
        )

    return triangles


def get_uv_bounds(triangles):
    values = [
        (u, v)
        for tri in triangles
        for u, v in tri["uv"]
    ]

    if not values:
        raise RuntimeError(
            "لم يتم العثور على بيانات UV."
        )

    us = [
        value[0]
        for value in values
    ]

    vs = [
        value[1]
        for value in values
    ]

    return (
        min(us),
        max(us),
        min(vs),
        max(vs),
    )


# ============================================================
# UV -> SURFACE
# ============================================================

def uv_to_position(
    uv_point,
    triangles,
    nearest=True
):
    best_distance = float("inf")
    best_triangle = None

    for tri in triangles:

        a, b, c = tri["uv"]

        weights = barycentric_2d(
            uv_point,
            a,
            b,
            c
        )

        if weights:

            if all(
                w >= -1e-7
                for w in weights
            ):
                return (
                    barycentric_3d(
                        weights,
                        tri["pos"][0],
                        tri["pos"][1],
                        tri["pos"][2],
                    ),
                    True,
                )

        if nearest:

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
    best_distance = float("inf")

    edges = (
        (uv[0], uv[1]),
        (uv[1], uv[2]),
        (uv[2], uv[0]),
    )

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

        distance = math.hypot(
            uv_point[0] - q[0],
            uv_point[1] - q[1]
        )

        if distance < best_distance:

            best_distance = distance
            best_q = q

    if best_q is None:
        return None, False

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
            pos[2],
        ),
        False,
    )


def uv_point_inside(
    point,
    triangles,
    tolerance=1e-8
):
    for tri in triangles:

        weights = barycentric_2d(
            point,
            tri["uv"][0],
            tri["uv"][1],
            tri["uv"][2],
        )

        if weights:

            if all(
                value >= -tolerance
                for value in weights
            ):
                return True

    return False


# ============================================================
# UV MARGIN
# ============================================================

def estimate_uv_margin(
    props,
    uv_bounds
):
    min_u, max_u, min_v, max_v = uv_bounds

    uv_width = max_u - min_u
    uv_height = max_v - min_v

    if props.margin_mode == "UV":

        margin = max(
            0.0,
            props.margin_value
        )

        return (
            margin,
            margin
        )

    if props.margin_mode == "PERCENT":

        percentage = (
            max(
                0.0,
                props.margin_value
            ) / 100.0
        )

        return (
            uv_width * percentage,
            uv_height * percentage
        )

    # MM

    target = props.target

    if target is None:
        return 0.0, 0.0

    dimensions = target.dimensions

    world_width = max(
        abs(dimensions.x),
        1e-9
    )

    world_height = max(
        abs(dimensions.y),
        1e-9
    )

    millimeters = (
        max(
            0.0,
            props.margin_value
        ) / 1000.0
    )

    return (
        uv_width * (
            millimeters /
            world_width
        ),
        uv_height * (
            millimeters /
            world_height
        ),
    )


def clip_uv_to_bounds(
    point,
    bounds,
    margin_u,
    margin_v
):
    min_u, max_u, min_v, max_v = bounds

    return (
        min_u + margin_u <= point[0] <= max_u - margin_u
        and
        min_v + margin_v <= point[1] <= max_v - margin_v
    )


# ============================================================
# CURVE SAMPLING
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
        p1 * (3.0 * u * u * t)
        +
        p2 * (3.0 * u * t * t)
        +
        p3 * (t ** 3)
    )


def sample_curve(
    obj,
    samples
):
    result = []

    for spline_index, spline in enumerate(
        obj.data.splines
    ):

        try:

            points = []

            if spline.type == "BEZIER":

                bezier_points = (
                    spline.bezier_points
                )

                count = len(
                    bezier_points
                )

                if count < 2:
                    continue

                segments = (
                    count
                    if spline.use_cyclic_u
                    else count - 1
                )

                per_segment = max(
                    4,
                    samples //
                    max(1, segments)
                )

                for i in range(segments):

                    p0 = bezier_points[i]

                    p3 = bezier_points[
                        (i + 1) % count
                    ]

                    for s in range(
                        per_segment
                    ):

                        if (
                            i > 0
                            and s == 0
                        ):
                            continue

                        t = (
                            s /
                            per_segment
                        )

                        points.append(
                            bezier_point(
                                p0.co.copy(),
                                p0.handle_right.copy(),
                                p3.handle_left.copy(),
                                p3.co.copy(),
                                t,
                            )
                        )

                if not spline.use_cyclic_u:

                    points.append(
                        bezier_points[
                            -1
                        ].co.copy()
                    )

            elif spline.type in {
                "POLY",
                "NURBS",
            }:

                points = [
                    p.co.xyz.copy()
                    for p in spline.points
                ]

            if len(points) >= 2:

                result.append({
                    "index": spline_index,
                    "points": points,
                    "cyclic": spline.use_cyclic_u,
                })

        except Exception as exc:

            print(
                f"[UV Projector] "
                f"Curve spline {spline_index} failed: "
                f"{exc}"
            )

    return result


def source_bounds(splines):

    points = [
        point
        for spline in splines
        for point in spline["points"]
    ]

    if not points:
        raise RuntimeError(
            "المصدر لا يحتوي نقاطًا."
        )

    return (
        min(p.x for p in points),
        max(p.x for p in points),
        min(p.y for p in points),
        max(p.y for p in points),
    )


def normalize_source_to_uv(
    splines,
    uv_bounds,
    props
):
    sx0, sx1, sy0, sy1 = (
        source_bounds(splines)
    )

    ux0, ux1, uy0, uy1 = uv_bounds

    margin_u, margin_v = (
        estimate_uv_margin(
            props,
            uv_bounds
        )
    )

    tx0 = ux0 + margin_u
    tx1 = ux1 - margin_u

    ty0 = uy0 + margin_v
    ty1 = uy1 - margin_v

    if tx1 <= tx0 or ty1 <= ty0:
        raise RuntimeError(
            "الهامش أكبر من مساحة UV."
        )

    source_width = sx1 - sx0
    source_height = sy1 - sy0

    if (
        abs(source_width) < 1e-12
        or
        abs(source_height) < 1e-12
    ):
        raise RuntimeError(
            "عرض أو ارتفاع المصدر يساوي صفرًا."
        )

    scale_u = (
        tx1 - tx0
    ) / source_width

    scale_v = (
        ty1 - ty0
    ) / source_height

    if props.keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    source_center_x = (
        sx0 + sx1
    ) / 2.0

    source_center_y = (
        sy0 + sy1
    ) / 2.0

    target_center_u = (
        tx0 + tx1
    ) / 2.0

    target_center_v = (
        ty0 + ty1
    ) / 2.0

    result = []

    for spline in splines:

        uv_points = []

        for point in spline["points"]:

            uv_points.append((
                target_center_u
                +
                (
                    point.x -
                    source_center_x
                ) * scale_u,

                target_center_v
                +
                (
                    point.y -
                    source_center_y
                ) * scale_v,
            ))

        result.append({
            "points": uv_points,
            "cyclic": spline["cyclic"],
            "index": spline["index"],
        })

    return result


# ============================================================
# MESH CUT
# ============================================================

def cut_mesh_with_uv_improved(
    target,
    source,
    props,
    triangles,
    uv_bounds
):
    """
    Project source mesh vertices to target surface
    using the target UV.

    Invalid faces are removed.
    """

    src = source.data

    margin_u, margin_v = (
        estimate_uv_margin(
            props,
            uv_bounds
        )
    )

    world_matrix = (
        source.matrix_world
    )

    world_points = [
        world_matrix @ vertex.co
        for vertex in src.vertices
    ]

    if not world_points:
        raise RuntimeError(
            "Source mesh has no vertices."
        )

    sx0 = min(
        point.x
        for point in world_points
    )

    sx1 = max(
        point.x
        for point in world_points
    )

    sy0 = min(
        point.y
        for point in world_points
    )

    sy1 = max(
        point.y
        for point in world_points
    )

    source_width = sx1 - sx0
    source_height = sy1 - sy0

    if (
        source_width < 1e-12
        or
        source_height < 1e-12
    ):
        raise RuntimeError(
            "Mesh/Plane must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + margin_u
    tx1 = ux1 - margin_u

    ty0 = uy0 + margin_v
    ty1 = uy1 - margin_v

    scale_u = (
        tx1 - tx0
    ) / source_width

    scale_v = (
        ty1 - ty0
    ) / source_height

    if props.keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    source_center_x = (
        sx0 + sx1
    ) / 2.0

    source_center_y = (
        sy0 + sy1
    ) / 2.0

    target_center_u = (
        tx0 + tx1
    ) / 2.0

    target_center_v = (
        ty0 + ty1
    ) / 2.0

    new_positions = []
    vertex_valid = []

    for point in world_points:

        u = (
            target_center_u
            +
            (
                point.x -
                source_center_x
            ) * scale_u
        )

        v = (
            target_center_v
            +
            (
                point.y -
                source_center_y
            ) * scale_v
        )

        if props.flip_v:
            v = 1.0 - v

        uv = (u, v)

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                uv,
                triangles
            )

        inside = (
            inside
            and
            clip_uv_to_bounds(
                uv,
                uv_bounds,
                margin_u,
                margin_v
            )
        )

        position = None

        if inside:

            position, _ = uv_to_position(
                uv,
                triangles,
                props.use_nearest
            )

        if position is None:

            vertex_valid.append(False)

            new_positions.append(
                Vector((0.0, 0.0, 0.0))
            )

        else:

            vertex_valid.append(True)

            new_positions.append(
                position
            )

    face_valid = []

    for polygon in src.polygons:

        vertices = list(
            polygon.vertices
        )

        valid = (
            len(vertices) >= 3
            and
            all(
                vertex_valid[index]
                for index in vertices
            )
        )

        face_valid.append(valid)

    if not any(face_valid):
        raise RuntimeError(
            "No faces remain inside UV area. "
            "Try reducing margin or increasing "
            "source mesh subdivision."
        )

    import bmesh

    bm = bmesh.new()

    try:

        bm.from_mesh(src)

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for index, position in enumerate(
            new_positions
        ):

            if (
                vertex_valid[index]
                and
                index < len(bm.verts)
            ):

                bm.verts[index].co = position

        invalid_vertex_indices = {
            index
            for index, valid
            in enumerate(vertex_valid)
            if not valid
        }

        faces_to_delete = []

        for face in bm.faces:

            delete_face = False

            for vertex in face.verts:

                if vertex.index in (
                    invalid_vertex_indices
                ):

                    delete_face = True
                    break

            if delete_face:
                faces_to_delete.append(
                    face
                )

        if faces_to_delete:

            bmesh.ops.delete(
                bm,
                geom=faces_to_delete,
                context="FACES"
            )

        bm.verts.ensure_lookup_table()

        invalid_vertices = [
            vertex
            for vertex in bm.verts
            if vertex.index in invalid_vertex_indices
        ]

        if invalid_vertices:

            bmesh.ops.delete(
                bm,
                geom=invalid_vertices,
                context="VERTS"
            )

        bm.to_mesh(src)
        src.update()

    finally:

        bm.free()

    return source


def cut_mesh_with_uv_for_curve_improved(
    target,
    source,
    props,
    triangles,
    uv_bounds
):
    """
    Uses the source curve converted to temporary mesh
    as the projection area.
    """

    src = source.data

    margin_u, margin_v = (
        estimate_uv_margin(
            props,
            uv_bounds
        )
    )

    world_matrix = (
        source.matrix_world
    )

    world_points = [
        world_matrix @ vertex.co
        for vertex in src.vertices
    ]

    if not world_points:
        raise RuntimeError(
            "Curve mesh has no vertices."
        )

    sx0 = min(
        point.x
        for point in world_points
    )

    sx1 = max(
        point.x
        for point in world_points
    )

    sy0 = min(
        point.y
        for point in world_points
    )

    sy1 = max(
        point.y
        for point in world_points
    )

    source_width = sx1 - sx0
    source_height = sy1 - sy0

    if (
        source_width < 1e-12
        or
        source_height < 1e-12
    ):
        raise RuntimeError(
            "Curve must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + margin_u
    tx1 = ux1 - margin_u

    ty0 = uy0 + margin_v
    ty1 = uy1 - margin_v

    scale_u = (
        tx1 - tx0
    ) / source_width

    scale_v = (
        ty1 - ty0
    ) / source_height

    if props.keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    source_center_x = (
        sx0 + sx1
    ) / 2.0

    source_center_y = (
        sy0 + sy1
    ) / 2.0

    target_center_u = (
        tx0 + tx1
    ) / 2.0

    target_center_v = (
        ty0 + ty1
    ) / 2.0

    target_mesh = target.data

    target_world_points = [
        target.matrix_world @ vertex.co
        for vertex in target_mesh.vertices
    ]

    vertex_valid = []
    new_positions = []

    for point in target_world_points:

        u = (
            target_center_u
            +
            (
                point.x -
                source_center_x
            ) * scale_u
        )

        v = (
            target_center_v
            +
            (
                point.y -
                source_center_y
            ) * scale_v
        )

        if props.flip_v:
            v = 1.0 - v

        uv = (u, v)

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                uv,
                triangles
            )

        inside = (
            inside
            and
            clip_uv_to_bounds(
                uv,
                uv_bounds,
                margin_u,
                margin_v
            )
        )

        position = None

        if inside:

            position, _ = uv_to_position(
                uv,
                triangles,
                props.use_nearest
            )

        if position is None:

            vertex_valid.append(False)

            new_positions.append(
                Vector((0.0, 0.0, 0.0))
            )

        else:

            vertex_valid.append(True)

            new_positions.append(
                position
            )

    face_valid = []

    for polygon in target_mesh.polygons:

        vertices = list(
            polygon.vertices
        )

        valid = (
            len(vertices) >= 3
            and
            all(
                vertex_valid[index]
                for index in vertices
            )
        )

        face_valid.append(valid)

    if not any(face_valid):

        raise RuntimeError(
            "No faces of target remain "
            "inside UV area."
        )

    import bmesh

    bm = bmesh.new()

    try:

        bm.from_mesh(target_mesh)

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        for index, position in enumerate(
            new_positions
        ):

            if (
                vertex_valid[index]
                and
                index < len(bm.verts)
            ):

                bm.verts[index].co = position

        invalid_indices = {
            index
            for index, valid
            in enumerate(vertex_valid)
            if not valid
        }

        faces_to_delete = []

        for face in bm.faces:

            if any(
                vertex.index in invalid_indices
                for vertex in face.verts
            ):

                faces_to_delete.append(
                    face
                )

        if faces_to_delete:

            bmesh.ops.delete(
                bm,
                geom=faces_to_delete,
                context="FACES"
            )

        bm.verts.ensure_lookup_table()

        invalid_vertices = [
            vertex
            for vertex in bm.verts
            if vertex.index in invalid_indices
        ]

        if invalid_vertices:

            bmesh.ops.delete(
                bm,
                geom=invalid_vertices,
                context="VERTS"
            )

        bm.to_mesh(target_mesh)
        target_mesh.update()

    finally:

        bm.free()

    return target


def curve_to_mesh_and_cut_improved(
    target,
    curve_obj,
    props,
    triangles,
    uv_bounds
):
    """
    Convert Curve to temporary mesh and process it.
    """

    temp_mesh = None
    temp_obj = None

    try:

        depsgraph = (
            bpy.context
            .evaluated_depsgraph_get()
        )

        evaluated_curve = (
            curve_obj.evaluated_get(
                depsgraph
            )
        )

        temp_mesh = bpy.data.meshes.new_from_object(
            evaluated_curve,
            preserve_all_data_layers=False,
            depsgraph=depsgraph
        )

        if temp_mesh is None:
            raise RuntimeError(
                "Could not convert Curve to Mesh."
            )

        temp_obj = bpy.data.objects.new(
            "_temp_curve_mesh",
            temp_mesh
        )

        temp_obj.matrix_world = (
            curve_obj.matrix_world.copy()
        )

        bpy.context.collection.objects.link(
            temp_obj
        )

        result = (
            cut_mesh_with_uv_for_curve_improved(
                target,
                temp_obj,
                props,
                triangles,
                uv_bounds
            )
        )

        return result

    except Exception as exc:

        raise RuntimeError(
            f"Failed to cut with Curve: {exc}"
        )

    finally:

        if temp_obj is not None:

            bpy.data.objects.remove(
                temp_obj,
                do_unlink=True
            )

        elif temp_mesh is not None:

            if temp_mesh.users == 0:

                bpy.data.meshes.remove(
                    temp_mesh
                )


# ============================================================
# UV FLAT
# ============================================================

def create_uv_flat_mesh(
    target,
    offset_z=0.01,
    margin=0.0,
    fit_to_object=True,
    preserve_aspect=True,
):
    """
    Create an accurate flat representation
    of the target active UV map.

    IMPORTANT:
    UV coordinates are stored PER LOOP.

    This preserves UV seams correctly.

    The old implementation averaged UVs per
    vertex. That caused UV seams to collapse.

    This implementation creates one vertex
    for every mesh loop.
    """

    if target is None:

        raise RuntimeError(
            "Target object is None."
        )

    if target.type != "MESH":

        raise RuntimeError(
            f"Target '{target.name}' "
            f"is not a Mesh."
        )

    mesh = target.data

    if not mesh.uv_layers:

        raise RuntimeError(
            "Target has no UV layers."
        )

    uv_layer = mesh.uv_layers.active

    if uv_layer is None:

        raise RuntimeError(
            "Target has no active UV layer."
        )

    if len(mesh.loops) == 0:

        raise RuntimeError(
            "Target mesh has no loops."
        )

    # --------------------------------------------------------
    # READ UV PER LOOP
    # --------------------------------------------------------

    loop_uv = []

    min_u = float("inf")
    max_u = float("-inf")

    min_v = float("inf")
    max_v = float("-inf")

    for loop_index in range(
        len(mesh.loops)
    ):

        uv = (
            uv_layer.data[
                loop_index
            ].uv
        )

        u = float(uv.x)
        v = float(uv.y)

        loop_uv.append(
            Vector((u, v))
        )

        min_u = min(
            min_u,
            u
        )

        max_u = max(
            max_u,
            u
        )

        min_v = min(
            min_v,
            v
        )

        max_v = max(
            max_v,
            v
        )

    # --------------------------------------------------------
    # UV SIZE
    # --------------------------------------------------------

    uv_width = (
        max_u - min_u
    )

    uv_height = (
        max_v - min_v
    )

    if uv_width <= 1e-10:

        raise RuntimeError(
            "UV width is zero."
        )

    if uv_height <= 1e-10:

        raise RuntimeError(
            "UV height is zero."
        )

    uv_center_u = (
        min_u + max_u
    ) * 0.5

    uv_center_v = (
        min_v + max_v
    ) * 0.5

    # --------------------------------------------------------
    # LOCAL TARGET BOUNDING BOX
    #
    # Rotation does not affect this calculation.
    # --------------------------------------------------------

    bbox = [
        Vector(corner)
        for corner in target.bound_box
    ]

    min_x = min(
        point.x
        for point in bbox
    )

    max_x = max(
        point.x
        for point in bbox
    )

    min_y = min(
        point.y
        for point in bbox
    )

    max_y = max(
        point.y
        for point in bbox
    )

    object_width = max(
        max_x - min_x,
        1e-10
    )

    object_height = max(
        max_y - min_y,
        1e-10
    )

    # --------------------------------------------------------
    # SCALE
    # --------------------------------------------------------

    if fit_to_object:

        scale_x = (
            object_width /
            uv_width
        )

        scale_y = (
            object_height /
            uv_height
        )

        if preserve_aspect:

            uniform_scale = min(
                scale_x,
                scale_y
            )

            scale_x = (
                uniform_scale
            )

            scale_y = (
                uniform_scale
            )

    else:

        scale_x = 1.0
        scale_y = 1.0

    # --------------------------------------------------------
    # MARGIN
    # --------------------------------------------------------

    margin = max(
        0.0,
        float(margin)
    )

    base_width = (
        uv_width *
        scale_x
    )

    base_height = (
        uv_height *
        scale_y
    )

    if margin > 0.0:

        margin_scale_x = (
            base_width + margin * 2.0
        ) / max(
            base_width,
            1e-10
        )

        margin_scale_y = (
            base_height + margin * 2.0
        ) / max(
            base_height,
            1e-10
        )

    else:

        margin_scale_x = 1.0
        margin_scale_y = 1.0

    # --------------------------------------------------------
    # BUILD ONE VERTEX PER LOOP
    # --------------------------------------------------------

    local_vertices = []

    for uv in loop_uv:

        x = (
            uv.x -
            uv_center_u
        ) * scale_x

        y = (
            uv.y -
            uv_center_v
        ) * scale_y

        x *= margin_scale_x
        y *= margin_scale_y

        z = offset_z

        local_vertices.append(
            Vector((
                x,
                y,
                z
            ))
        )

    # --------------------------------------------------------
    # BUILD FACES USING LOOP INDICES
    # --------------------------------------------------------

    new_faces = []

    for polygon in mesh.polygons:

        face = [
            loop_index
            for loop_index
            in polygon.loop_indices
        ]

        if len(face) >= 3:

            new_faces.append(face)

    if not new_faces:

        raise RuntimeError(
            "No valid faces found."
        )

    # --------------------------------------------------------
    # CREATE MESH
    # --------------------------------------------------------

    new_mesh = bpy.data.meshes.new(
        f"{target.name}_UV_Flat_Mesh"
    )

    new_mesh.from_pydata(
        local_vertices,
        [],
        new_faces
    )

    new_mesh.update()

    # --------------------------------------------------------
    # CREATE OBJECT
    # --------------------------------------------------------

    obj = bpy.data.objects.new(
        f"{target.name}_UV_Flat",
        new_mesh
    )

    # The vertices are LOCAL.
    # Therefore copy target transform.
    obj.matrix_world = (
        target.matrix_world.copy()
    )

    # --------------------------------------------------------
    # LINK
    # --------------------------------------------------------

    col = get_uv_flat_collection()

    col.objects.link(obj)

    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    obj.display_type = "WIRE"

    # --------------------------------------------------------
    # CUSTOM PROPERTIES
    # --------------------------------------------------------

    obj["uv_source"] = target.name
    obj["uv_layer"] = uv_layer.name

    obj["uv_min_u"] = min_u
    obj["uv_max_u"] = max_u
    obj["uv_min_v"] = min_v
    obj["uv_max_v"] = max_v

    obj["uv_width"] = uv_width
    obj["uv_height"] = uv_height

    obj["uv_margin"] = margin

    obj["uv_scale_x"] = scale_x
    obj["uv_scale_y"] = scale_y

    return obj


# ============================================================
# SHOW UV FLAT
# ============================================================

class UVPROJECTOR_OT_show_uv_flat(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.show_uv_flat"
    )

    bl_label = "Show UV Flat"

    bl_description = (
        "Create accurate UV flat "
        "comparison"
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(self, context):

        props = (
            context.scene.uv_projector
        )

        target = props.target

        if (
            not target
            or target.type != "MESH"
        ):

            self.report(
                {"ERROR"},
                "Select a valid Target Mesh."
            )

            return {"CANCELLED"}

        if not target.data.uv_layers:

            self.report(
                {"ERROR"},
                "Target Mesh has no UV layers."
            )

            return {"CANCELLED"}

        # Remove old flat.
        clear_collection_objects(
            UV_FLAT_COLLECTION_NAME
        )

        try:

            create_uv_flat_mesh(
                target,
                offset_z=0.01,
                margin=0.0,
                fit_to_object=True,
                preserve_aspect=True,
            )

            self.report(
                {"INFO"},
                (
                    f"UV flat mesh created for "
                    f"'{target.name}'. "
                    f"UV seams preserved."
                )
            )

        except Exception as exc:

            self.report(
                {"ERROR"},
                f"Failed to create UV flat: {exc}"
            )

            traceback.print_exc()

            return {"CANCELLED"}

        return {"FINISHED"}


# ============================================================
# CLEAR UV FLAT
# ============================================================

class UVPROJECTOR_OT_clear_uv_flat(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.clear_uv_flat"
    )

    bl_label = "Clear UV Flat"

    bl_description = (
        "Remove all UV flat meshes"
    )

    def execute(self, context):

        clear_collection_objects(
            UV_FLAT_COLLECTION_NAME
        )

        self.report(
            {"INFO"},
            "UV flat meshes cleared."
        )

        return {"FINISHED"}


# ============================================================
# LEGACY CURVE
# ============================================================

def process_curve_legacy(
    target,
    source,
    props,
    triangles,
    uv_bounds
):
    splines = sample_curve(
        source,
        props.curve_samples
    )

    if not splines:

        raise RuntimeError(
            "No valid Splines in Curve."
        )

    normalized = normalize_source_to_uv(
        splines,
        uv_bounds,
        props
    )

    margin_u, margin_v = (
        estimate_uv_margin(
            props,
            uv_bounds
        )
    )

    mapped = []

    for spline in normalized:

        current = []

        for uv in spline["points"]:

            if props.flip_v:

                uv = (
                    uv[0],
                    1.0 - uv[1]
                )

            inside_box = (
                clip_uv_to_bounds(
                    uv,
                    uv_bounds,
                    margin_u,
                    margin_v
                )
            )

            inside_uv = (
                uv_point_inside(
                    uv,
                    triangles
                )
                if props.clip_outside_uv
                else True
            )

            if (
                inside_box
                and
                inside_uv
            ):

                position, _ = (
                    uv_to_position(
                        uv,
                        triangles,
                        props.use_nearest
                    )
                )

                if position is not None:

                    current.append(
                        position
                    )

            else:

                if len(current) >= 2:

                    mapped.append({
                        "points": current,
                        "cyclic": False,
                    })

                current = []

        if len(current) >= 2:

            mapped.append({
                "points": current,
                "cyclic": (
                    spline["cyclic"]
                    and
                    len(mapped) == 0
                ),
            })

    if not mapped:

        raise RuntimeError(
            "Curve completely outside "
            "UV area after clipping."
        )

    return mapped


# ============================================================
# LEGACY CURVE OUTPUT
# ============================================================

def create_curve_output_legacy(
    target,
    mapped,
    props,
    name
):
    data = bpy.data.curves.new(
        f"UV_{name}",
        "CURVE"
    )

    data.dimensions = "3D"
    data.resolution_u = 12

    if props.bevel_depth > 0:

        data.bevel_depth = (
            props.bevel_depth
        )

        data.bevel_resolution = (
            props.bevel_resolution
        )

    output = bpy.data.objects.new(
        f"UV_{name}",
        data
    )

    get_output_collection().objects.link(
        output
    )

    output.matrix_world = (
        target.matrix_world.copy()
    )

    for spline in mapped:

        points = spline["points"]

        if len(points) < 2:
            continue

        poly = data.splines.new(
            "POLY"
        )

        poly.points.add(
            len(points) - 1
        )

        for index, point in enumerate(
            points
        ):

            poly.points[index].co = (
                point.x,
                point.y,
                point.z,
                1.0
            )

        poly.use_cyclic_u = (
            spline["cyclic"]
        )

    return output


# ============================================================
# LEGACY PROJECTED MESH
# ============================================================

def create_projected_mesh_legacy(
    target,
    source,
    props,
    triangles,
    uv_bounds
):
    src = source.data

    margin_u, margin_v = (
        estimate_uv_margin(
            props,
            uv_bounds
        )
    )

    world_points = [
        source.matrix_world @ vertex.co
        for vertex in src.vertices
    ]

    if not world_points:

        raise RuntimeError(
            "Source mesh has no vertices."
        )

    sx0 = min(
        point.x
        for point in world_points
    )

    sx1 = max(
        point.x
        for point in world_points
    )

    sy0 = min(
        point.y
        for point in world_points
    )

    sy1 = max(
        point.y
        for point in world_points
    )

    source_width = sx1 - sx0
    source_height = sy1 - sy0

    if (
        source_width < 1e-12
        or
        source_height < 1e-12
    ):

        raise RuntimeError(
            "Mesh/Plane must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + margin_u
    tx1 = ux1 - margin_u

    ty0 = uy0 + margin_v
    ty1 = uy1 - margin_v

    scale_u = (
        tx1 - tx0
    ) / source_width

    scale_v = (
        ty1 - ty0
    ) / source_height

    if props.keep_aspect:

        scale = min(
            scale_u,
            scale_v
        )

        scale_u = scale
        scale_v = scale

    source_center_x = (
        sx0 + sx1
    ) / 2.0

    source_center_y = (
        sy0 + sy1
    ) / 2.0

    target_center_u = (
        tx0 + tx1
    ) / 2.0

    target_center_v = (
        ty0 + ty1
    ) / 2.0

    new_vertices = []
    valid = []

    for point in world_points:

        u = (
            target_center_u
            +
            (
                point.x -
                source_center_x
            ) * scale_u
        )

        v = (
            target_center_v
            +
            (
                point.y -
                source_center_y
            ) * scale_v
        )

        if props.flip_v:

            v = 1.0 - v

        uv = (u, v)

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                uv,
                triangles
            )

        inside = (
            inside
            and
            clip_uv_to_bounds(
                uv,
                uv_bounds,
                margin_u,
                margin_v
            )
        )

        position = None

        if inside:

            position, _ = (
                uv_to_position(
                    uv,
                    triangles,
                    props.use_nearest
                )
            )

        if position is None:

            valid.append(False)

            new_vertices.append(
                (0.0, 0.0, 0.0)
            )

        else:

            valid.append(True)

            new_vertices.append(
                tuple(position)
            )

    new_faces = []

    for polygon in src.polygons:

        vertices = list(
            polygon.vertices
        )

        if (
            len(vertices) >= 3
            and
            all(
                valid[index]
                for index in vertices
            )
        ):

            new_faces.append(
                vertices
            )

    if not new_faces:

        raise RuntimeError(
            "No faces remain inside UV area."
        )

    mesh = bpy.data.meshes.new(
        f"UV_{source.name}"
    )

    mesh.from_pydata(
        new_vertices,
        [],
        new_faces
    )

    mesh.update()

    output = bpy.data.objects.new(
        f"UV_{source.name}",
        mesh
    )

    get_output_collection().objects.link(
        output
    )

    return output


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

    source_type: EnumProperty(
        name="Source Type",

        items=[
            (
                "AUTO",
                "Auto",
                "Curve or Mesh"
            ),
            (
                "CURVE",
                "Curve",
                "Selected Curves"
            ),
            (
                "PLANE",
                "Plane / Mesh",
                "Selected Meshes"
            ),
        ],

        default="AUTO"
    )

    clip_outside_uv: BoolProperty(
        name="Clip Outside UV",

        description=(
            "Removes parts outside "
            "actual UV triangles"
        ),

        default=True
    )

    keep_aspect: BoolProperty(
        name="Keep Aspect Ratio",
        default=True
    )

    flip_v: BoolProperty(
        name="Flip V",
        default=False
    )

    use_nearest: BoolProperty(
        name="Nearest Triangle",

        description=(
            "Find nearest triangle "
            "for edge points"
        ),

        default=True
    )

    margin_mode: EnumProperty(
        name="Margin Mode",

        items=[
            (
                "UV",
                "UV",
                "Margin in UV units"
            ),
            (
                "PERCENT",
                "Percent",
                "Margin as percentage"
            ),
            (
                "MM",
                "Millimeters",
                "Estimate margin in mm"
            ),
        ],

        default="UV"
    )

    margin_value: FloatProperty(
        name="Edge Margin",

        description=(
            "Safe distance from UV edges"
        ),

        default=0.002,

        min=0.0
    )

    curve_samples: IntProperty(
        name="Curve Samples",

        default=150,

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

    cut_target: BoolProperty(
        name="Cut Target/Source (Knife)",

        description=(
            "Cuts the target/source directly "
            "instead of creating a new object"
        ),

        default=True
    )

    preserve_edges: BoolProperty(
        name="Preserve Edges",

        description=(
            "Preserves edge structure "
            "to reduce deformation"
        ),

        default=True
    )


# ============================================================
# MAIN PROJECT OPERATOR
# ============================================================

class UVPROJECTOR_OT_project(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.project"
    )

    bl_label = (
        "Project to UV Surface"
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(self, context):

        props = (
            context.scene.uv_projector
        )

        target = props.target

        if (
            not target
            or target.type != "MESH"
        ):

            self.report(
                {"ERROR"},
                "Select a valid Target Mesh."
            )

            return {"CANCELLED"}

        if not target.data.uv_layers:

            self.report(
                {"ERROR"},
                "Target Mesh has no UV layers."
            )

            return {"CANCELLED"}

        try:

            triangles = build_uv_triangles(
                target,
                False
            )

            uv_bounds = get_uv_bounds(
                triangles
            )

        except Exception as exc:

            self.report(
                {"ERROR"},
                str(exc)
            )

            return {"CANCELLED"}

        sources = [
            obj
            for obj in context.selected_objects
            if obj != target
            and (
                (
                    props.source_type == "CURVE"
                    and
                    obj.type == "CURVE"
                )
                or
                (
                    props.source_type == "PLANE"
                    and
                    obj.type == "MESH"
                )
                or
                (
                    props.source_type == "AUTO"
                    and
                    obj.type in {
                        "CURVE",
                        "MESH"
                    }
                )
            )
        ]

        if not sources:

            self.report(
                {"ERROR"},
                (
                    "Select a Curve or Plane/Mesh "
                    "with the Target."
                )
            )

            return {"CANCELLED"}

        success_count = 0
        fail_count = 0

        print()
        print("=" * 70)
        print(
            "UV SURFACE PROJECTOR PRO"
        )
        print(
            "UV PROJECT / KNIFE MODE"
        )
        print("=" * 70)

        for source in sources:

            try:

                if source.type == "CURVE":

                    if props.cut_target:

                        if props.preserve_edges:

                            cut_mesh_with_uv_for_curve_improved(
                                target,
                                source,
                                props,
                                triangles,
                                uv_bounds
                            )

                        else:

                            curve_to_mesh_and_cut_improved(
                                target,
                                source,
                                props,
                                triangles,
                                uv_bounds
                            )

                    else:

                        mapped = (
                            process_curve_legacy(
                                target,
                                source,
                                props,
                                triangles,
                                uv_bounds
                            )
                        )

                        create_curve_output_legacy(
                            target,
                            mapped,
                            props,
                            source.name
                        )

                else:

                    if props.cut_target:

                        cut_mesh_with_uv_improved(
                            target,
                            source,
                            props,
                            triangles,
                            uv_bounds
                        )

                    else:

                        create_projected_mesh_legacy(
                            target,
                            source,
                            props,
                            triangles,
                            uv_bounds
                        )

                success_count += 1

                print(
                    f"[OK] {source.name} "
                    f"- Processed successfully"
                )

            except Exception as exc:

                fail_count += 1

                print(
                    f"[FAILED] "
                    f"{source.name}: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                traceback.print_exc()

                continue

        print(
            f"Finished | "
            f"Success: {success_count} | "
            f"Failed: {fail_count}"
        )

        print("=" * 70)

        self.report(
            {"INFO"},
            (
                f"Completed: "
                f"{success_count} succeeded, "
                f"{fail_count} failed. "
                f"Details in Console."
            )
        )

        return {"FINISHED"}


# ============================================================
# CLEAR RESULTS
# ============================================================

class UVPROJECTOR_OT_clear(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.clear"
    )

    bl_label = "Clear Results"

    def execute(self, context):

        clear_collection_objects(
            OUTPUT_COLLECTION_NAME
        )

        self.report(
            {"INFO"},
            "Results cleared."
        )

        return {"FINISHED"}


# ============================================================
# UI PANEL
# ============================================================

class UVPROJECTOR_PT_panel(
    bpy.types.Panel
):

    bl_label = (
        "UV Surface Projector Pro"
    )

    bl_idname = (
        "UVPROJECTOR_PT_panel"
    )

    bl_space_type = "VIEW_3D"

    bl_region_type = "UI"

    bl_category = "UV Projector"

    def draw(
        self,
        context
    ):
        layout = self.layout

        props = (
            context.scene.uv_projector
        )

        # ----------------------------------------------------
        # TARGET
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
        # SOURCE
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

        # ----------------------------------------------------
        # CUT
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Cut Mode (Knife)",
            icon="SCULPTMODE_HLT"
        )

        box.prop(
            props,
            "cut_target",
            text="Cut Instead of New Object"
        )

        box.prop(
            props,
            "preserve_edges",
            text="Preserve Edges"
        )

        # ----------------------------------------------------
        # UV
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="UV Clipping",
            icon="UV"
        )

        box.prop(
            props,
            "clip_outside_uv"
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
            "use_nearest"
        )

        # ----------------------------------------------------
        # MARGIN
        # ----------------------------------------------------

        box.separator()

        box.label(
            text="Edge Margin"
        )

        box.prop(
            props,
            "margin_mode"
        )

        box.prop(
            props,
            "margin_value"
        )

        if props.margin_mode == "UV":

            box.label(
                text=(
                    "Example: 0.002 = "
                    "small UV margin"
                )
            )

        elif props.margin_mode == "PERCENT":

            box.label(
                text=(
                    "Example: 1 = "
                    "1% of UV area"
                )
            )

        else:

            box.label(
                text=(
                    "MM uses estimation "
                    "from target dimensions"
                )
            )

        # ----------------------------------------------------
        # CURVE
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Curve",
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
        # PROJECT
        # ----------------------------------------------------

        row = layout.row()

        row.scale_y = 1.5

        row.operator(
            "uv_projector.project",
            icon="MOD_SHRINKWRAP"
        )

        # ----------------------------------------------------
        # UV FLAT
        # ----------------------------------------------------

        row = layout.row()

        row.operator(
            "uv_projector.show_uv_flat",
            icon="UV"
        )

        row.operator(
            "uv_projector.clear_uv_flat",
            icon="TRASH"
        )

        # ----------------------------------------------------
        # CLEAR
        # ----------------------------------------------------

        layout.operator(
            "uv_projector.clear",
            icon="TRASH"
        )


# ============================================================
# REGISTER
# ============================================================

classes = (
    UVProjectorProperties,
    UVPROJECTOR_OT_project,
    UVPROJECTOR_OT_show_uv_flat,
    UVPROJECTOR_OT_clear_uv_flat,
    UVPROJECTOR_OT_clear,
    UVPROJECTOR_PT_panel,
)


def register():

    for cls in classes:

        bpy.utils.register_class(
            cls
        )

    bpy.types.Scene.uv_projector = (
        PointerProperty(
            type=UVProjectorProperties
        )
    )


def unregister():

    if hasattr(
        bpy.types.Scene,
        "uv_projector"
    ):

        del bpy.types.Scene.uv_projector

    for cls in reversed(classes):

        bpy.utils.unregister_class(
            cls
        )


if __name__ == "__main__":
    register()
