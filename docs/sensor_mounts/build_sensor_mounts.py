# iAqua sensor mounts — parametric mm geometry (Blender 5.x, 1 BU = 1 mm)
# See dimensions.md for drawing callouts.

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_SensorMounts.blend")
GLB_PATH = os.path.join(OUT_DIR, "iAqua_SensorMounts.glb")
os.makedirs(STL_DIR, exist_ok=True)
COL = "iAqua_SensorMounts"

# ---------- strict constants (mm) ----------
PLATE_W, PLATE_H = 120.0, 100.0
OUTER_T, INNER_T = 8.0, 6.0
GLASS_T = 8.0

M4_HOLE = 4.4
M4_CB_D, M4_CB_DEPTH = 8.0, 4.2
M4_NUT_AF, M4_NUT_DEPTH = 7.8, 5.0
M4_PATTERN = [(-50, -40), (50, -40), (-50, 40), (50, 40)]

GROOVE_W, GROOVE_D, GROOVE_INSET = 2.0, 1.5, 5.0

PORTS = [
    ("TEMP", -30.0, 8.0, 6.4),
    ("PH", 0.0, 8.0, 12.5),
    ("TDS", 30.0, 8.0, 12.5),
    ("PG7", 0.0, -28.0, 12.5),
]

RAIL_W, RAIL_L, RAIL_T = 20.0, 128.0, 6.0
RAIL_TENON_L = 12.0
M3_HOLE, M3_CB_D, M3_CB_DEPTH = 2.9, 6.5, 3.2
M3_ZS = [18, 38, 58, 78, 98, 118]

CLIP_W, CLIP_D, CLIP_H = 42.0, 28.0, 26.0
JAW_GAP = 10.5
M5_HOLE, M5_NUT_AF, M5_NUT_DEPTH = 5.5, 9.0, 5.0
SLOT_W, SLOT_D = 20.0, 6.0

SR04_W, SR04_D, SR04_H = 45.0, 20.0, 15.0
GY30 = 16.5


def mm_units():
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def clear_meshes():
    for obj in list(bpy.data.objects):
        if obj.type == "MESH":
            bpy.data.objects.remove(obj, do_unlink=True)


def collection():
    if COL not in bpy.data.collections:
        c = bpy.data.collections.new(COL)
        bpy.context.scene.collection.children.link(c)
    return bpy.data.collections[COL]


def link_obj(obj, col):
    if obj.name not in col.objects:
        col.objects.link(obj)
    sc = bpy.context.scene.collection
    if obj.name in sc.objects:
        sc.objects.unlink(obj)


def new_mesh(name, col):
    m = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, m)
    link_obj(o, col)
    return o


def put_bm(obj, bm):
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def mat_obj(obj, rgba):
    mt = bpy.data.materials.get("SM_" + obj.name) or bpy.data.materials.new("SM_" + obj.name)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    obj.data.materials.clear()
    obj.data.materials.append(mt)


def box(w, d, h):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= w
        v.co.y *= d
        v.co.z *= h
    return bm


def cyl(r, h, segs=32):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=h, matrix=Matrix.Identity(4)
    )
    return bm


def hex_prism(af, depth, segs=6):
    """af = flat-to-flat for M4 nut 7.8 etc."""
    r = af / math.sqrt(3)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth, matrix=Matrix.Identity(4)
    )
    return bm


def bool_diff(host, cutters):
    if not cutters:
        return
    for i, c in enumerate(cutters):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "FLOAT"
        mod.object = c
        c.hide_set(True)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = host.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = host.data
    host.modifiers.clear()
    host.data = baked
    bpy.data.meshes.remove(old)
    for c in cutters:
        md = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        if md.users == 0:
            bpy.data.meshes.remove(md)


def cutter_box(name, col, w, d, h, loc, rot=(0, 0, 0)):
    o = new_mesh(name, col)
    put_bm(o, box(w, d, h))
    o.location = loc
    o.rotation_euler = Euler(rot, "XYZ")
    return o


