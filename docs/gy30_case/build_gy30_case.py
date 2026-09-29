# GY-30 外壳 — inset 挖腔（封闭盒，无通槽、无腔内布尔）
# PCB 32.6×15.1；板+芯片 3mm；左右内壁 1mm 托条高 8mm
# 走线：下壳顶边开口槽 + 上盖裙边底开口槽（先装板穿线，上盖仍能套入）
import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_GY30_Case.blend")
COL = "iAqua_GY30_Case"

PCB_L, PCB_W = 32.6, 15.1
BOARD_CHIP_H = 3.0
CHIP_FROM_TOP = 12.0
LIGHT_R, WIRE_R = 3.0, 3.0
M3_R = 1.6
HOLE_FROM_BODY = 10.0      # 孔心距体外沿，原 5，各外移 5
EAR_SEGS = 48
WALL, FLOOR = 1.4, 1.8
CLEAR, FIT = 0.5, 0.35
LID_WALL, LID_TOP, SKIRT = 1.4, 0.75, 8.0  # 顶厚减半，多进光
LEDGE_T, LEDGE_H = 1.0, 8.0
# 左右互配波浪：合盖同相嵌合；插入时错相过峰卡住
WAVE_AMP = 0.42
WAVE_N = 2.0
WAVE_EMBED = 0.90
SNAP_FIT = 0.12
WAVE_X_MARGIN = 2.4
WAVE_Z0 = 1.20
WAVE_Z1 = SKIRT - 0.85

INNER_L = PCB_L + 2 * CLEAR
INNER_W = PCB_W + 2 * CLEAR
INNER_H = LEDGE_H + BOARD_CHIP_H + 0.5
BASE_OUT_L = INNER_L + 2 * WALL
BASE_OUT_W = INNER_W + 2 * WALL
LID_IN_L = BASE_OUT_L + 2 * FIT
LID_IN_W = BASE_OUT_W + 2 * FIT
LID_OUT_L = LID_IN_L + 2 * LID_WALL
LID_OUT_W = LID_IN_W + 2 * LID_WALL
BASE_H = FLOOR + INNER_H
PCB_POCKET = INNER_H - LEDGE_H  # 托条以上到沿口
WIRE_Z = FLOOR + LEDGE_H  # 板面高度出线
ASSEMBLED_LID_Z = BASE_H - SKIRT  # 上盖内顶落在下壳沿口
# 底板两端半圆：圆心=固定孔，半径=板宽一半（多边形内接=板宽）
EAR_R = (BASE_OUT_W / 2.0) / math.cos(math.pi / EAR_SEGS)
EAR_EXT = HOLE_FROM_BODY + EAR_R

PCB_TOP_X = -PCB_L / 2
CHIP_X = PCB_TOP_X + CHIP_FROM_TOP


def mm_units():
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def collection():
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


def new_mesh(name, c):
    me = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, me)
    link_obj(o, c)
    return o


def mat(o, rgba):
    n = "GY30_" + o.name
    mt = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    o.data.materials.clear()
    o.data.materials.append(mt)


def clear_gy30():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith("GY30"):
            bpy.data.objects.remove(o, do_unlink=True)


