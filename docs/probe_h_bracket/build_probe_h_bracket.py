# iAqua 温度 / TDS / pH 缸沿支架
# 剖面与超声波支架相同：倒 L + 整体 H 夹；上横板高出缸沿 20mm；
# 缸内竖板下伸 140mm，末端再一块同孔径横板。孔径：温度 Ø8×2、TDS Ø10、pH Ø30。
# 上下横板间距 160mm，总高 170mm（方便打印）。
# 1 BU = 1 mm

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_ProbeH_Bracket.blend")
COL = "iAqua_ProbeH_Bracket"

# ----- 横板与孔（pH Ø30；旁补偿温度孔）-----
SHELF_T = 5.0
RISE = 20.0          # 上横板底面高出缸沿 2cm
DROP = 140.0         # 缸内竖板从缸沿向下 14cm（到下横板顶面）；总高 17cm
RISER_T = 6.0
WALL_MIN = 2.8       # 孔边最小壁厚
HOLE_SEGS = 48
FILLET_D = 10.0      # 上下横板直角倒圆直径
FILLET_R = FILLET_D / 2.0
FILLET_SEGS = 32

D_TEMP, D_TDS, D_PH = 8.2, 10.2, 30.2  # 名义 Ø8 / Ø10 / Ø30，+0.2 间隙
R_TEMP, R_TDS, R_PH = D_TEMP / 2.0, D_TDS / 2.0, D_PH / 2.0


def hole_cut_r(d):
    return (d / 2.0) / math.cos(math.pi / HOLE_SEGS)


HOLE_X = -(RISER_T + WALL_MIN + R_PH)
SHELF_X = RISER_T + 2.0 * (WALL_MIN + R_PH)  # 伸入缸内，随 Ø30
# 沿 Y：水温、TDS、pH、pH补偿温度（贴 pH）
_HOLE_SPEC = (
    ("TEMP", R_TEMP),
    ("TDS", R_TDS),
    ("PH", R_PH),
    ("TEMP2", R_TEMP),
)
_inner = sum(2.0 * r for _, r in _HOLE_SPEC) + WALL_MIN * (len(_HOLE_SPEC) - 1)
SHELF_Y = _inner + 2.0 * WALL_MIN  # 两端保持 WALL_MIN
_edge = (SHELF_Y - _inner) / 2.0
_y = -SHELF_Y / 2.0 + _edge
_holes = []
for _tag, _r in _HOLE_SPEC:
    _y += _r
    _holes.append((_tag, _r, round(_y, 2)))
    _y += _r + WALL_MIN
HOLES = tuple(_holes)

# ----- H 夹（内外竖板同厚 6mm）-----
GLASS_T = 8.0
SLOT = 12.0
FLANGE_OUT = RISER_T  # 与内竖板同厚
WEB_T = 8.0
FLANGE_DROP = 40.0
H_Y = SHELF_Y

M8_TAP_D = 8.5       # 内螺纹大径（打印间隙，配 M8×1.25）
M8_HEAD_AF = 13.0
M8_HEAD_H = 5.3
M8_Y = 20.0
M8_Z_FROM_WEB = 20.0
M8_PITCH = 1.25
M8_THREAD_LEN = 20.0

GLASS_H = 220.0
GLASS_Y = 160.0


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


def new_mesh(name, c):
    m = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, m)
    link_obj(o, c)
    return o


def put(o, bm):
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def mat(o, rgba):
    n = "ProbeH_" + o.name
    mt = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.4
    if len(rgba) > 3 and rgba[3] < 0.99:
        mt.blend_method = "BLEND"
        bsdf.inputs["Alpha"].default_value = rgba[3]
    o.data.materials.clear()
    o.data.materials.append(mt)


def extrude_xz(name, c, xz, y0, y1):
    """xz 闭合环沿 Y 挤出，两端封口。"""
    n = len(xz)
    verts = []
    for y in (y0, y1):
        for x, z in xz:
            verts.append((x, y, z))
    faces = []
    for i in range(n):
        a, b = i, (i + 1) % n
        faces.append((a, b, b + n, a + n))
    faces.append(list(range(n - 1, -1, -1)))
    faces.append(list(range(n, 2 * n)))
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.validate()
    o = bpy.data.objects.new(name, me)
    link_obj(o, c)
    return o


def bool_exact(host, cutters, op="DIFFERENCE"):
    for i, ct in enumerate(cutters):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = op
        mod.solver = "EXACT"
        mod.object = ct
        ct.hide_set(True)
        ct.hide_render = True
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


