bl_info = {
    "name": "UV Surface Projector Pro",
    "author": "Simple Code",
    "version": (3, 0, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > UV Projector",
    "description": (
        "Projects curves and meshes onto the active UV target. "
        "The active object is the Target and all other selected objects are Sources. "
        "Includes UV island boundary preview and collapsible settings."
    ),
    "category": "Object",
}

import bpy
import math
import bmesh

from mathutils import Vector
from bpy.props import (
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

def get_or_create_collection(name):
    col = bpy.data.collections.get(name)

    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)

    return col


def get_output_collection():
    return get_or_create_collection(
        OUTPUT_COLLECTION_NAME
    )


def get_uv_flat_collection():
    return get_or_create_collection(
        UV_FLAT_COLLECTION_NAME
    )


def clear_collection(name):
    col = bpy.data.collections.get(name)

    if not col:
        return

    for obj in list(col.objects):
        bpy.data.objects.remove(
            obj,
            do_unlink=True
        )


# ============================================================
# ACTIVE TARGET / SOURCE HELPERS
# ============================================================

def get_active_target(context):
    """
    Active object is always the Target.
    """

    obj = context.active_object

    if obj is None:
        raise RuntimeError(
            "يجب تحديد عنصر وجعله Active ليكون هو Target."
        )

    if obj.type != "MESH":
        raise RuntimeError(
            "العنصر النشط يجب أن يكون Mesh ليكون Target."
        )

    if not obj.data.uv_layers:
        raise RuntimeError(
            "العنصر النشط لا يحتوي على UV Map."
        )

    return obj


def get_sources(context, target, props):
    """
    All selected objects except the active Target
    are considered Sources.
    """

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

            if obj.type in {"CURVE", "MESH"}:
                sources.append(obj)

    return sources


# ============================================================
# UV GEOMETRY
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
        v0x * v1y
        -
        v1x * v0y
    )

    if abs(den) < 1e-12:
        return None

    inv = 1.0 / den

    w2 = (
        v2x * v1y
        -
        v1x * v2y
    ) * inv

    w3 = (
        v0x * v2y
        -
        v0y * v2x
    ) * inv

    return (
        1.0 - w2 - w3,
        w2,
        w3
    )


def barycentric_3d(weights, a, b, c):

    w1, w2, w3 = weights

    return (
        a * w1
        +
        b * w2
        +
        c * w3
    )


def point_segment_distance(p, a, b):

    px, py = p
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    ls = (
        dx * dx
        +
        dy * dy
    )

    if ls < 1e-15:

        return math.hypot(
            px - ax,
            py - ay
        )

    t = (
        (px - ax) * dx
        +
        (py - ay) * dy
    ) / ls

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
            p,
            a,
            b
        ),
        point_segment_distance(
            p,
            b,
            c
        ),
        point_segment_distance(
            p,
            c,
            a
        ),
    )


# ============================================================
# BUILD UV TRIANGLES
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

    mesh.calc_loop_triangles()

    triangles = []

    for tri in mesh.loop_triangles:

        if len(tri.loops) != 3:
            continue

        uv = []
        pos = []

        for li in tri.loops:

            uvv = uv_layer.data[li].uv

            u = float(uvv.x)
            v = float(uvv.y)

            if flip_v:
                v = 1.0 - v

            uv.append(
                (u, v)
            )

            vi = mesh.loops[
                li
            ].vertex_index

            pos.append(
                mesh.vertices[
                    vi
                ].co.copy()
            )

        triangles.append({
            "uv": uv,
            "pos": pos,
        })

    return triangles


def get_uv_bounds(triangles):

    values = [
        uv
        for tri in triangles
        for uv in tri["uv"]
    ]

    if not values:
        raise RuntimeError(
            "لم يتم العثور على بيانات UV."
        )

    us = [
        v[0]
        for v in values
    ]

    vs = [
        v[1]
        for v in values
    ]

    return (
        min(us),
        max(us),
        min(vs),
        max(vs),
    )


