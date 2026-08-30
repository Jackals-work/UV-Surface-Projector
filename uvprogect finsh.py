```python
bl_info = {
    "name": "UV Surface Projector Pro",
    "author": "Simple Code",
    "version": (2, 4, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > UV Projector",
    "description": "Projects and cuts Curves and Mesh/Planes onto a UV-mapped target, with UV boundary view",
    "category": "Object",
}

import bpy
import math
import bmesh

from mathutils import Vector, Matrix

from bpy.props import (
    PointerProperty,
    BoolProperty,
    FloatProperty,
    IntProperty,
    EnumProperty
)


OUTPUT_COLLECTION_NAME = "UV_Projector_Results"
UV_FLAT_COLLECTION_NAME = "UV_Flat_Comparison"


# ============================================================
# UV / GEOMETRY HELPERS
# ============================================================

def barycentric_2d(p, a, b, c):
    px, py = p
    ax, ay = a
    bx, by = b
    cx, cy = c

    v0x, v0y = bx - ax, by - ay
    v1x, v1y = cx - ax, cy - ay
    v2x, v2y = px - ax, py - ay

    den = v0x * v1y - v1x * v0y

    if abs(den) < 1e-12:
        return None

    inv = 1.0 / den

    w2 = (v2x * v1y - v1x * v2y) * inv
    w3 = (v0x * v2y - v0y * v2x) * inv

    return 1.0 - w2 - w3, w2, w3


def barycentric_3d(weights, a, b, c):
    w1, w2, w3 = weights
    return a * w1 + b * w2 + c * w3


def point_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b

    dx = bx - ax
    dy = by - ay

    ls = dx * dx + dy * dy

    if ls < 1e-15:
        return math.hypot(px - ax, py - ay)

    t = (
        (px - ax) * dx +
        (py - ay) * dy
    ) / ls

    t = max(0.0, min(1.0, t))

    qx = ax + dx * t
    qy = ay + dy * t

    return math.hypot(
        px - qx,
        py - qy
    )


def triangle_distance(p, a, b, c):
    bary = barycentric_2d(p, a, b, c)

    if bary:
        if all(w >= 0 for w in bary):
            return 0.0

    return min(
        point_segment_distance(p, a, b),
        point_segment_distance(p, b, c),
        point_segment_distance(p, c, a)
    )


def build_uv_triangles(obj, flip_v=False):
    mesh = obj.data

    if not mesh.uv_layers:
        raise RuntimeError(
            "Target Mesh لا يحتوي على UV."
        )

    uv_layer = mesh.uv_layers.active

    mesh.calc_loop_triangles()

    tris = []

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

            uv.append((u, v))

            vi = mesh.loops[li].vertex_index

            pos.append(
                mesh.vertices[vi].co.copy()
            )

        tris.append({
            "uv": uv,
            "pos": pos
        })

    return tris


def get_uv_bounds(tris):

    vals = [
        (u, v)
        for t in tris
        for u, v in t["uv"]
    ]

    if not vals:
        raise RuntimeError(
            "لم يتم العثور على بيانات UV."
        )

    us = [x for x, y in vals]
    vs = [y for x, y in vals]

    return (
        min(us),
        max(us),
        min(vs),
        max(vs)
    )


def uv_to_position(
    uv_point,
    triangles,
    nearest=True
):

    best_d = float("inf")
    best = None

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

            d = triangle_distance(
                uv_point,
                a,
                b,
                c
            )

            if d < best_d:

                best_d = d
                best = tri

    if best is None:
        return None, False

    uv = best["uv"]
    pos = best["pos"]

    best_q = None
    best_d = float("inf")

    for a, b in (
        (uv[0], uv[1]),
        (uv[1], uv[2]),
        (uv[2], uv[0])
    ):

        ax, ay = a
        bx, by = b

        dx = bx - ax
        dy = by - ay

        ls = dx * dx + dy * dy

        if ls < 1e-15:

            q = a

        else:

            t = (
                (uv_point[0] - ax) * dx +
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


def uv_point_inside(
    p,
    triangles,
    tolerance=1e-8
):

    for tri in triangles:

        w = barycentric_2d(
            p,
            tri["uv"][0],
            tri["uv"][1],
            tri["uv"][2]
        )

        if w and all(
            x >= -tolerance
            for x in w
        ):
            return True

    return False


# ============================================================
# UV MARGIN / CLIPPING
# ============================================================

def estimate_uv_margin(
    props,
    uv_bounds
):
    """
    Calculate UV margin.

    If use_margin is False:
        margin = 0
    """

    # --------------------------------------------------------
    # Margin disabled
    # --------------------------------------------------------

    if not props.use_margin:
        return 0.0, 0.0

    min_u, max_u, min_v, max_v = uv_bounds

    uw = max_u - min_u
    vh = max_v - min_v

    # --------------------------------------------------------
    # UV units
    # --------------------------------------------------------

    if props.margin_mode == "UV":

        margin = max(
            0.0,
            props.margin_value
        )

        return margin, margin

    # --------------------------------------------------------
    # Percentage
    # --------------------------------------------------------

    if props.margin_mode == "PERCENT":

        m = max(
            0.0,
            props.margin_value
        ) / 100.0

        return (
            uw * m,
            vh * m
        )

    # --------------------------------------------------------
    # Millimeters
    # --------------------------------------------------------

    target = props.target

    if not target:
        return 0.0, 0.0

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
        uw * (mm / world_w),
        vh * (mm / world_h)
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

    for si, spline in enumerate(
        obj.data.splines
    ):

        try:

            pts = []

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

                per_seg = max(
                    4,
                    samples // max(
                        1,
                        segments
                    )
                )

                for i in range(segments):

                    p0 = bp[i]

                    p3 = bp[
                        (i + 1) % count
                    ]

                    for s in range(
                        per_seg
                    ):

                        if i > 0 and s == 0:
                            continue

                        t = s / per_seg

                        pts.append(
                            bezier_point(
                                p0.co.copy(),
                                p0.handle_right.copy(),
                                p3.handle_left.copy(),
                                p3.co.copy(),
                                t
                            )
                        )

                if not spline.use_cyclic_u:

                    pts.append(
                        bp[-1].co.copy()
                    )

            elif spline.type in {
                "POLY",
                "NURBS"
            }:

                pts = [
                    p.co.xyz.copy()
                    for p in spline.points
                ]

            if len(pts) >= 2:

                result.append({
                    "index": si,
                    "points": pts,
                    "cyclic": spline.use_cyclic_u
                })

        except Exception as e:

            print(
                f"[UV Projector] "
                f"Curve spline {si} failed: {e}"
            )

    return result


def source_bounds(splines):

    pts = [
        p
        for s in splines
        for p in s["points"]
    ]

    if not pts:
        raise RuntimeError(
            "المصدر لا يحتوي نقاطًا."
        )

    return (
        min(p.x for p in pts),
        max(p.x for p in pts),
        min(p.y for p in pts),
        max(p.y for p in pts)
    )


def normalize_source_to_uv(
    splines,
    uv_bounds,
    props
):

    sx0, sx1, sy0, sy1 = source_bounds(
        splines
    )

    ux0, ux1, uy0, uy1 = uv_bounds

    uw = ux1 - ux0
    uh = uy1 - uy0

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds
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

    if abs(sw) < 1e-12:
        raise RuntimeError(
            "عرض المصدر يساوي صفرًا."
        )

    if abs(sh) < 1e-12:
        raise RuntimeError(
            "ارتفاع المصدر يساوي صفرًا."
        )

    su = (tx1 - tx0) / sw
    sv = (ty1 - ty0) / sh

    if props.keep_aspect:

        s = min(
            su,
            sv
        )

        su = s
        sv = s

    scx = (sx0 + sx1) / 2
    scy = (sy0 + sy1) / 2

    tcx = (tx0 + tx1) / 2
    tcy = (ty0 + ty1) / 2

    out = []

    for s in splines:

        uvpts = []

        for p in s["points"]:

            uvpts.append((
                tcx + (p.x - scx) * su,
                tcy + (p.y - scy) * sv
            ))

        out.append({
            "points": uvpts,
            "cyclic": s["cyclic"],
            "index": s["index"]
        })

    return out


# ============================================================
# IMPROVED MESH CUT
# ============================================================

def cut_mesh_with_uv_improved(
    target,
    source,
    props,
    triangles,
    uv_bounds
):

    src = source.data

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds
    )

    world_matrix = source.matrix_world

    world_pts = [
        world_matrix @ v.co
        for v in src.vertices
    ]

    if not world_pts:
        raise RuntimeError(
            "Source mesh has no vertices."
        )

    sx0 = min(p.x for p in world_pts)
    sx1 = max(p.x for p in world_pts)

    sy0 = min(p.y for p in world_pts)
    sy1 = max(p.y for p in world_pts)

    sw = sx1 - sx0
    sh = sy1 - sy0

    if sw < 1e-12 or sh < 1e-12:

        raise RuntimeError(
            "Mesh/Plane must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + mu
    tx1 = ux1 - mu

    ty0 = uy0 + mv
    ty1 = uy1 - mv

    su = (tx1 - tx0) / sw
    sv = (ty1 - ty0) / sh

    if props.keep_aspect:

        s = min(
            su,
            sv
        )

        su = s
        sv = s

    scx = (sx0 + sx1) / 2
    scy = (sy0 + sy1) / 2

    tcx = (tx0 + tx1) / 2
    tcy = (ty0 + ty1) / 2

    new_positions = []
    vertex_valid = []

    for p in world_pts:

        u = tcx + (p.x - scx) * su
        v = tcy + (p.y - scy) * sv

        if props.flip_v:
            v = 1.0 - v

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                (u, v),
                triangles
            )

        # ----------------------------------------------------
        # Margin check
        # ----------------------------------------------------

        inside = (
            inside
            and
            clip_uv_to_bounds(
                (u, v),
                uv_bounds,
                mu,
                mv
            )
        )

        pos = None

        if inside:

            pos, _ = uv_to_position(
                (u, v),
                triangles,
                props.use_nearest
            )

        if pos is None:

            vertex_valid.append(False)

            new_positions.append(
                Vector((0, 0, 0))
            )

        else:

            vertex_valid.append(True)

            new_positions.append(pos)

    # --------------------------------------------------------
    # Face validation
    # --------------------------------------------------------

    face_valid = []

    for poly in src.polygons:

        verts = list(poly.vertices)

        valid = (
            len(verts) >= 3
            and
            all(
                vertex_valid[i]
                for i in verts
            )
        )

        face_valid.append(valid)

    if not any(face_valid):

        raise RuntimeError(
            "No faces remain inside UV area. "
            "Try reducing margin or increasing plane subdivision."
        )

    # --------------------------------------------------------
    # BMesh
    # --------------------------------------------------------

    bm = bmesh.new()

    try:

        bm.from_mesh(src)

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        # Move valid vertices
        for i, pos in enumerate(
            new_positions
        ):

            if (
                vertex_valid[i]
                and
                i < len(bm.verts)
            ):

                bm.verts[i].co = (
                    target.matrix_world.inverted()
                    @ pos
                )

        # Delete invalid faces
        faces_to_delete = []

        for face in bm.faces:

            delete = False

            for v in face.verts:

                if not vertex_valid[v.index]:

                    delete = True
                    break

            if delete:
                faces_to_delete.append(face)

        if faces_to_delete:

            bmesh.ops.delete(
                bm,
                geom=faces_to_delete,
                context="FACES"
            )

        # Remove loose invalid vertices
        bm.verts.ensure_lookup_table()

        invalid_verts = [
            v
            for v in bm.verts
            if v.index < len(vertex_valid)
            and not vertex_valid[v.index]
            and not v.link_faces
        ]

        if invalid_verts:

            bmesh.ops.delete(
                bm,
                geom=invalid_verts,
                context="VERTS"
            )

        # Merge doubles
        if props.preserve_edges:

            bmesh.ops.remove_doubles(
                bm,
                verts=bm.verts,
                dist=0.0001
            )

        bm.to_mesh(src)
        src.update()

    finally:

        bm.free()

    return source


# ============================================================
# CURVE -> MESH CUT
# ============================================================

def cut_mesh_with_uv_for_curve_improved(
    target,
    source,
    props,
    triangles,
    uv_bounds
):

    src = source.data

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds
    )

    world_matrix = source.matrix_world

    world_pts = [
        world_matrix @ v.co
        for v in src.vertices
    ]

    if not world_pts:

        raise RuntimeError(
            "Curve mesh contains no vertices."
        )

    sx0 = min(p.x for p in world_pts)
    sx1 = max(p.x for p in world_pts)

    sy0 = min(p.y for p in world_pts)
    sy1 = max(p.y for p in world_pts)

    sw = sx1 - sx0
    sh = sy1 - sy0

    if sw < 1e-12 or sh < 1e-12:

        raise RuntimeError(
            "Curve must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + mu
    tx1 = ux1 - mu

    ty0 = uy0 + mv
    ty1 = uy1 - mv

    su = (tx1 - tx0) / sw
    sv = (ty1 - ty0) / sh

    if props.keep_aspect:

        s = min(
            su,
            sv
        )

        su = s
        sv = s

    scx = (sx0 + sx1) / 2
    scy = (sy0 + sy1) / 2

    tcx = (tx0 + tx1) / 2
    tcy = (ty0 + ty1) / 2

    target_mesh = target.data

    target_world_pts = [
        target.matrix_world @ v.co
        for v in target_mesh.vertices
    ]

    vertex_valid = []
    new_positions = []

    for p in target_world_pts:

        u = tcx + (p.x - scx) * su
        v = tcy + (p.y - scy) * sv

        if props.flip_v:
            v = 1.0 - v

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                (u, v),
                triangles
            )

        inside = (
            inside
            and
            clip_uv_to_bounds(
                (u, v),
                uv_bounds,
                mu,
                mv
            )
        )

        pos = None

        if inside:

            pos, _ = uv_to_position(
                (u, v),
                triangles,
                props.use_nearest
            )

        if pos is None:

            vertex_valid.append(False)

            new_positions.append(
                Vector((0, 0, 0))
            )

        else:

            vertex_valid.append(True)

            new_positions.append(pos)

    if not any(vertex_valid):

        raise RuntimeError(
            "No target vertices remain inside UV area."
        )

    bm = bmesh.new()

    try:

        bm.from_mesh(target_mesh)

        bm.verts.ensure_lookup_table()
        bm.faces.ensure_lookup_table()

        target_inverse = (
            target.matrix_world.inverted()
        )

        for i, pos in enumerate(
            new_positions
        ):

            if (
                vertex_valid[i]
                and
                i < len(bm.verts)
            ):

                bm.verts[i].co = (
                    target_inverse @ pos
                )

        faces_to_delete = []

        for face in bm.faces:

            delete = False

            for v in face.verts:

                if not vertex_valid[v.index]:

                    delete = True
                    break

            if delete:

                faces_to_delete.append(face)

        if faces_to_delete:

            bmesh.ops.delete(
                bm,
                geom=faces_to_delete,
                context="FACES"
            )

        bm.verts.ensure_lookup_table()

        invalid_verts = [
            v
            for v in bm.verts
            if v.index < len(vertex_valid)
            and not vertex_valid[v.index]
            and not v.link_faces
        ]

        if invalid_verts:

            bmesh.ops.delete(
                bm,
                geom=invalid_verts,
                context="VERTS"
            )

        if props.preserve_edges:

            bmesh.ops.remove_doubles(
                bm,
                verts=bm.verts,
                dist=0.0001
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

    temp_obj = None
    temp_mesh = None

    try:

        temp_mesh = bpy.data.meshes.new_from_object(
            curve_obj,
            preserve_all_data_layers=False,
            depsgraph=bpy.context.evaluated_depsgraph_get()
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

        result = cut_mesh_with_uv_for_curve_improved(
            target,
            temp_obj,
            props,
            triangles,
            uv_bounds
        )

        bpy.data.objects.remove(
            temp_obj,
            do_unlink=True
        )

        return result

    except Exception as e:

        if temp_obj:

            try:
                bpy.data.objects.remove(
                    temp_obj,
                    do_unlink=True
                )
            except:
                pass

        elif temp_mesh:

            try:
                bpy.data.meshes.remove(
                    temp_mesh,
                    do_unlink=True
                )
            except:
                pass

        raise RuntimeError(
            f"Failed to cut with Curve: {e}"
        )


# ============================================================
# UV FLAT / BOUNDARY
# ============================================================

def get_uv_flat_collection():

    col = bpy.data.collections.get(
        UV_FLAT_COLLECTION_NAME
    )

    if col is None:

        col = bpy.data.collections.new(
            UV_FLAT_COLLECTION_NAME
        )

        bpy.context.scene.collection.children.link(
            col
        )

    return col


def create_uv_flat_mesh(
    target,
    offset_z=0.01
):
    """
    Creates ONLY UV boundary edges.

    Internal UV mesh edges are NOT created.

    Multiple UV islands are supported.
    """

    mesh = target.data

    if not mesh.uv_layers:

        raise RuntimeError(
            "Target has no UV layers."
        )

    if (
        len(mesh.vertices) == 0
        or
        len(mesh.polygons) == 0
    ):

        raise RuntimeError(
            "Target mesh is empty."
        )

    uv_layer = mesh.uv_layers.active

    mesh.calc_loop_triangles()

    # --------------------------------------------------------
    # Build UV edge usage
    # --------------------------------------------------------

    edge_usage = {}

    def quantize_uv(
        p,
        precision=8
    ):

        return (
            round(float(p[0]), precision),
            round(float(p[1]), precision)
        )

    for tri in mesh.loop_triangles:

        if len(tri.loops) != 3:
            continue

        uv_tri = []

        for li in tri.loops:

            uv = uv_layer.data[li].uv

            uv_tri.append(
                quantize_uv((
                    uv.x,
                    uv.y
                ))
            )

        edges = [
            (uv_tri[0], uv_tri[1]),
            (uv_tri[1], uv_tri[2]),
            (uv_tri[2], uv_tri[0])
        ]

        for a, b in edges:

            if a == b:
                continue

            key = tuple(
                sorted((a, b))
            )

            edge_usage[key] = (
                edge_usage.get(key, 0) + 1
            )

    # --------------------------------------------------------
    # Boundary only
    # --------------------------------------------------------

    boundary_edges = [
        edge
        for edge, count in edge_usage.items()
        if count == 1
    ]

    if not boundary_edges:

        raise RuntimeError(
            "No UV boundary edges found."
        )

    # --------------------------------------------------------
    # UV bounds
    # --------------------------------------------------------

    uv_values = []

    for a, b in boundary_edges:

        uv_values.append(a)
        uv_values.append(b)

    min_u = min(
        p[0]
        for p in uv_values
    )

    max_u = max(
        p[0]
        for p in uv_values
    )

    min_v = min(
        p[1]
        for p in uv_values
    )

    max_v = max(
        p[1]
        for p in uv_values
    )

    uv_width = max(
        max_u - min_u,
        1e-9
    )

    uv_height = max(
        max_v - min_v,
        1e-9
    )

    # --------------------------------------------------------
    # Target world bounds
    # --------------------------------------------------------

    world_vertices = [
        target.matrix_world @ v.co
        for v in mesh.vertices
    ]

    min_x = min(
        v.x
        for v in world_vertices
    )

    max_x = max(
        v.x
        for v in world_vertices
    )

    min_y = min(
        v.y
        for v in world_vertices
    )

    max_y = max(
        v.y
        for v in world_vertices
    )

    world_width = max(
        max_x - min_x,
        1e-6
    )

    world_height = max(
        max_y - min_y,
        1e-6
    )

    # --------------------------------------------------------
    # Same physical size
    # --------------------------------------------------------

    scale = min(
        world_width / uv_width,
        world_height / uv_height
    )

    uv_center = Vector((
        (min_u + max_u) * 0.5,
        (min_v + max_v) * 0.5
    ))

    # --------------------------------------------------------
    # Create vertices
    # --------------------------------------------------------

    vertex_map = {}
    vertices = []

    def get_vertex(uv):

        key = quantize_uv(uv)

        if key in vertex_map:

            return vertex_map[key]

        u, v = uv

        local_pos = Vector((
            (u - uv_center.x) * scale,
            (v - uv_center.y) * scale,
            offset_z
        ))

        world_pos = (
            target.matrix_world
            @ local_pos
        )

        index = len(vertices)

        vertices.append(
            tuple(world_pos)
        )

        vertex_map[key] = index

        return index

    # --------------------------------------------------------
    # ONLY edges
    # --------------------------------------------------------

    edges = []

    for uv_a, uv_b in boundary_edges:

        a = get_vertex(uv_a)
        b = get_vertex(uv_b)

        if a != b:

            edges.append((
                a,
                b
            ))

    # --------------------------------------------------------
    # Create mesh
    # --------------------------------------------------------

    new_mesh = bpy.data.meshes.new(
        f"{target.name}_UV_Boundary"
    )

    # NO FACES
    new_mesh.from_pydata(
        vertices,
        edges,
        []
    )

    new_mesh.update()

    obj = bpy.data.objects.new(
        f"{target.name}_UV_Boundary",
        new_mesh
    )

    # Vertices already in world space
    obj.matrix_world = Matrix.Identity(4)

    col = get_uv_flat_collection()

    col.objects.link(obj)

    obj.display_type = "WIRE"
    obj.show_wire = True
    obj.show_all_edges = True

    return obj


# ============================================================
# LEGACY CURVE OUTPUT
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

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds
    )

    mapped = []

    for s in normalized:

        current = []

        for uv in s["points"]:

            if props.flip_v:

                uv = (
                    uv[0],
                    1.0 - uv[1]
                )

            inside_box = clip_uv_to_bounds(
                uv,
                uv_bounds,
                mu,
                mv
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

                pos, _ = uv_to_position(
                    uv,
                    triangles,
                    props.use_nearest
                )

                if pos is not None:

                    current.append(pos)

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
                    s["cyclic"]
                    and
                    len(mapped) == 0
                )
            })

    if not mapped:

        raise RuntimeError(
            "Curve completely outside UV area after clipping."
        )

    return mapped


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

    out = bpy.data.objects.new(
        f"UV_{name}",
        data
    )

    get_output_collection().objects.link(
        out
    )

    out.matrix_world = (
        target.matrix_world.copy()
    )

    inverse = target.matrix_world.inverted()

    for s in mapped:

        if len(s["points"]) < 2:
            continue

        sp = data.splines.new(
            "POLY"
        )

        sp.points.add(
            len(s["points"]) - 1
        )

        for i, p in enumerate(
            s["points"]
        ):

            local_p = inverse @ p

            sp.points[i].co = (
                local_p.x,
                local_p.y,
                local_p.z,
                1.0
            )

        sp.use_cyclic_u = (
            s["cyclic"]
        )

    return out


# ============================================================
# LEGACY MESH OUTPUT
# ============================================================

def create_projected_mesh_legacy(
    target,
    source,
    props,
    triangles,
    uv_bounds
):

    src = source.data

    mu, mv = estimate_uv_margin(
        props,
        uv_bounds
    )

    world_pts = [
        source.matrix_world @ v.co
        for v in src.vertices
    ]

    sx0 = min(p.x for p in world_pts)
    sx1 = max(p.x for p in world_pts)

    sy0 = min(p.y for p in world_pts)
    sy1 = max(p.y for p in world_pts)

    sw = sx1 - sx0
    sh = sy1 - sy0

    if sw < 1e-12 or sh < 1e-12:

        raise RuntimeError(
            "Mesh/Plane must have area in X/Y."
        )

    ux0, ux1, uy0, uy1 = uv_bounds

    tx0 = ux0 + mu
    tx1 = ux1 - mu

    ty0 = uy0 + mv
    ty1 = uy1 - mv

    su = (tx1 - tx0) / sw
    sv = (ty1 - ty0) / sh

    if props.keep_aspect:

        s = min(
            su,
            sv
        )

        su = s
        sv = s

    scx = (sx0 + sx1) / 2
    scy = (sy0 + sy1) / 2

    tcx = (tx0 + tx1) / 2
    tcy = (ty0 + ty1) / 2

    new_verts = []
    valid = []

    for p in world_pts:

        u = tcx + (p.x - scx) * su
        v = tcy + (p.y - scy) * sv

        if props.flip_v:

            v = 1.0 - v

        inside = True

        if props.clip_outside_uv:

            inside = uv_point_inside(
                (u, v),
                triangles
            )

        inside = (
            inside
            and
            clip_uv_to_bounds(
                (u, v),
                uv_bounds,
                mu,
                mv
            )
        )

        pos = None

        if inside:

            pos, _ = uv_to_position(
                (u, v),
                triangles,
                props.use_nearest
            )

        if pos is None:

            valid.append(False)

            new_verts.append(
                (0.0, 0.0, 0.0)
            )

        else:

            valid.append(True)

            local_pos = (
                target.matrix_world.inverted()
                @ pos
            )

            new_verts.append(
                tuple(local_pos)
            )

    new_faces = []

    for poly in src.polygons:

        verts = list(
            poly.vertices
        )

        if (
            len(verts) >= 3
            and
            all(
                valid[i]
                for i in verts
            )
        ):

            new_faces.append(
                verts
            )

    if not new_faces:

        raise RuntimeError(
            "No faces remain inside UV area."
        )

    mesh = bpy.data.meshes.new(
        f"UV_{source.name}"
    )

    mesh.from_pydata(
        new_verts,
        [],
        new_faces
    )

    mesh.update()

    out = bpy.data.objects.new(
        f"UV_{source.name}",
        mesh
    )

    get_output_collection().objects.link(
        out
    )

    out.matrix_world = (
        target.matrix_world.copy()
    )

    return out


# ============================================================
# COLLECTION
# ============================================================

def get_output_collection():

    col = bpy.data.collections.get(
        OUTPUT_COLLECTION_NAME
    )

    if col is None:

        col = bpy.data.collections.new(
            OUTPUT_COLLECTION_NAME
        )

        bpy.context.scene.collection.children.link(
            col
        )

    return col


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
            "Removes any part outside "
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
            "Finds nearest triangle "
            "for edge points"
        ),
        default=True
    )

    # --------------------------------------------------------
    # NEW MARGIN SWITCH
    # --------------------------------------------------------

    use_margin: BoolProperty(
        name="Enable Edge Margin",
        description=(
            "Enable or disable the UV edge margin"
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
                "Margin as percentage of UV"
            ),
            (
                "MM",
                "Millimeters",
                "Estimate margin in millimeters"
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
            "Cuts the target or source mesh "
            "directly instead of creating a new object"
        ),
        default=True
    )

    preserve_edges: BoolProperty(
        name="Preserve Edges",
        description=(
            "Preserves edge structure "
            "to prevent deformation"
        ),
        default=True
    )


# ============================================================
# PROJECT OPERATOR
# ============================================================

class UVPROJECTOR_OT_project(
    bpy.types.Operator
):

    bl_idname = "uv_projector.project"

    bl_label = "Project to UV Surface"

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(
        self,
        context
    ):

        props = (
            context.scene.uv_projector
        )

        target = props.target

        if (
            not target
            or
            target.type != "MESH"
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

        except Exception as e:

            self.report(
                {"ERROR"},
                str(e)
            )

            return {"CANCELLED"}

        sources = [
            o
            for o in context.selected_objects
            if o != target
            and (
                (
                    props.source_type == "CURVE"
                    and
                    o.type == "CURVE"
                )
                or
                (
                    props.source_type == "PLANE"
                    and
                    o.type == "MESH"
                )
                or
                (
                    props.source_type == "AUTO"
                    and
                    o.type in {
                        "CURVE",
                        "MESH"
                    }
                )
            )
        ]

        if not sources:

            self.report(
                {"ERROR"},
                "Select a Curve or Plane/Mesh with the Target."
            )

            return {"CANCELLED"}

        ok = 0
        fail = 0

        print(
            "\n"
            + "=" * 70
        )

        print(
            "UV SURFACE PROJECTOR PRO"
        )

        print(
            "=" * 70
        )

        print(
            "Edge Margin:",
            "ON"
            if props.use_margin
            else "OFF"
        )

        for source in sources:

            try:

                if source.type == "CURVE":

                    if props.cut_target:

                        cut_mesh_with_uv_for_curve_improved(
                            target,
                            source,
                            props,
                            triangles,
                            uv_bounds
                        )

                    else:

                        mapped = process_curve_legacy(
                            target,
                            source,
                            props,
                            triangles,
                            uv_bounds
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

                ok += 1

                print(
                    f"[OK] {source.name} - "
                    f"Cut successfully"
                )

            except Exception as e:

                fail += 1

                print(
                    f"[FAILED] "
                    f"{source.name}: "
                    f"{type(e).__name__}: {e}"
                )

                import traceback

                traceback.print_exc()

        print(
            f"Finished | "
            f"Success: {ok} | "
            f"Failed: {fail}"
        )

        print(
            "=" * 70
        )

        self.report(
            {"INFO"},
            f"Completed: {ok} succeeded, {fail} failed."
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
        "Create only the outer UV boundary "
        "with correct real-world size"
    )

    bl_options = {
        "REGISTER",
        "UNDO"
    }

    def execute(
        self,
        context
    ):

        props = (
            context.scene.uv_projector
        )

        target = props.target

        if (
            not target
            or
            target.type != "MESH"
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

        # Remove previous boundary
        col = bpy.data.collections.get(
            UV_FLAT_COLLECTION_NAME
        )

        if col:

            for obj in list(col.objects):

                bpy.data.objects.remove(
                    obj,
                    do_unlink=True
                )

        try:

            create_uv_flat_mesh(
                target,
                offset_z=0.01
            )

            self.report(
                {"INFO"},
                f"UV boundary created for '{target.name}'."
            )

        except Exception as e:

            self.report(
                {"ERROR"},
                f"Failed to create UV boundary: {e}"
            )

            return {"CANCELLED"}

        return {"FINISHED"}


# ============================================================
# CLEAR UV BOUNDARY
# ============================================================

class UVPROJECTOR_OT_clear_uv_flat(
    bpy.types.Operator
):

    bl_idname = (
        "uv_projector.clear_uv_flat"
    )

    bl_label = "Clear UV Boundary"

    def execute(
        self,
        context
    ):

        col = bpy.data.collections.get(
            UV_FLAT_COLLECTION_NAME
        )

        if col:

            for obj in list(col.objects):

                bpy.data.objects.remove(
                    obj,
                    do_unlink=True
                )

        self.report(
            {"INFO"},
            "UV boundary cleared."
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

    def execute(
        self,
        context
    ):

        col = bpy.data.collections.get(
            OUTPUT_COLLECTION_NAME
        )

        if col:

            for obj in list(col.objects):

                bpy.data.objects.remove(
                    obj,
                    do_unlink=True
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

        p = (
            context.scene.uv_projector
        )

        # ----------------------------------------------------
        # Target
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Target Surface",
            icon="MESH_DATA"
        )

        box.prop(
            p,
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
            p,
            "source_type",
            expand=True
        )

        # ----------------------------------------------------
        # Cut Mode
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Cut Mode (Knife)",
            icon="SCULPTMODE_HLT"
        )

        box.prop(
            p,
            "cut_target",
            text="Cut Instead of New Object"
        )

        box.prop(
            p,
            "preserve_edges",
            text="Preserve Edges"
        )

        # ----------------------------------------------------
        # UV Clipping
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="UV Clipping",
            icon="UV"
        )

        box.prop(
            p,
            "clip_outside_uv"
        )

        box.prop(
            p,
            "keep_aspect"
        )

        box.prop(
            p,
            "flip_v"
        )

        box.prop(
            p,
            "use_nearest"
        )

        # ----------------------------------------------------
        # Edge Margin
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Edge Margin",
            icon="MOD_OFFSET"
        )

        # Main ON/OFF switch
        box.prop(
            p,
            "use_margin",
            text="Enable Edge Margin"
        )

        # Disable controls when margin is OFF
        row = box.row()

        row.enabled = p.use_margin

        row.prop(
            p,
            "margin_mode"
        )

        row = box.row()

        row.enabled = p.use_margin

        row.prop(
            p,
            "margin_value"
        )

        if not p.use_margin:

            box.label(
                text="Margin disabled - full UV area used",
                icon="CHECKMARK"
            )

        elif p.margin_mode == "UV":

            box.label(
                text="Example: 0.002 = small UV margin"
            )

        elif p.margin_mode == "PERCENT":

            box.label(
                text="Example: 1 = 1% of UV area"
            )

        else:

            box.label(
                text="MM uses target dimensions"
            )

        # ----------------------------------------------------
        # Curve
        # ----------------------------------------------------

        box = layout.box()

        box.label(
            text="Curve",
            icon="CURVE_DATA"
        )

        box.prop(
            p,
            "curve_samples"
        )

        box.prop(
            p,
            "bevel_depth"
        )

        box.prop(
            p,
            "bevel_resolution"
        )

        # ----------------------------------------------------
        # Project
        # ----------------------------------------------------

        row = layout.row()

        row.scale_y = 1.5

        row.operator(
            "uv_projector.project",
            icon="MOD_SHRINKWRAP"
        )

        # ----------------------------------------------------
        # UV Boundary
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
        # Clear
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

