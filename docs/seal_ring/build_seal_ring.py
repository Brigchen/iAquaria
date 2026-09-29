# iAqua 密封圈：环状，径向切面中间低、两边高。1 BU = 1 mm
# A: 内 68.5 / 外 75.5；B: 内 68.75 / 外 75.25。其余相同。

import math
import os

import bmesh
import bpy
from mathutils import Euler, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_SealRing.blend")
COL = "iAqua_SealRing"

D_VALLEY = 72.0
H_EDGE = 3.0
H_VALLEY = 2.0
SPIN_SEGS = 96
PROFILE_SEGS = 20
PARK_Y = 90.0
CAP_Y = -90.0

# 帽形密封件（长轴剖面如图）：旋成后再压成椭圆
CAP_LONG = 22.0
CAP_SHORT = 11.0
CAP_CAVITY = 10.0
CAP_HOLE = 8.0
CAP_H_OLD = 5.0
CAP_FLANGE_T = 1.0
CAP_WALL = 1.6  # 全周帽壁向外加厚；内腔不变
CAP_HAT = CAP_CAVITY + 2.0 * CAP_WALL  # 13.2
CAP_SPIN = 80
CAP_ARC = 12
# 腔内/底孔仍按 22×11 比例
CAP_CAVITY_S = CAP_CAVITY * CAP_SHORT / CAP_LONG  # 5.0
CAP_HOLE_S = CAP_HOLE * CAP_SHORT / CAP_LONG  # 4.0
CAP_HAT_S = CAP_CAVITY_S + 2.0 * CAP_WALL  # 8.2
CAP_FILLET_R = min(1.0, CAP_WALL * 0.6)
CAP_CAV_Z1 = CAP_H_OLD - 1.0 - 0.2  # 原腔内顶 z=3.8，保持不变
CAP_H = CAP_CAV_Z1 + CAP_WALL  # 顶壁 1.6，总高 5.4

RINGS = [
    {"name": "SealRing", "stl": "SealRing.stl", "d_in": 68.5, "d_out": 75.5, "y": 0.0, "rgba": (0.18, 0.18, 0.20, 1.0)},
    {
        "name": "SealRing_B",
        "stl": "SealRing_68.75.stl",
        "d_in": 68.75,
        "d_out": 75.25,
        "y": PARK_Y,
        "rgba": (0.22, 0.28, 0.32, 1.0),
    },
]


def mm_units():
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def col():
    if COL not in bpy.data.collections:
        c = bpy.data.collections.new(COL)
        bpy.context.scene.collection.children.link(c)
    return bpy.data.collections[COL]


def link_obj(o, c):
    if o.name not in c.objects:
        c.objects.link(o)
    sc = bpy.context.scene.collection
    if o.name in sc.objects:
        sc.objects.unlink(o)


def mat(o, rgba):
    n = "SealRing_" + o.name
    mt = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.55
    o.data.materials.clear()
    o.data.materials.append(mt)


def z_top(r, r_valley, r_out):
    """直径 72 mm 最低 2 mm，内外沿 3 mm，二次曲线。"""
    dr = r_out - r_valley
    return H_VALLEY + (H_EDGE - H_VALLEY) * ((r - r_valley) / dr) ** 2


def clear_seal():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and (o.name.startswith("SealRing") or o.name.startswith("SealCap")):
            bpy.data.objects.remove(o, do_unlink=True)


def build_ring(c, spec):
    r_in = spec["d_in"] / 2.0
    r_out = spec["d_out"] / 2.0
    r_valley = D_VALLEY / 2.0
    prof = [(r_in, 0.0), (r_out, 0.0), (r_out, H_EDGE)]
    for i in range(1, PROFILE_SEGS):
        t = i / PROFILE_SEGS
        r = r_out + (r_in - r_out) * t
        prof.append((r, z_top(r, r_valley, r_out)))
    prof.append((r_in, H_EDGE))

    bm = bmesh.new()
    vs = [bm.verts.new((x, 0.0, z)) for x, z in prof]
    n = len(vs)
    for i in range(n):
        bm.edges.new((vs[i], vs[(i + 1) % n]))
    geom = list(bm.verts) + list(bm.edges)
    bmesh.ops.spin(
        bm,
        geom=geom,
        cent=(0.0, 0.0, 0.0),
        axis=(0.0, 0.0, 1.0),
        angle=2.0 * math.pi,
        steps=SPIN_SEGS,
        use_duplicate=False,
    )
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.0004)
    holes = [e for e in bm.edges if e.is_boundary]
    if holes:
        bmesh.ops.bridge_loops(bm, edges=holes)

    me = bpy.data.meshes.new(spec["name"])
    bm.to_mesh(me)
    bm.free()
    me.validate()
    o = bpy.data.objects.new(spec["name"], me)
    link_obj(o, c)
    o.location.y = spec["y"]
    mat(o, spec["rgba"])
    return o