# ============================================================
# UV TO POSITION
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
                        tri["pos"][2]
                    ),
                    True
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

    for a, b in (
        (uv[0], uv[1]),
        (uv[1], uv[2]),
        (uv[2], uv[0])
    ):

        ax, ay = a
        bx, by = b

        dx = bx - ax
        dy = by - ay

        ls = (
            dx * dx
            +
            dy * dy
        )

        if ls < 1e-15:

            q = a

        else:

            t = (
                (uv_point[0] - ax) * dx
                +
                (uv_point[1] - ay) * dy
            ) / ls

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

        if d < best_distance:

            best_distance = d
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


def uv_point_inside(
    p,
    triangles,
    tolerance=1e-8
):

    for tri in triangles:

        weights = barycentric_2d(
            p,
            tri["uv"][0],
            tri["uv"][1],
            tri["uv"][2]
        )

        if weights:

            if all(
                w >= -tolerance
                for w in weights
            ):
                return True

    return False


# ============================================================
# MARGIN
# ============================================================

def estimate_uv_margin(
    props,
    uv_bounds,
    target
):

    # When disabled, margin is EXACTLY zero.
    if not props.enable_margin:
        return 0.0, 0.0

    min_u, max_u, min_v, max_v = uv_bounds

    uv_width = max_u - min_u
    uv_height = max_v - min_v

    if props.margin_mode == "UV":

        m = max(
            0.0,
            props.margin_value
        )

        return m, m

    if props.margin_mode == "PERCENT":

        m = max(
            0.0,
            props.margin_value
        ) / 100.0

        return (
            uv_width * m,
            uv_height * m
        )

    # MM

    dims = target.dimensions

    world_w = max(
        abs(dims.x),
        1e-9
    )

    world_h = max(
        abs(dims.y),
        1e-9
    )

    mm = max(
        0.0,
        props.margin_value
    ) / 1000.0

    return (
        uv_width * (
            mm / world_w
        ),
        uv_height * (
            mm / world_h
        )
    )


def clip_uv_to_bounds(
    p,
    bounds,
    margin_u,
    margin_v
):

    min_u, max_u, min_v, max_v = bounds

    return (
        min_u + margin_u <= p[0] <= max_u - margin_u
        and
        min_v + margin_v <= p[1] <= max_v - margin_v
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
        p1 * (3 * u * u * t)
        +
        p2 * (3 * u * t * t)
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

                bp = spline.bezier_points
                count = len(bp)

                if count < 2:
                    continue

                segments = (
                    count
                    if spline.use_cyclic_u
                    else count - 1
                )

                per_segment = max(
                    4,
                    samples // max(
                        1,
                        segments
                    )
                )

                for i in range(
                    segments
                ):

                    p0 = bp[i]

                    p3 = bp[
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
                                t
                            )
                        )

                if not spline.use_cyclic_u:

                    points.append(
                        bp[-1].co.copy()
                    )

            elif spline.type in {
                "POLY",
                "NURBS"
            }:

                points = [
                    p.co.xyz.copy()
                    for p in spline.points
                ]

            if len(points) >= 2:

                result.append({
                    "index": spline_index,
                    "points": points,
                    "cyclic": spline.use_cyclic_u
                })

        except Exception as e:

            print(
                f"[UV Projector] "
                f"Curve spline {spline_index} failed: {e}"
            )

    return result


def source_bounds(splines):

    points = [
        p
        for spline in splines
        for p in spline["points"]
    ]

    if not points:
        raise RuntimeError(
            "المصدر لا يحتوي نقاطًا."
        )

    return (
        min(
            p.x
            for p in points
        ),
        max(
            p.x
            for p in points
        ),
        min(
            p.y
            for p in points
        ),
        max(
            p.y
            for p in points
        ),
    )