def cyl_obj(c, name, r, depth, loc, rot, segs=32):
    o = new_mesh(name, c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=depth, matrix=Matrix.Identity(4)
    )
    put(o, bm)
    o.location = loc
    o.rotation_euler = Euler(rot, "XYZ")
    return o


def box_obj(c, name, sx, sy, sz, loc):
    o = new_mesh(name, c)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= sx
        v.co.y *= sy
        v.co.z *= sz
    put(o, bm)
    o.location = loc
    return o


def make_corner_fillet_cutter(c, name, x_c, y_c, z_mid, h, dx, dy):
    """从直角切掉方块减圆：圆心在板内，半径 FILLET_R。dx/dy 为从角指向板内。"""
    r = FILLET_R / math.cos(math.pi / FILLET_SEGS)
    cx = x_c + dx * FILLET_R
    cy = y_c + dy * FILLET_R
    box = box_obj(
        c,
        name + "_b",
        FILLET_R + 0.4,
        FILLET_R + 0.4,
        h + 2.0,
        (x_c + dx * FILLET_R / 2.0, y_c + dy * FILLET_R / 2.0, z_mid),
    )
    cyl = cyl_obj(c, name + "_c", r, h + 4.0, (cx, cy, z_mid), (0, 0, 0), segs=FILLET_SEGS)
    bool_exact(box, [cyl], "DIFFERENCE")
    return box


def hex_obj(c, name, af, depth, loc, rot):
    o = new_mesh(name, c)
    r = af / math.sqrt(3)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=6, radius1=r, radius2=r, depth=depth, matrix=Matrix.Identity(4)
    )
    put(o, bm)
    o.location = loc
    o.rotation_euler = Euler(rot, "XYZ")
    return o


def clear_probeh():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and (o.name.startswith("ProbeH") or o.name in ("Glass_probe_demo",)):
            bpy.data.objects.remove(o, do_unlink=True)


def build_bracket(c):
    """
    玻璃 X=0..GLASS_T，缸沿顶 Z=0；缸内 −X。
    上横板底 Z=RISE；下横板顶 Z=−DROP。
    XZ 剖面一次挤出（与示意图相同），避免多块布尔丢面。
    """
    x0, x1, x2 = -SHELF_X, -RISER_T, 0.0
    x3, x4 = SLOT, SLOT + FLANGE_OUT
    z_lo0, z_lo1 = -DROP - SHELF_T, -DROP
    z_out, z_web0, z_web1 = -FLANGE_DROP, 0.0, WEB_T
    z_up0, z_up1 = RISE, RISE + SHELF_T
    xz = [
        (x0, z_lo0),
        (x2, z_lo0),
        (x2, z_web0),
        (x3, z_web0),
        (x3, z_out),
        (x4, z_out),
        (x4, z_web1),
        (x2, z_web1),
        (x2, z_up1),
        (x0, z_up1),
        (x0, z_up0),
        (x1, z_up0),
        (x1, z_lo1),
        (x0, z_lo1),
    ]
    br = extrude_xz("ProbeH_Bracket", c, xz, -SHELF_Y / 2, SHELF_Y / 2)

    cutters = []
    up_z = (z_up0 + z_up1) / 2
    lo_z = (z_lo0 + z_lo1) / 2
    for tag, r, y in HOLES:
        for z in (up_z, lo_z):
            cutters.append(
                cyl_obj(
                    c,
                    f"_h_{tag}_{int(z)}",
                    hole_cut_r(2.0 * r),
                    SHELF_T + 4,
                    (HOLE_X, y, z),
                    (0, 0, 0),
                    segs=HOLE_SEGS,
                )
            )

    bool_exact(br, cutters, "DIFFERENCE")

    # 上下横板仅游离端两角倒圆 Ø10（与竖板相连的角不倒）
    fillets = []
    n = 0
    for z_mid, h in ((up_z, SHELF_T), (lo_z, SHELF_T)):
        for y, dy in ((-SHELF_Y / 2.0, 1.0), (SHELF_Y / 2.0, -1.0)):
            fillets.append(make_corner_fillet_cutter(c, f"_fil_i{n}", -SHELF_X, y, z_mid, h, 1.0, dy))
            n += 1
    bool_exact(br, fillets, "DIFFERENCE")

    # 外竖板两孔：M8×1.25 内螺纹，大径 8.5，与螺丝同旋向
    m8_z = -M8_Z_FROM_WEB
    x_outer = SLOT + FLANGE_OUT
    tap_len = FLANGE_OUT + 4.0
    tap_rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    for i, y in enumerate((-M8_Y, M8_Y)):
        tap = make_m8_tap_cutter(c, f"_m8tap_{i}", d=M8_TAP_D, pitch=M8_PITCH, thread_len=tap_len)
        tap.rotation_euler = tap_rot
        tap.location = (x_outer + 1.5, y, m8_z)
        bool_exact(br, [tap], "DIFFERENCE")
    mat(br, (0.62, 0.70, 0.76, 1))
    return br