def bm_to_obj(name, c, bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_mesh(name, c)
    bm.to_mesh(o.data)
    o.data.update()
    bm.free()
    return o


def cube_z0(sx, sy, sz):
    """原点在底面中心，+Z 向上的长方体。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
        v.co.z += sz / 2.0
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    return bm


def face_at_z(bm, z):
    bm.faces.ensure_lookup_table()
    bm.normal_update()
    cand = [f for f in bm.faces if abs(f.calc_center_median().z - z) < 0.08]
    if not cand:
        raise RuntimeError(f"no face at z={z}")
    return max(cand, key=lambda f: f.calc_area())


def open_pocket(bm, face, thickness, depth):
    """先水平内缩（竖直壁），再沿法向负方向挤出 depth，并删掉原面开口。"""
    bmesh.ops.inset_region(
        bm,
        faces=[face],
        thickness=thickness,
        depth=0.0,
        use_boundary=True,
        use_even_offset=True,
        use_interpolate=True,
        use_relative_offset=False,
        use_outset=False,
    )
    face.normal_update()
    n = face.normal.normalized()
    ret = bmesh.ops.extrude_face_region(bm, geom=[face])
    new_verts = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=new_verts, vec=-n * abs(depth))
    bmesh.ops.delete(bm, geom=[face], context="FACES")


def bool_exact(host, cutters, op="DIFFERENCE"):
    for i, ct in enumerate(cutters):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = op
        mod.solver = "EXACT"
        mod.object = ct
        ct.hide_set(True)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = host.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = host.data
    host.modifiers.clear()
    host.data = baked
    bpy.data.meshes.remove(old)
    baked.validate()
    for ct in cutters:
        md = ct.data
        bpy.data.objects.remove(ct, do_unlink=True)
        if md.users == 0:
            bpy.data.meshes.remove(md)


def cyl(c, name, r, depth, loc, rot, segs=32):
    o = new_mesh(name, c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth, matrix=Matrix.Identity(4)
    )
    bm.to_mesh(o.data)
    bm.free()
    o.location = loc
    o.rotation_euler = Euler(rot, "XYZ")
    return o


def box(c, name, sx, sy, sz, loc):
    o = new_mesh(name, c)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    bm.to_mesh(o.data)
    bm.free()
    o.location = loc
    return o


def wave_offset(z, z0, z1, amp=WAVE_AMP, n=WAVE_N):
    if z1 <= z0:
        return 0.0
    t = (z - z0) / (z1 - z0)
    t = max(0.0, min(1.0, t))
    edge = 0.14
    if t < edge:
        fade = 0.5 - 0.5 * math.cos(math.pi * t / edge)
    elif t > 1.0 - edge:
        fade = 0.5 - 0.5 * math.cos(math.pi * (1.0 - t) / edge)
    else:
        fade = 1.0
    return amp * math.sin(2.0 * math.pi * n * t) * fade


def make_wave_prism(c, name, x0, x1, z0, z1, ya_fn, yb, segs=48):
    """X 向拉伸的 YZ 波浪条，ya_fn(z) 与常值 yb 为两条 Y 边。"""
    n = segs
    verts = []
    for i in range(n):
        z = z0 + (z1 - z0) * i / (n - 1)
        ya = ya_fn(z)
        verts.append((x0, ya, z))
        verts.append((x1, ya, z))
        verts.append((x0, yb, z))
        verts.append((x1, yb, z))
    faces = []
    for i in range(n - 1):
        a = i * 4
        b = (i + 1) * 4
        faces.append((a + 0, a + 1, b + 1, b + 0))
        faces.append((a + 2, b + 2, b + 3, a + 3))
        faces.append((a + 0, b + 0, b + 2, a + 2))
        faces.append((a + 1, a + 3, b + 3, b + 1))
    last = (n - 1) * 4
    faces.append((0, 2, 3, 1))
    faces.append((last + 0, last + 1, last + 3, last + 2))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.validate()
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    link_obj(o, c)
    return o


def base_wave_solids(c, x0, x1, z0, z1):
    wall = BASE_OUT_W / 2
    back = wall - WAVE_EMBED

    def y_out(z):
        return wall + wave_offset(z, z0, z1)

    return [
        make_wave_prism(c, "_bw_yp", x0, x1, z0, z1, y_out, back),
        make_wave_prism(c, "_bw_yn", x0, x1, z0, z1, lambda z: -y_out(z), -back),
    ]


def lid_wave_adders(c, x0, x1, z0, z1):
    inner = LID_IN_W / 2

    def des(z):
        return BASE_OUT_W / 2 + SNAP_FIT + wave_offset(z, z0, z1)

    return [
        make_wave_prism(c, "_lw_add_yp", x0, x1, z0, z1, lambda z: min(des(z), inner), inner + 0.32),
        make_wave_prism(c, "_lw_add_yn", x0, x1, z0, z1, lambda z: max(-des(z), -inner), -inner - 0.32),
    ]


def lid_wave_cutters(c, x0, x1, z0, z1):
    inner = LID_IN_W / 2

    def des(z):
        return BASE_OUT_W / 2 + SNAP_FIT + wave_offset(z, z0, z1)

    return [
        make_wave_prism(c, "_lw_cut_yp", x0, x1, z0, z1, lambda z: max(des(z), inner), inner - 0.22),
        make_wave_prism(c, "_lw_cut_yn", x0, x1, z0, z1, lambda z: min(-des(z), -inner), -inner + 0.22),
    ]


def u_slot_cutters(c, name, x_wall, z_round, z_open, r=WIRE_R):
    """U 形走线槽：圆端在 z_round，开口做到 z_open。"""
    depth = 14.0
    z0, z1 = min(z_round, z_open), max(z_round, z_open)
    h = (z1 - z0) + 0.4
    cz = (z0 + z1) / 2.0
    return [
        box(c, name + "_s", depth, 2.0 * r, h, (x_wall, 0.0, cz)),
        cyl(c, name + "_c", r, depth, (x_wall, 0.0, z_round), (0.0, math.radians(90), 0.0)),
    ]


def build_base(c):
    bm = cube_z0(BASE_OUT_L, BASE_OUT_W, BASE_H)
    open_pocket(bm, face_at_z(bm, BASE_H), WALL, PCB_POCKET)
    open_pocket(bm, face_at_z(bm, FLOOR + LEDGE_H), LEDGE_T, LEDGE_H)
    base = bm_to_obj("GY30_Base", c, bm)

    ears = []
    for sx in (-1, 1):
        hole_x = sx * (BASE_OUT_L / 2 + HOLE_FROM_BODY)
        neck_cx = sx * (BASE_OUT_L / 2 + HOLE_FROM_BODY / 2)
        ears.append(box(c, "_ear", HOLE_FROM_BODY, BASE_OUT_W, FLOOR, (neck_cx, 0, FLOOR / 2)))
        ears.append(cyl(c, "_earcap", EAR_R, FLOOR, (hole_x, 0, FLOOR / 2), (0, 0, 0), segs=EAR_SEGS))
    wx0 = -(BASE_OUT_L / 2 - WAVE_X_MARGIN)
    wx1 = BASE_OUT_L / 2 - WAVE_X_MARGIN
    wz0 = ASSEMBLED_LID_Z + WAVE_Z0
    wz1 = ASSEMBLED_LID_Z + WAVE_Z1
    ears.extend(base_wave_solids(c, wx0, wx1, wz0, wz1))
    bool_exact(base, ears, "UNION")

    cutters = []
    ear_x = BASE_OUT_L / 2 + HOLE_FROM_BODY
    for x in (-ear_x, ear_x):
        cutters.append(cyl(c, "_m3", M3_R, FLOOR + 4, (x, 0, FLOOR / 2), (0, 0, 0)))
    # 顶边开口走线槽：板放入后线直接落入，不必从封闭孔穿出
    cutters.extend(u_slot_cutters(c, "_wire", -BASE_OUT_L / 2, WIRE_Z, BASE_H + 4.0))
    bool_exact(base, cutters, "DIFFERENCE")
    mat(base, (0.62, 0.70, 0.76, 1))
    return base


def build_lid(c):
    h = LID_TOP + SKIRT
    bm = cube_z0(LID_OUT_L, LID_OUT_W, h)
    open_pocket(bm, face_at_z(bm, 0.0), LID_WALL, SKIRT)
    lid = bm_to_obj("GY30_Lid", c, bm)
    wx0 = -(BASE_OUT_L / 2 - WAVE_X_MARGIN)
    wx1 = BASE_OUT_L / 2 - WAVE_X_MARGIN
    bool_exact(lid, lid_wave_adders(c, wx0, wx1, WAVE_Z0, WAVE_Z1), "UNION")
    cutters = [
        cyl(c, "_light", LIGHT_R, LID_TOP + 4, (CHIP_X, 0, h - LID_TOP / 2), (0, 0, 0)),
    ]
    # 裙边底开口：套入时槽口从已引出的线上滑过
    cutters.extend(
        u_slot_cutters(c, "_wirel", -LID_OUT_L / 2, WIRE_Z - ASSEMBLED_LID_Z, -4.0)
    )
    cutters.extend(lid_wave_cutters(c, wx0, wx1, WAVE_Z0, WAVE_Z1))
    bool_exact(lid, cutters, "DIFFERENCE")
    mat(lid, (0.72, 0.78, 0.82, 1))
    return lid


def build_pcb(c):
    pcb = box(c, "GY30_PCB", PCB_L, PCB_W, BOARD_CHIP_H, (0, 0, FLOOR + LEDGE_H + BOARD_CHIP_H / 2))
    mat(pcb, (0.12, 0.32, 0.62, 1))
    chip = box(c, "GY30_Chip", 2.4, 2.4, 0.35, (CHIP_X, 0, FLOOR + LEDGE_H + BOARD_CHIP_H + 0.2))
    mat(chip, (0.1, 0.1, 0.12, 1))


def measure_case():
    base = bpy.data.objects["GY30_Base"]
    lid = bpy.data.objects["GY30_Lid"]
    bb = [v.co for v in base.data.vertices]
    lb = [v.co for v in lid.data.vertices]
    ear_x = BASE_OUT_L / 2 + HOLE_FROM_BODY
    lid_z = [v.z for v in lb]
    lid_inner_top = SKIRT
    lid_outer_top = max(lid_z)
    floor = [v for v in bb if v.z < FLOOR + 0.05]
    return {
        "lid_top_mm": round(lid_outer_top - lid_inner_top, 3),
        "base_x": [round(min(v.x for v in bb), 2), round(max(v.x for v in bb), 2)],
        "hole_x": [-round(ear_x, 2), round(ear_x, 2)],
        "hole_span_mm": round(2 * ear_x, 2),
        "ear_r": round(EAR_R, 3),
        "ear_tip": round(ear_x + BASE_OUT_W / 2, 2),
        "floor_ymax": round(max(abs(v.y) for v in floor), 3) if floor else None,
        "spec_lid_top": LID_TOP,
        "spec_ear_ext": round(EAR_EXT, 2),
        "spec_hole_from_body": HOLE_FROM_BODY,
        "base_verts": len(base.data.vertices),
        "lid_verts": len(lid.data.vertices),
    }


def frame():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "OBJECT"
        sp.overlay.show_wireframes = False
        sp.overlay.show_object_origins = False
        r = sp.region_3d
        r.view_location = Vector((0, 0, 7))
        r.view_distance = 55
        r.view_rotation = Euler((math.radians(55), 0, math.radians(-42)), "XYZ").to_quaternion()


def export_stl():
    out = []
    for name in ("GY30_Base", "GY30_Lid"):
        o = bpy.data.objects.get(name)
        if not o:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        fn = f"{name}.stl"
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, fn), export_selected_objects=True)
        out.append(fn)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_gy30()
    c = collection()
    build_base(c)
    lid = build_lid(c)
    lid.location.z = BASE_H + 14.0
    build_pcb(c)
    frame()
    stl = export_stl()
    return {"stl": stl, "measure": measure_case()}


if __name__ == "__main__" or True:
    RESULT = build()