def normalize_source_to_uv(
    splines,
    uv_bounds,
    props,
    target
):

    sx0, sx1, sy0, sy1 = source_bounds(
        splines
    )

    ux0, ux1, uy0, uy1 = uv_bounds

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds,
        target
    )

    tx0 = ux0 + mu
    tx1 = ux1 - mu

    ty0 = uy0 + mv
    ty1 = uy1 - mv

    if tx1 <= tx0 or ty1 <= ty0:

        raise RuntimeError(
            "الهامش أكبر من مساحة UV."
        )

    sw = sx1 - sx0
    sh = sy1 - sy0

    if (
        abs(sw) < 1e-12
        or
        abs(sh) < 1e-12
    ):

        raise RuntimeError(
            "عرض أو ارتفاع المصدر يساوي صفرًا."
        )

    su = (
        tx1 - tx0
    ) / sw

    sv = (
        ty1 - ty0
    ) / sh

    if props.keep_aspect:

        scale = min(
            su,
            sv
        )

        su = scale
        sv = scale

    scx = (
        sx0 + sx1
    ) / 2

    scy = (
        sy0 + sy1
    ) / 2

    tcx = (
        tx0 + tx1
    ) / 2

    tcy = (
        ty0 + ty1
    ) / 2

    output = []

    for spline in splines:

        uv_points = []

        for p in spline["points"]:

            uv_points.append(
                (
                    tcx +
                    (p.x - scx) * su,

                    tcy +
                    (p.y - scy) * sv
                )
            )

        output.append({
            "points": uv_points,
            "cyclic": spline["cyclic"],
            "index": spline["index"]
        })

    return output


# ============================================================
# SOURCE MESH -> TARGET SURFACE
# ============================================================

def project_mesh_to_target(
    target,
    source,
    props,
    triangles,
    uv_bounds
):

    src_mesh = source.data

    # --------------------------------------------------------
    # Source world coordinates
    # --------------------------------------------------------

    source_world_points = [
        source.matrix_world @ vertex.co
        for vertex in src_mesh.vertices
    ]

    if not source_world_points:

        raise RuntimeError(
            "Source mesh has no vertices."
        )

    sx0 = min(
        p.x
        for p in source_world_points
    )

    sx1 = max(
        p.x
        for p in source_world_points
    )

    sy0 = min(
        p.y
        for p in source_world_points
    )

    sy1 = max(
        p.y
        for p in source_world_points
    )

    sw = sx1 - sx0
    sh = sy1 - sy0

    if (
        sw < 1e-12
        or
        sh < 1e-12
    ):

        raise RuntimeError(
            "Mesh/Plane must have area in X/Y."
        )

    # --------------------------------------------------------
    # UV destination
    # --------------------------------------------------------

    ux0, ux1, uy0, uy1 = uv_bounds

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds,
        target
    )

    tx0 = ux0 + mu
    tx1 = ux1 - mu

    ty0 = uy0 + mv
    ty1 = uy1 - mv

    if tx1 <= tx0 or ty1 <= ty0:

        raise RuntimeError(
            "UV destination became empty."
        )

    su = (
        tx1 - tx0
    ) / sw

    sv = (
        ty1 - ty0
    ) / sh

    if props.keep_aspect:

        scale = min(
            su,
            sv
        )

        su = scale
        sv = scale

    scx = (
        sx0 + sx1
    ) / 2

    scy = (
        sy0 + sy1
    ) / 2

    tcx = (
        tx0 + tx1
    ) / 2

    tcy = (
        ty0 + ty1
    ) / 2

    # --------------------------------------------------------
    # Calculate projected positions
    # --------------------------------------------------------

    valid = []
    projected_world = []

    for world_pos in source_world_points:

        u = (
            tcx +
            (world_pos.x - scx) * su
        )

        v = (
            tcy +
            (world_pos.y - scy) * sv
        )

        if props.flip_v:
            v = 1.0 - v

        uv = (
            u,
            v
        )

        inside = True

        # Actual UV triangles clipping
        if props.clip_outside_uv:

            inside = uv_point_inside(
                uv,
                triangles
            )

        # Margin clipping
        if inside and props.enable_margin:

            inside = clip_uv_to_bounds(
                uv,
                uv_bounds,
                mu,
                mv
            )

        # Margin disabled
        elif inside and not props.enable_margin:

            inside = clip_uv_to_bounds(
                uv,
                uv_bounds,
                0.0,
                0.0
            )

        position_local = None

        if inside:

            position_local, _ = uv_to_position(
                uv,
                triangles,
                props.use_nearest
            )

        if position_local is None:

            valid.append(False)
            projected_world.append(None)

        else:

            target_world_position = (
                target.matrix_world
                @
                position_local
            )

            valid.append(True)

            projected_world.append(
                target_world_position
            )

    # --------------------------------------------------------
    # Check valid faces
    # --------------------------------------------------------

    face_valid = []

    for poly in src_mesh.polygons:

        verts = list(
            poly.vertices
        )

        face_valid.append(
            len(verts) >= 3
            and
            all(
                valid[index]
                for index in verts
            )
        )

    if not any(face_valid):

        raise RuntimeError(
            "No faces remain inside UV area."
        )

    # --------------------------------------------------------
    # BMesh
    # --------------------------------------------------------

    bm = bmesh.new()

    try:

        bm.from_mesh(
            src_mesh
        )

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Move valid vertices
        for index, world_pos in enumerate(
            projected_world
        ):

            if world_pos is None:
                continue

            if index >= len(
                bm.verts
            ):
                continue

            # TARGET WORLD -> SOURCE LOCAL
            local_position = (
                source.matrix_world.inverted_safe()
                @
                world_pos
            )

            bm.verts[index].co = (
                local_position
            )

        # ----------------------------------------------------
        # Delete invalid faces
        # ----------------------------------------------------

        faces_to_delete = []

        for face in list(
            bm.faces
        ):

            should_delete = False

            for vertex in face.verts:

                if not valid[
                    vertex.index
                ]:

                    should_delete = True
                    break

            if should_delete:

                faces_to_delete.append(
                    face
                )

        if faces_to_delete:

            bmesh.ops.delete(
                bm,
                geom=faces_to_delete,
                context="FACES"
            )

        # ----------------------------------------------------
        # Remove loose invalid vertices
        # ----------------------------------------------------

        invalid_vertices = [
            bm.verts[i]
            for i, state in enumerate(valid)
            if not state
            and i < len(bm.verts)
        ]

        invalid_vertices = [
            v
            for v in invalid_vertices
            if v.is_valid
            and not v.link_faces
        ]

        if invalid_vertices:

            bmesh.ops.delete(
                bm,
                geom=invalid_vertices,
                context="VERTS"
            )

        # ----------------------------------------------------
        # Optional preserve edges
        # ----------------------------------------------------

        if props.preserve_edges:

            bmesh.ops.remove_doubles(
                bm,
                verts=list(
                    bm.verts
                ),
                dist=0.000001
            )

        bm.to_mesh(
            src_mesh
        )

        src_mesh.update()

    finally:

        bm.free()

    return source