def cutter_cyl(name, col, r, depth, loc, rot=(0, 0, 0)):
    o = new_mesh(name, col)
    put_bm(o, cyl(r, depth, 32))
    o.location = loc
    o.rotation_euler = Euler(rot, "XYZ")
    return o


def groove_cutters(col, y_face, sign=1):
    inner_w = PLATE_W - 2 * GROOVE_INSET
    inner_h = PLATE_H - 2 * GROOVE_INSET
    y0 = y_face
    ring = new_mesh("_gr_ring_tmp", col)
    put_bm(ring, box(PLATE_W, GROOVE_D, PLATE_H))
    ring.location = (0, y0 + sign * (GROOVE_D / 2), 0)
    inner2 = cutter_box("_gr_i2", col, inner_w, GROOVE_D + 1, inner_h, ring.location)
    bool_diff(ring, [inner2])
    return [ring]


def build_plate(col, name, thickness, glass_side_y, is_outer):
    """Plate in local coords: center origin, thickness along +Y from y=0."""
    o = new_mesh(name, col)
    put_bm(o, box(PLATE_W, thickness, PLATE_H))
    o.location = (0, 0, 0)
    cutters = []

    for i, (px, pz) in enumerate(M4_PATTERN):
        cutters.append(
            cutter_cyl(f"_{name}_m4_{i}", col, M4_HOLE / 2, thickness + 2, (px, 0, pz), (math.radians(90), 0, 0))
        )

    if is_outer:
        for i, (px, pz) in enumerate(M4_PATTERN):
            cutters.append(
                cutter_cyl(
                    f"_{name}_m4cb_{i}",
                    col,
                    M4_CB_D / 2,
                    M4_CB_DEPTH + 0.2,
                    (px, thickness / 2 - M4_CB_DEPTH / 2, pz),
                    (math.radians(90), 0, 0),
                )
            )
        gy = -thickness / 2 + GROOVE_D / 2
        cutters.extend(groove_cutters(col, gy, sign=-1))
    else:
        for i, (px, pz) in enumerate(M4_PATTERN):
            cutters.append(
                cutter_cyl(
                    f"_{name}_nut_{i}",
                    col,
                    M4_NUT_AF / math.sqrt(3),
                    M4_NUT_DEPTH + 0.2,
                    (px, -thickness / 2 + M4_NUT_DEPTH / 2, pz),
                    (math.radians(90), 0, 0),
                )
            )
        gy = -thickness / 2 + GROOVE_D / 2
        cutters.extend(groove_cutters(col, gy, sign=1))

    for i, (_, px, pz, pd) in enumerate(PORTS):
        cutters.append(
            cutter_cyl(f"_{name}_p_{i}", col, pd / 2, thickness + 2, (px, 0, pz), (math.radians(90), 0, 0))
        )

    bool_diff(o, cutters)
    # place in world: glass contact face
    o.location = (0, glass_side_y + thickness / 2, 0)
    mat_obj(o, (0.72, 0.74, 0.78, 1) if is_outer else (0.66, 0.68, 0.72, 1))
    return o


def build_drill_guide(col):
    g = new_mesh("DrillGuide", col)
    put_bm(g, box(PLATE_W, 3.0, PLATE_H))
    cutters = []
    for i, (px, pz) in enumerate(M4_PATTERN):
        cutters.append(cutter_cyl(f"_dg_m4_{i}", col, 2.1, 5, (px, 0, pz), (math.radians(90), 0, 0)))
    glass_d = [6.0, 12.0, 12.0, 12.5]
    for i, (_, px, pz, _) in enumerate(PORTS):
        cutters.append(cutter_cyl(f"_dg_p_{i}", col, glass_d[i] / 2, 5, (px, 0, pz), (math.radians(90), 0, 0)))
    bool_diff(g, cutters)
    g.location = (0, GLASS_T / 2 + 1.5, 0)
    mat_obj(g, (0.9, 0.75, 0.2, 1))
    return g