def build_probes(c):
    """示意探头，不导出。"""
    z_top = RISE + SHELF_T + 18.0
    z_bot = -DROP - SHELF_T - 12.0
    h = z_top - z_bot
    colors = {
        "TEMP": (0.75, 0.55, 0.22, 1),
        "TDS": (0.55, 0.58, 0.62, 1),
        "PH": (0.35, 0.72, 0.48, 1),
        "TEMP2": (0.82, 0.48, 0.18, 1),
    }
    for tag, r, y in HOLES:
        o = cyl_obj(c, f"ProbeH_{tag}", r - 0.4, h, (HOLE_X, y, (z_top + z_bot) / 2), (0, 0, 0), segs=20)
        mat(o, colors[tag])


def build_glass(c):
    o = new_mesh("Glass_probe_demo", c)
    bm = bmesh.new()
    m = Matrix.Translation(Vector((GLASS_T / 2, 0, -GLASS_H / 2))) @ Matrix.Diagonal(
        Vector((GLASS_T, GLASS_Y, GLASS_H, 1))
    )
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    put(o, bm)
    mat(o, (0.55, 0.75, 0.88, 0.28))


def bool_union(host, others):
    for i, o in enumerate(others):
        mod = host.modifiers.new(f"u{i}", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = "EXACT"
        mod.object = o
        o.hide_set(True)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = host.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = host.data
    host.modifiers.clear()
    host.data = baked
    bpy.data.meshes.remove(old)
    for o in others:
        md = o.data
        bpy.data.objects.remove(o, do_unlink=True)
        if md.users == 0:
            bpy.data.meshes.remove(md)


def make_m8_tap_cutter(c, name, d=8.5, pitch=1.25, thread_len=10.0, steps=24):
    """ISO 公制右旋外螺纹实体，布尔挖出匹配 M8 的内螺纹（大径 d）。"""
    H = pitch * math.sqrt(3.0) / 2.0
    r_maj = d / 2.0
    r_min = r_maj - (5.0 / 8.0) * H
    c_flat = pitch / 8.0
    flank = 5.0 * pitch / 16.0
    prof = [
        (r_min, c_flat),
        (r_maj, c_flat + flank),
        (r_maj, c_flat + flank + c_flat),
        (r_min, c_flat + flank + c_flat + flank),
    ]
    n_rings = int(round(thread_len / pitch * steps)) + 1
    verts, faces, n_p = [], [], len(prof)
    for i in range(n_rings):
        ang = 2.0 * math.pi * i / steps
        ca, sa = math.cos(ang), math.sin(ang)
        z_base = pitch * i / steps
        for r, zp in prof:
            z = min(z_base + zp, thread_len + pitch)
            verts.append((r * ca, r * sa, z))
    for i in range(n_rings - 1):
        for k in range(n_p):
            a = i * n_p + k
            b = i * n_p + (k + 1) % n_p
            c2 = (i + 1) * n_p + (k + 1) % n_p
            d2 = (i + 1) * n_p + k
            faces.append((a, d2, c2, b))
    mesh = bpy.data.meshes.new(name + "_th")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    mesh.validate()
    thread = bpy.data.objects.new(name + "_th", mesh)
    link_obj(thread, c)

    def cone(nm, r1, r2, depth, zc, segs=max(steps, 32)):
        o = new_mesh(nm, c)
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=segs,
            radius1=r1,
            radius2=r2,
            depth=depth,
            matrix=Matrix.Translation(Vector((0, 0, zc))),
        )
        put(o, bm)
        return o

    core = cone(name + "_core", r_min, r_min, thread_len + 1.0, thread_len / 2.0)
    # 两端在板外，保证打穿；板上整段是螺纹
    cap0 = cone(name + "_c0", r_maj, r_maj, 1.6, -0.6)
    cap1 = cone(name + "_c1", r_maj, r_maj, 1.6, thread_len + 0.6)
    bool_union(thread, [core, cap0, cap1])
    thread.name = name
    return thread