# ============================================================
# CURVE -> PROJECTED SURFACE
# ============================================================

def project_curve_to_target(
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
        props,
        target
    )

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds,
        target
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

            inside = True

            if props.clip_outside_uv:

                inside = uv_point_inside(
                    uv,
                    triangles
                )

            if inside:

                if props.enable_margin:

                    inside = clip_uv_to_bounds(
                        uv,
                        uv_bounds,
                        mu,
                        mv
                    )

                else:

                    inside = clip_uv_to_bounds(
                        uv,
                        uv_bounds,
                        0.0,
                        0.0
                    )

            if inside:

                position, _ = uv_to_position(
                    uv,
                    triangles,
                    props.use_nearest
                )

                if position is not None:

                    world_position = (
                        target.matrix_world
                        @
                        position
                    )

                    current.append(
                        world_position
                    )

                else:

                    if len(current) >= 2:

                        mapped.append({
                            "points": current,
                            "cyclic": False
                        })

                    current = []

            else:

                if len(current) >= 2:

                    mapped.append({
                        "points": current,
                        "cyclic": False
                    })

                current = []

        if len(current) >= 2:

            mapped.append({
                "points": current,
                "cyclic": (
                    spline["cyclic"]
                    and
                    len(current) >= 3
                )
            })

    if not mapped:

        raise RuntimeError(
            "Curve completely outside UV area."
        )

    return mapped