def build_gland(col):
    body = new_mesh("Gland_Body_6mm", col)
    put_bm(body, cyl(12.0, 8.0, 48))
    cutters = [
        cutter_cyl("_gb_bore", col, 6.4 / 2, 10, (0, 0, 0), (math.radians(90), 0, 0)),
        cutter_cyl("_gb_thread", col, 10.0 / 2, 14, (0, 4, 0), (math.radians(90), 0, 0)),
    ]
    bool_diff(body, cutters)
    body.location = (-30, GLASS_T / 2 + OUTER_T + 4, 8)
    mat_obj(body, (0.55, 0.56, 0.58, 1))

    ring = new_mesh("Gland_Ring_6mm", col)
    put_bm(ring, cyl(9.0, 4.0, 32))
    cutters = [cutter_cyl("_gr_b", col, 3.0 / 2, 6, (0, 0, 0), (math.radians(90), 0, 0))]
    bool_diff(ring, cutters)
    ring.location = (-30, GLASS_T / 2 + OUTER_T + 12, 8)
    mat_obj(ring, (0.5, 0.52, 0.54, 1))
    return body, ring


def build_rim_clip(col):
    base = new_mesh("RimClip_Base", col)
    put_bm(base, box(CLIP_W, CLIP_D, CLIP_H))
    cutters = []
    # rail slot on top
    cutters.append(cutter_box("_slot", col, SLOT_W, SLOT_D + 2, RAIL_TENON_L + 2, (0, -CLIP_D / 2 + SLOT_D / 2, CLIP_H / 2 - 3)))
    # jaw gap
    cutters.append(cutter_box("_gap", col, CLIP_W - 8, JAW_GAP, 16, (0, CLIP_D / 2 - JAW_GAP / 2 - 2, -2)))
    # M5 through fixed side
    cutters.append(cutter_cyl("_m5", col, M5_HOLE / 2, CLIP_W + 2, (0, 2, -4), (0, math.radians(90), 0)))
    bool_diff(base, cutters)
    base.location = (-70, 0, GLASS_T + 18)
    mat_obj(base, (0.62, 0.64, 0.68, 1))

    jaw = new_mesh("RimClip_Jaw", col)
    put_bm(jaw, box(14, 10, 18))
    cutters = [
        cutter_cyl("_jnut", col, M5_NUT_AF / math.sqrt(3), M5_NUT_DEPTH + 0.2, (0, 0, 4), (math.radians(90), 0, 0))
    ]
    bool_diff(jaw, cutters)
    jaw.location = (-70, 14, GLASS_T + 16)
    mat_obj(jaw, (0.58, 0.60, 0.64, 1))
    return base, jaw


def build_rail(col):
    r = new_mesh("VerticalRail", col)
    put_bm(r, box(RAIL_W, RAIL_T, RAIL_L))
    cutters = []
    for z in M3_ZS:
        zz = z - RAIL_L / 2
        cutters.append(cutter_cyl(f"_m3_{z}", col, M3_HOLE / 2, RAIL_T + 2, (0, 0, zz), (0, 0, 0)))
        cutters.append(
            cutter_cyl(
                f"_m3cb_{z}",
                col,
                M3_CB_D / 2,
                M3_CB_DEPTH + 0.2,
                (0, -RAIL_T / 2 + M3_CB_DEPTH / 2, zz),
                (0, 0, 0),
            )
        )
    # M4 heat-set for rail lock (printed hole 3.2 + user inserts nut)
    cutters.append(cutter_cyl("_m4lock", col, 3.2 / 2, 6, (8, 0, -RAIL_L / 2 + 6), (math.radians(90), 0, 0)))
    bool_diff(r, cutters)
    r.location = (-70, 0, GLASS_T + 18 + CLIP_H / 2 + RAIL_L / 2)
    mat_obj(r, (0.70, 0.72, 0.76, 1))
    return r