def make_iso_hex_bolt(c, name, d=8.0, pitch=1.25, thread_len=20.0, steps=28, head_af=13.0, head_h=5.3):
    H = pitch * math.sqrt(3.0) / 2.0
    r_maj = d / 2.0
    r_min = r_maj - (5.0 / 8.0) * H
    neck = 1.6
    c_flat = pitch / 8.0
    flank = 5.0 * pitch / 16.0
    prof = [
        (r_min, c_flat),
        (r_maj, c_flat + flank),
        (r_maj, c_flat + flank + c_flat),
        (r_min, c_flat + flank + c_flat + flank),
    ]
    n_rings = int(round(thread_len / pitch * steps)) + 1
    verts, faces, n_p = [], [], len(prof)
    for i in range(n_rings):
        ang = 2.0 * math.pi * i / steps
        ca, sa = math.cos(ang), math.sin(ang)
        z_base = neck + pitch * i / steps
        for r, zp in prof:
            z = min(z_base + zp, neck + thread_len + pitch)
            verts.append((r * ca, r * sa, z))
    for i in range(n_rings - 1):
        for k in range(n_p):
            a = i * n_p + k
            b = i * n_p + (k + 1) % n_p
            c2 = (i + 1) * n_p + (k + 1) % n_p
            d2 = (i + 1) * n_p + k
            faces.append((a, d2, c2, b))
    mesh = bpy.data.meshes.new(name + "_th")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    thread = bpy.data.objects.new(name + "_th", mesh)
    link_obj(thread, c)

    def cone(nm, r1, r2, depth, zc, segs=steps):
        o = new_mesh(nm, c)
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm,
            cap_ends=True,
            segments=segs,
            radius1=r1,
            radius2=r2,
            depth=depth,
            matrix=Matrix.Translation(Vector((0, 0, zc))),
        )
        put(o, bm)
        return o

    core = cone(name + "_core", r_min, r_min, thread_len + 0.4, neck + thread_len / 2)
    under = cone(name + "_neck", r_maj, r_maj, neck + 0.2, neck / 2)
    hex_r = head_af / math.sqrt(3.0)
    head = cone(name + "_head", hex_r, hex_r, head_h, -head_h / 2, segs=6)
    wash = cone(name + "_wf", d * 0.72, d * 0.72, 0.4, 0.15, segs=32)
    tip = cone(name + "_tip", r_min * 0.55, r_maj, 1.2, neck + thread_len + 0.2)
    bool_union(thread, [core, under, head, wash, tip])
    thread.name = name
    mat(thread, (0.55, 0.56, 0.58, 1))
    return thread


def build_m8_bolts(c):
    m8_z = -M8_Z_FROM_WEB
    rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    x_head = SLOT + FLANGE_OUT
    for i, y in enumerate((-M8_Y, M8_Y)):
        bolt = make_iso_hex_bolt(c, f"ProbeH_M8_{i}", d=8.0, pitch=M8_PITCH, thread_len=M8_THREAD_LEN)
        bolt.rotation_euler = rot
        bolt.location = (x_head, y, m8_z)


def frame():
    if bpy.context.screen is None:
        return
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "OBJECT"
        sp.overlay.show_object_origins = False
        sp.overlay.show_wireframes = False
        r = sp.region_3d
        r.view_location = Vector((-15, 0, -40))
        r.view_distance = 320
        r.view_rotation = Euler((math.radians(78), 0, math.radians(108)), "XYZ").to_quaternion()


def export_stl():
    out = []
    o = bpy.data.objects.get("ProbeH_Bracket")
    if o:
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, "ProbeH_Bracket.stl"), export_selected_objects=True)
        out.append("ProbeH_Bracket.stl")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_probeh()
    c = col()
    build_bracket(c)
    build_probes(c)
    build_glass(c)
    build_m8_bolts(c)
    frame()
    stl = export_stl()
    return {
        "stl": stl,
        "shelf": (round(SHELF_X, 2), round(SHELF_Y, 2), SHELF_T),
        "hole_x": round(HOLE_X, 2),
        "holes": [(t, round(2.0 * r, 2), y) for t, r, y in HOLES],
        "m8_tap_d": M8_TAP_D,
        "m8_pitch": M8_PITCH,
        "drop": DROP,
        "rise": RISE,
        "total_h": RISE + DROP + 2.0 * SHELF_T,
        "fillet_d": FILLET_D,
    }


if __name__ == "__main__" or True:
    RESULT = build()