def create_curve_output(
    target,
    mapped,
    props,
    name
):

    curve_data = bpy.data.curves.new(
        f"UV_{name}",
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
        f"UV_{name}",
        curve_data
    )

    get_output_collection().objects.link(
        output
    )

    # World coordinates are used directly.
    output.matrix_world.identity()

    for spline in mapped:

        points = spline["points"]

        if len(points) < 2:
            continue

        poly = curve_data.splines.new(
            "POLY"
        )

        poly.points.add(
            len(points) - 1
        )

        for i, point in enumerate(
            points
        ):

            poly.points[i].co = (
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
# UV FLAT - ONLY UV ISLAND BOUNDARIES
# ============================================================

def uv_key(
    uv,
    precision=8
):

    return (
        round(
            float(uv[0]),
            precision
        ),
        round(
            float(uv[1]),
            precision
        )
    )


def normalized_edge_key(
    a,
    b
):

    ka = uv_key(a)
    kb = uv_key(b)

    if ka <= kb:

        return (
            ka,
            kb
        )

    return (
        kb,
        ka
    )


def build_uv_boundary_edges(
    target,
    flip_v=False
):

    mesh = target.data

    if not mesh.uv_layers:

        raise RuntimeError(
            "Target has no UV layer."
        )

    uv_layer = mesh.uv_layers.active

    boundary_counts = {}

    for poly in mesh.polygons:

        loop_indices = list(
            poly.loop_indices
        )

        if len(loop_indices) < 3:
            continue

        # Fan triangulation
        for i in range(
            1,
            len(loop_indices) - 1
        ):

            tri_loops = (
                loop_indices[0],
                loop_indices[i],
                loop_indices[i + 1]
            )

            tri_uv = []

            for li in tri_loops:

                uv = uv_layer.data[
                    li
                ].uv

                u = float(
                    uv.x
                )

                v = float(
                    uv.y
                )

                if flip_v:
                    v = 1.0 - v

                tri_uv.append(
                    (
                        u,
                        v
                    )
                )

            edges = (
                (
                    tri_uv[0],
                    tri_uv[1]
                ),
                (
                    tri_uv[1],
                    tri_uv[2]
                ),
                (
                    tri_uv[2],
                    tri_uv[0]
                ),
            )

            for a, b in edges:

                key = normalized_edge_key(
                    a,
                    b
                )

                if key not in boundary_counts:

                    boundary_counts[key] = {
                        "count": 1,
                        "a": a,
                        "b": b,
                    }

                else:

                    boundary_counts[key][
                        "count"
                    ] += 1

    boundary_edges = []

    for data in boundary_counts.values():

        if data["count"] == 1:

            boundary_edges.append(
                (
                    data["a"],
                    data["b"]
                )
            )

    return boundary_edges


def create_uv_flat_mesh(
    target,
    offset_z=0.01
):

    mesh = target.data

    if not mesh.uv_layers:

        raise RuntimeError(
            "Target has no UV layers."
        )

    boundary_edges = build_uv_boundary_edges(
        target,
        False
    )

    if not boundary_edges:

        raise RuntimeError(
            "No UV island boundary edges found."
        )

    # --------------------------------------------------------
    # UV bounds
    # --------------------------------------------------------

    all_uv = []

    for a, b in boundary_edges:

        all_uv.append(a)
        all_uv.append(b)

    min_u = min(
        p[0]
        for p in all_uv
    )

    max_u = max(
        p[0]
        for p in all_uv
    )

    min_v = min(
        p[1]
        for p in all_uv
    )

    max_v = max(
        p[1]
        for p in all_uv
    )

    uv_width = max(
        max_u - min_u,
        1e-8
    )

    uv_height = max(
        max_v - min_v,
        1e-8
    )

    # --------------------------------------------------------
    # Real world dimensions
    # --------------------------------------------------------

    world_vertices = [
        target.matrix_world @ vertex.co
        for vertex in mesh.vertices
    ]

    if not world_vertices:

        raise RuntimeError(
            "Target has no vertices."
        )

    world_min_x = min(
        p.x
        for p in world_vertices
    )

    world_max_x = max(
        p.x
        for p in world_vertices
    )

    world_min_y = min(
        p.y
        for p in world_vertices
    )

    world_max_y = max(
        p.y
        for p in world_vertices
    )

    world_width = max(
        world_max_x - world_min_x,
        1e-8
    )

    world_height = max(
        world_max_y - world_min_y,
        1e-8
    )

    # --------------------------------------------------------
    # Uniform scale
    # --------------------------------------------------------

    scale = min(
        world_width / uv_width,
        world_height / uv_height
    )

    uv_center = Vector((
        (
            min_u + max_u
        ) / 2,

        (
            min_v + max_v
        ) / 2
    ))

    # --------------------------------------------------------
    # Build unique vertices
    # --------------------------------------------------------

    vertex_map = {}
    vertices = []
    edges = []

    for uv_a, uv_b in boundary_edges:

        for uv in (
            uv_a,
            uv_b
        ):

            key = uv_key(
                uv
            )

            if key not in vertex_map:

                x = (
                    uv[0]
                    -
                    uv_center.x
                ) * scale

                y = (
                    uv[1]
                    -
                    uv_center.y
                ) * scale

                local_position = Vector((
                    x,
                    y,
                    offset_z
                ))

                world_position = (
                    target.matrix_world
                    @
                    local_position
                )

                vertex_map[key] = len(
                    vertices
                )

                vertices.append(
                    world_position
                )

        ka = uv_key(
            uv_a
        )

        kb = uv_key(
            uv_b
        )

        ia = vertex_map[ka]
        ib = vertex_map[kb]

        edges.append(
            (
                ia,
                ib
            )
        )

    # --------------------------------------------------------
    # Create edge-only mesh
    # --------------------------------------------------------

    new_mesh = bpy.data.meshes.new(
        f"{target.name}_UV_Boundary"
    )

    new_mesh.from_pydata(
        vertices,
        edges,
        []
    )

    new_mesh.update()

    output = bpy.data.objects.new(
        f"{target.name}_UV_Boundary",
        new_mesh
    )

    get_uv_flat_collection().objects.link(
        output
    )

    output.display_type = "WIRE"

    return output


# ============================================================
# PROJECT OPERATOR
# ============================================================

class UVPROJECTOR_OT_project(
    bpy.types.Operator
):

    bl_idname = "uv_projector.project"

    bl_label = "Project / Cut"

    bl_description = (
        "Active object = Target. "
        "Other selected objects = Sources."
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(self, context):

        props = context.scene.uv_projector

        # ----------------------------------------------------
        # Active object = Target
        # ----------------------------------------------------

        try:

            target = get_active_target(
                context
            )

        except Exception as e:

            self.report(
                {"ERROR"},
                str(e)
            )

            return {"CANCELLED"}

        # ----------------------------------------------------
        # Build UV data
        # ----------------------------------------------------

        try:

            triangles = build_uv_triangles(
                target,
                False
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

        sources = get_sources(
            context,
            target,
            props
        )

        if not sources:

            self.report(
                {"ERROR"},
                "حدد Target كعنصر Active ثم حدد معه العناصر الأخرى كمصادر."
            )

            return {"CANCELLED"}

        print()
        print("=" * 70)
        print("UV SURFACE PROJECTOR PRO")
        print("=" * 70)

        print(
            f"TARGET : {target.name}"
        )

        print(
            f"SOURCES: {len(sources)}"
        )

        success = 0
        failed = 0

        for source in sources:

            try:

                print(
                    f"\nProcessing: {source.name}"
                )

                # ------------------------------------------------
                # CURVE
                # ------------------------------------------------

                if source.type == "CURVE":

                    mapped = project_curve_to_target(
                        target,
                        source,
                        props,
                        triangles,
                        uv_bounds
                    )

                    # Curves create projected surface curves.
                    create_curve_output(
                        target,
                        mapped,
                        props,
                        source.name
                    )

                # ------------------------------------------------
                # MESH
                # ------------------------------------------------

                elif source.type == "MESH":

                    project_mesh_to_target(
                        target,
                        source,
                        props,
                        triangles,
                        uv_bounds
                    )

                success += 1

                print(
                    f"[OK] {source.name}"
                )

            except Exception as e:

                failed += 1

                print(
                    f"[FAILED] {source.name}: "
                    f"{type(e).__name__}: {e}"
                )

                import traceback

                traceback.print_exc()

        print()

        print(
            f"Finished | "
            f"Success: {success} | "
            f"Failed: {failed}"
        )

        print("=" * 70)

        self.report(
            {"INFO"},
            (
                f"Target: {target.name} | "
                f"Success: {success} | "
                f"Failed: {failed}"
            )
        )

        return {"FINISHED"}


# ============================================================
# SHOW UV BOUNDARY
# ============================================================

class UVPROJECTOR_OT_show_uv_flat(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.show_uv_flat"
    )

    bl_label = "Show UV Boundary"

    bl_description = (
        "Creates only UV island boundary lines "
        "with real-world scale."
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(self, context):

        try:

            target = get_active_target(
                context
            )

        except Exception as e:

            self.report(
                {"ERROR"},
                str(e)
            )

            return {"CANCELLED"}

        clear_collection(
            UV_FLAT_COLLECTION_NAME
        )

        try:

            create_uv_flat_mesh(
                target,
                offset_z=0.01
            )

        except Exception as e:

            self.report(
                {"ERROR"},
                f"UV Boundary failed: {e}"
            )

            return {"CANCELLED"}

        self.report(
            {"INFO"},
            (
                f"UV Boundary created "
                f"for '{target.name}'."
            )
        )

        return {"FINISHED"}


# ============================================================
# CLEAR UV
# ============================================================

class UVPROJECTOR_OT_clear_uv_flat(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.clear_uv_flat"
    )

    bl_label = "Clear UV Boundary"

    def execute(self, context):

        clear_collection(
            UV_FLAT_COLLECTION_NAME
        )

        self.report(
            {"INFO"},
            "UV Boundary cleared."
        )

        return {"FINISHED"}


# ============================================================
# CLEAR RESULTS
# ============================================================

class UVPROJECTOR_OT_clear(
    bpy.types.Operator
):

    bl_idname = "uv_projector.clear"

    bl_label = "Clear Results"

    def execute(self, context):

        clear_collection(
            OUTPUT_COLLECTION_NAME
        )

        self.report(
            {"INFO"},
            "Results cleared."
        )

        return {"FINISHED"}


# ============================================================
# PROPERTIES
# ============================================================

class UVPROJECTORProperties(
    bpy.types.PropertyGroup
):

    # ========================================================
    # COLLAPSIBLE UI SECTIONS
    # ========================================================

    show_source: BoolProperty(
        name="Source",
        default=True
    )

    show_cut: BoolProperty(
        name="Projection / Cut",
        default=True
    )

    show_uv: BoolProperty(
        name="UV Projection",
        default=True
    )

    show_margin: BoolProperty(
        name="Edge Margin",
        default=False
    )

    show_curve: BoolProperty(
        name="Curve Settings",
        default=False
    )

    # ========================================================
    # SOURCE TYPE
    # ========================================================

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
                "Use selected Curves"
            ),
            (
                "PLANE",
                "Mesh",
                "Use selected Meshes"
            ),
        ],

        default="AUTO"
    )

    # ========================================================
    # CUT
    # ========================================================

    cut_target: BoolProperty(
        name="Cut / Modify Source",

        description=(
            "Modify selected source meshes "
            "instead of creating a new mesh"
        ),

        default=True
    )

    preserve_edges: BoolProperty(
        name="Preserve Edges",

        description=(
            "Avoid aggressive vertex welding "
            "and preserve source topology"
        ),

        default=True
    )

    # ========================================================
    # UV CLIPPING
    # ========================================================

    clip_outside_uv: BoolProperty(
        name="Clip Outside UV",

        description=(
            "Remove source parts outside "
            "the actual UV islands"
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
            "Find nearest UV triangle for "
            "points close to UV boundaries"
        ),

        default=True
    )

    # ========================================================
    # MARGIN
    # ========================================================

    enable_margin: BoolProperty(
        name="Enable Edge Margin",

        description=(
            "Enable/disable UV edge margin. "
            "When disabled, margin is exactly zero."
        ),

        default=False
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
                "Percentage of UV size"
            ),
            (
                "MM",
                "Millimeters",
                "Estimate from target dimensions"
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

    # ========================================================
    # CURVE
    # ========================================================

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


# ============================================================
# UI HELPERS
# ============================================================

def draw_fold_header(
    layout,
    props,
    property_name,
    title,
    icon
):

    row = layout.row()

    is_open = getattr(
        props,
        property_name
    )

    row.prop(
        props,
        property_name,
        text="",
        emboss=False,
        icon=(
            "TRIA_DOWN"
            if is_open
            else "TRIA_RIGHT"
        )
    )

    row.label(
        text=title,
        icon=icon
    )

    return is_open


# ============================================================
# PANEL
# ============================================================

class UVPROJECTOR_PT_panel(
    bpy.types.Panel
):

    bl_label = "UV Surface Projector Pro"

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

        active = context.active_object

        # ====================================================
        # TARGET
        # ====================================================

        box = layout.box()

        row = box.row()

        row.label(
            text="Target",
            icon="MESH_DATA"
        )

        if active and active.type == "MESH":

            row.label(
                text=active.name,
                icon="CHECKMARK"
            )

        else:

            row.label(
                text="Select Active Mesh",
                icon="ERROR"
            )

        box.label(
            text=(
                "Active Object = Target"
            )
        )

        box.label(
            text=(
                "Other Selected Objects = Sources"
            )
        )

        # ====================================================
        # SOURCE
        # ====================================================

        box = layout.box()

        if draw_fold_header(
            box,
            props,
            "show_source",
            "Source",
            "OBJECT_DATA"
        ):

            box.separator()

            box.prop(
                props,
                "source_type",
                expand=True
            )

        # ====================================================
        # CUT
        # ====================================================

        box = layout.box()

        if draw_fold_header(
            box,
            props,
            "show_cut",
            "Projection / Cut",
            "SCULPTMODE_HLT"
        ):

            box.separator()

            box.prop(
                props,
                "cut_target"
            )

            box.prop(
                props,
                "preserve_edges"
            )

            box.separator()

            box.label(
                text=(
                    "Mesh sources are modified "
                    "directly."
                )
            )

            box.label(
                text=(
                    "Curves create projected "
                    "surface curves."
                )
            )

        # ====================================================
        # UV
        # ====================================================

        box = layout.box()

        if draw_fold_header(
            box,
            props,
            "show_uv",
            "UV Projection",
            "UV_DATA"
        ):

            box.separator()

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

        # ====================================================
        # MARGIN
        # ====================================================

        box = layout.box()

        if draw_fold_header(
            box,
            props,
            "show_margin",
            "Edge Margin",
            "MOD_BEVEL"
        ):

            box.separator()

            box.prop(
                props,
                "enable_margin"
            )

            if props.enable_margin:

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
                            "Example: 0.002 UV"
                        )
                    )

                elif props.margin_mode == "PERCENT":

                    box.label(
                        text=(
                            "Example: 1 = 1%"
                        )
                    )

                else:

                    box.label(
                        text=(
                            "Millimeters are estimated "
                            "from target dimensions."
                        )
                    )

            else:

                box.label(
                    text=(
                        "Margin DISABLED — "
                        "no margin will be removed."
                    ),
                    icon="CHECKMARK"
                )

        # ====================================================
        # CURVE
        # ====================================================

        box = layout.box()

        if draw_fold_header(
            box,
            props,
            "show_curve",
            "Curve Settings",
            "CURVE_DATA"
        ):

            box.separator()

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

        # ====================================================
        # ACTIONS
        # ====================================================

        box = layout.box()

        row = box.row()

        row.scale_y = 1.6

        row.operator(
            "uv_projector.project",
            text="Project / Cut",
            icon="MOD_SHRINKWRAP"
        )

        row = box.row()

        row.operator(
            "uv_projector.show_uv_flat",
            text="UV Boundary",
            icon="UV"
        )

        row.operator(
            "uv_projector.clear_uv_flat",
            text="Clear",
            icon="TRASH"
        )

        box.operator(
            "uv_projector.clear",
            text="Clear Results",
            icon="TRASH"
        )


# ============================================================
# REGISTER
# ============================================================

classes = (

    UVPROJECTORProperties,

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
        bpy.props.PointerProperty(
            type=UVPROJECTORProperties
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