def build_sr04_mount(col):
    m = new_mesh("Mount_SR04", col)
    put_bm(m, box(48, 24, 8))
    cutters = [
        cutter_box("_cavity", col, SR04_W + 0.5, SR04_D + 0.5, SR04_H, (0, -2, 2)),
        cutter_box("_open", col, 46, 18, 20, (0, -6, 0)),
    ]
    for dz in (-10, 10):
        cutters.append(cutter_cyl(f"_ear_{dz}", col, M3_HOLE / 2, 10, (0, 3, dz), (math.radians(90), 0, 0)))
    bool_diff(m, cutters)
    m.location = (-70, 6, GLASS_T + 18 + CLIP_H / 2 + 95)
    m.rotation_euler = Euler((math.radians(90), 0, 0), "XYZ")
    mat_obj(m, (0.35, 0.48, 0.58, 1))
    return m


def build_bh1750_mount(col):
    m = new_mesh("Mount_BH1750", col)
    put_bm(m, box(22, 14, 12))
    cutters = [
        cutter_box("_c", col, GY30 + 0.4, GY30 + 0.4, 6, (0, 0, 2)),
        cutter_cyl("_wire", col, 2.0, 16, (0, -5, 0), (math.radians(90), 0, 0)),
    ]
    for dz in (-10, 10):
        cutters.append(cutter_cyl(f"_m3_{dz}", col, M3_HOLE / 2, 16, (0, 4, dz), (math.radians(90), 0, 0)))
    bool_diff(m, cutters)
    m.location = (-70, 8, GLASS_T + 18 + CLIP_H / 2 + 55)
    m.rotation_euler = Euler((math.radians(15), 0, 0), "XYZ")
    mat_obj(m, (0.40, 0.52, 0.48, 1))
    return m


def build_glass(col):
    g = new_mesh("GlassPanel", col)
    put_bm(g, box(200, GLASS_T, 160))
    g.location = (0, 0, 0)
    mat_obj(g, (0.5, 0.7, 0.85, 0.25))


def build_m4_bolts_demo(col):
    """Visual only — not exported."""
    bolts = []
    y0 = GLASS_T / 2 + OUTER_T
    for i, (px, pz) in enumerate(M4_PATTERN):
        b = new_mesh(f"M4_demo_{i}", col)
        put_bm(b, cyl(2.0, 45, 12))
        b.location = (px, y0, pz)
        b.rotation_euler = Euler((math.radians(90), 0, 0), "XYZ")
        mat_obj(b, (0.3, 0.3, 0.32, 1))
        bolts.append(b)
    return bolts


def purge_tmp():
    for obj in list(bpy.data.objects):
        if obj.name.startswith("_") or obj.name.startswith("M4_demo"):
            bpy.data.objects.remove(obj, do_unlink=True)


def build():
    mm_units()
    clear_meshes()
    c = collection()
    build_glass(c)
    y_outer = GLASS_T / 2
    y_inner = -GLASS_T / 2
    build_plate(c, "Bulkhead_Outer", OUTER_T, y_outer, True)
    build_plate(c, "Bulkhead_Inner", INNER_T, y_inner - INNER_T, False)
    build_drill_guide(c)
    build_gland(c)
    build_rim_clip(c)
    build_rail(c)
    build_sr04_mount(c)
    build_bh1750_mount(c)
    build_m4_bolts_demo(c)
    purge_tmp()
    frame_view()
    return [o.name for o in c.objects if o.type == "MESH"]


def frame_view():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "OBJECT"
        sp.overlay.show_object_origins = False
        r = sp.region_3d
        r.view_location = Vector((-10, 0, 55))
        r.view_distance = 340
        r.view_rotation = Euler((math.radians(56), 0, math.radians(48)), "XYZ").to_quaternion()


EXPORT = [
    "Bulkhead_Outer",
    "Bulkhead_Inner",
    "DrillGuide",
    "Gland_Body_6mm",
    "Gland_Ring_6mm",
    "RimClip_Base",
    "RimClip_Jaw",
    "VerticalRail",
    "Mount_SR04",
    "Mount_BH1750",
]


def export_stls():
    for name in EXPORT:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, f"{name}.stl"), export_selected_objects=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.export_scene.gltf(filepath=GLB_PATH, export_format="GLB")
    return sorted(os.listdir(STL_DIR))


if __name__ == "__main__" or True:
    parts = build()
    stl = export_stls()
    RESULT = {"parts": parts, "stl": stl}