def make_ellipse_cyl(c, name, rx, ry, z0, z1, segs=80):
    bm = bmesh.new()
    rings = []
    for z in (z0, z1):
        ring = []
        for i in range(segs):
            a = 2.0 * math.pi * i / segs
            ring.append(bm.verts.new((rx * math.cos(a), ry * math.sin(a), z)))
        rings.append(ring)
    for i in range(segs):
        a, b = rings[0][i], rings[0][(i + 1) % segs]
        d, e = rings[1][i], rings[1][(i + 1) % segs]
        bm.faces.new((a, b, e, d))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[1])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.validate()
    o = bpy.data.objects.new(name, me)
    link_obj(o, c)
    return o


def bake_bool(host, others, op, solver="EXACT"):
    for i, ot in enumerate(others):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = op
        mod.solver = solver
        mod.object = ot
        ot.hide_set(True)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = host.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = host.data
    host.modifiers.clear()
    host.data = baked
    bpy.data.meshes.remove(old)
    baked.validate()
    for ot in others:
        md = ot.data
        bpy.data.objects.remove(ot, do_unlink=True)
        if md.users == 0:
            bpy.data.meshes.remove(md)


def build_cap(c):
    """内腔 10×5 / 底孔 8×4 不变；帽壁向外加到 1.6 mm。"""
    flange = make_ellipse_cyl(c, "_cap_fl", CAP_LONG / 2.0, CAP_SHORT / 2.0, 0.0, CAP_FLANGE_T)
    hat = make_ellipse_cyl(c, "_cap_hat", CAP_HAT / 2.0, CAP_HAT_S / 2.0, CAP_FLANGE_T - 0.05, CAP_H)
    bake_bool(flange, [hat], "UNION", "FLOAT")
    # 顶外沿倒圆
    bm = bmesh.new()
    bm.from_mesh(flange.data)
    bm.edges.ensure_lookup_table()
    top = []
    for e in bm.edges:
        if abs(e.verts[0].co.z - CAP_H) > 0.02 or abs(e.verts[1].co.z - CAP_H) > 0.02:
            continue
        mid = (e.verts[0].co + e.verts[1].co) * 0.5
        if (mid.x / (CAP_HAT / 2.0)) ** 2 + (mid.y / (CAP_HAT_S / 2.0)) ** 2 > 0.75:
            top.append(e)
    if top:
        bmesh.ops.bevel(bm, geom=top, offset=CAP_FILLET_R, segments=CAP_ARC, affect="EDGES")
    bm.to_mesh(flange.data)
    flange.data.update()
    bm.free()
    cav = make_ellipse_cyl(c, "_cap_cav", CAP_CAVITY / 2.0, CAP_CAVITY_S / 2.0, CAP_FLANGE_T - 0.02, CAP_CAV_Z1)
    hole = make_ellipse_cyl(c, "_cap_hole", CAP_HOLE / 2.0, CAP_HOLE_S / 2.0, -0.2, CAP_FLANGE_T + 0.15)
    bake_bool(flange, [cav, hole], "DIFFERENCE", "FLOAT")
    bm = bmesh.new()
    bm.from_mesh(flange.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0006)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0006, edges=bm.edges)
    wires = [v for v in bm.verts if not v.link_faces]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="VERTS")
    loose = [e for e in bm.edges if e.is_wire]
    if loose:
        bmesh.ops.delete(bm, geom=loose, context="EDGES")
    bm.to_mesh(flange.data)
    flange.data.update()
    flange.data.validate()
    bm.free()
    flange.name = "SealCap"
    mat(flange, (0.16, 0.20, 0.26, 1.0))
    flange.location.y = CAP_Y
    return flange


def frame():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "OBJECT"
        sp.overlay.show_object_origins = False
        r = sp.region_3d
        r.view_location = Vector((0.0, CAP_Y, 2.0))
        r.view_distance = 55.0
        r.view_rotation = Euler((math.radians(58), 0.0, math.radians(40)), "XYZ").to_quaternion()


def export_stl():
    out = []
    for spec in RINGS:
        o = bpy.data.objects.get(spec["name"])
        if not o:
            continue
        loc = o.location.copy()
        o.location = (0.0, 0.0, 0.0)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, spec["stl"]), export_selected_objects=True)
        o.location = loc
        out.append(spec["stl"])
    cap = bpy.data.objects.get("SealCap")
    if cap:
        loc = cap.location.copy()
        bpy.ops.object.select_all(action="DESELECT")
        cap.select_set(True)
        bpy.context.view_layer.objects.active = cap
        cap.location = (0.0, 0.0, 0.0)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, "SealCap.stl"), export_selected_objects=True)
        cap.location = loc
        out.append("SealCap.stl")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_seal()
    c = col()
    for spec in RINGS:
        build_ring(c, spec)
    build_cap(c)
    frame()
    return export_stl()


if __name__ == "__main__" or True:
    RESULT = {
        "stl": build(),
        "rings": [(s["name"], s["d_in"], s["d_out"]) for s in RINGS],
        "cap": (CAP_LONG, CAP_SHORT, CAP_H, CAP_HAT, CAP_HAT_S, CAP_WALL, CAP_CAVITY, CAP_CAVITY_S),
    }
