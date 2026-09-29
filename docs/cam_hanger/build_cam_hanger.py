# iAqua 鱼缸外挂摄像头吊架
# 缸沿挂钩 + 外竖板 A（三圆孔）+ 外竖板 B（槽孔调长度）+ 万向接头。
# A 最上 M8 顶玻璃；下面两颗 M8 锁 A/B。四孔 Ø8.1（略大于牙尖，PETG 自攻能咬住）。板厚 5mm。

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_CamHanger.blend")
COL = "iAqua_CamHanger"

PLATE = 5.0
SLOT = 12.0          # ≤10mm 玻璃
INNER_DROP = 30.0
BAR_LEN = 100.0
BAR_W = 18.0         # M8 六角对边 13
PAD = 30.0           # 接头座 30×30
OVERLAP = 50.0       # 演示重叠
M8_TAP_D = 8.1       # 略大于 M8 大径 8.0，螺丝能旋入并卡住
HOLE_SEGS = 48
M8_TAP_R = (M8_TAP_D / 2.0) / math.cos(math.pi / HOLE_SEGS)
M8_HOLE_D = 9.0      # B 调节槽宽，螺丝能穿过再旋入 A
M8_CLEAR = (M8_HOLE_D / 2.0) / math.cos(math.pi / HOLE_SEGS)
M8_HEAD_AF = 13.0
M8_HEAD_H = 5.3
M8_PITCH = 1.25
M8_THREAD_LEN = 10.0  # A/B 连接，不穿出到玻璃
M8_CLAMP_THREAD = 6.0  # 顶到玻璃外表面，不穿玻璃
ADJ_SLOT_W = M8_HOLE_D
ADJ_SLOT_LEN = 80.0
# A 板上到下三孔：顶玻璃、锁 B、锁 B
Z_CLAMP = -18.0
Z_AB1 = -68.0
Z_AB2 = -88.0
TEXT_BODY = "iAquaria-JMU"
TEXT_LEN = 34.0
TEXT_DEPTH = 1.0
FILLET_R = 5.0       # 横板 / 垫板游离角 Ø10
FILLET_R_END = 2.5   # 5mm 竖板端头（半圆）
FILLET_SEGS = 32

GLASS_T = 8.0
GLASS_H = 280.0
GLASS_Y = 120.0

# 上板：沿口顶 Z=PLATE，外板底 Z=PLATE-BAR_LEN
Z_WEB1 = PLATE
Z_UP_BOT = PLATE - BAR_LEN
# 下板：重叠 OVERLAP
Z_LO_TOP = Z_UP_BOT + OVERLAP
Z_LO_BOT = Z_LO_TOP - BAR_LEN
Z_PAD0 = Z_LO_BOT - PLATE

X_IN0 = -PLATE
X_GLASS0 = 0.0
X_OUT0 = SLOT
X_OUT1 = SLOT + PLATE
X_LO0 = SLOT + PLATE
X_LO1 = SLOT + 2 * PLATE
X_PAD1 = X_LO0 + PAD


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
    n = "CamH_" + o.name
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


def cyl_obj(c, name, r, depth, loc, rot, segs=HOLE_SEGS):
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


def make_m8_tap_cutter(c, name, d=8.5, pitch=1.25, thread_len=16.0, steps=24):
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
    cap0 = cone(name + "_c0", r_maj, r_maj, 1.6, -0.6)
    cap1 = cone(name + "_c1", r_maj, r_maj, 1.6, thread_len + 0.6)
    bool_union(thread, [core, cap0, cap1], solver="EXACT")
    thread.name = name
    return thread


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


def load_engrave_font():
    for p in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ):
        if not os.path.isfile(p):
            continue
        for f in bpy.data.fonts:
            if f.filepath.replace("/", "\\").lower() == p.lower():
                return f
        return bpy.data.fonts.load(p)
    return bpy.data.fonts[0]


def make_text_cutter(c, name, body, length, depth):
    """平面文字挤出成凹字刀具，书写方向为局部 +X，总长 length。"""
    cu = bpy.data.curves.new(name + "_cu", "FONT")
    cu.body = body
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.size = 1.0
    cu.resolution_u = 3
    cu.font = load_engrave_font()
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    link_obj(tmp, c)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(cu)

    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    if not bm.verts:
        bm.free()
        raise RuntimeError("text mesh empty")
    xs = [v.co.x for v in bm.verts]
    span = max(xs) - min(xs)
    s = length / span if span > 1e-6 else 1.0
    bmesh.ops.scale(bm, vec=Vector((s, s, 1.0)), verts=list(bm.verts))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    ret = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
    ev = [g for g in ret["geom"] if isinstance(g, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=ev, vec=Vector((0.0, 0.0, -(depth + 0.15))))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    out = bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    o = bpy.data.objects.new(name, out)
    link_obj(o, c)
    return o


def make_corner_fillet_cutter(c, name, x_c, y_c, z_mid, h, dx, dy, radius=FILLET_R):
    """XY 平面直角切成圆弧。dx/dy 为从角指向板内。"""
    r = radius / math.cos(math.pi / FILLET_SEGS)
    box = box_obj(
        c,
        name + "_b",
        radius + 0.4,
        radius + 0.4,
        h + 2.0,
        (x_c + dx * radius / 2.0, y_c + dy * radius / 2.0, z_mid),
    )
    cyl = cyl_obj(
        c,
        name + "_c",
        r,
        h + 4.0,
        (x_c + dx * radius, y_c + dy * radius, z_mid),
        (0, 0, 0),
        segs=FILLET_SEGS,
    )
    bool_exact(box, [cyl])
    return box


def xy_rect_fillets(c, prefix, x0, x1, y0, y1, z_mid, h, radius):
    """水平板 XY 四角倒圆。"""
    return [
        make_corner_fillet_cutter(c, prefix + "0", x0, y0, z_mid, h, 1.0, 1.0, radius),
        make_corner_fillet_cutter(c, prefix + "1", x0, y1, z_mid, h, 1.0, -1.0, radius),
        make_corner_fillet_cutter(c, prefix + "2", x1, y0, z_mid, h, -1.0, 1.0, radius),
        make_corner_fillet_cutter(c, prefix + "3", x1, y1, z_mid, h, -1.0, -1.0, radius),
    ]


def make_yz_fillet_cutter(c, name, x_mid, y_c, z_c, thick, dy, dz, radius=FILLET_R):
    """竖板板面（YZ）直角切成圆弧。圆柱沿 X 穿过板厚。"""
    r = radius / math.cos(math.pi / FILLET_SEGS)
    box = box_obj(
        c,
        name + "_b",
        thick + 2.0,
        radius + 0.4,
        radius + 0.4,
        (x_mid, y_c + dy * radius / 2.0, z_c + dz * radius / 2.0),
    )
    cyl = cyl_obj(
        c,
        name + "_c",
        r,
        thick + 4.0,
        (x_mid, y_c + dy * radius, z_c + dz * radius),
        (0.0, math.radians(90.0), 0.0),
        segs=FILLET_SEGS,
    )
    bool_exact(box, [cyl])
    return box


def yz_end_fillets(c, prefix, x_mid, thick, y0, y1, z_end, dz, radius=FILLET_R):
    """竖板游离端左右两角，沿板面倒圆。dz 指向板内。"""
    return [
        make_yz_fillet_cutter(c, prefix + "0", x_mid, y0, z_end, thick, 1.0, dz, radius),
        make_yz_fillet_cutter(c, prefix + "1", x_mid, y1, z_end, thick, -1.0, dz, radius),
    ]


def slot_cutter(c, name, x, z0, z1, y=0.0):
    h = abs(z1 - z0)
    cz = (z0 + z1) / 2.0
    return [
        box_obj(c, name + "_s", PLATE + 8, M8_HOLE_D, h, (x, y, cz)),
        cyl_obj(c, name + "_a", M8_CLEAR, PLATE + 8, (x, y, z0), (0, math.radians(90), 0)),
        cyl_obj(c, name + "_b", M8_CLEAR, PLATE + 8, (x, y, z1), (0, math.radians(90), 0)),
    ]


def clear_hanger():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and (
            o.name.startswith("CamHanger")
            or o.name.startswith("CamH_")
            or o.name.startswith("TEST_")
            or o.name in ("Glass_cam_demo", "CamHanger_CAM")
        ):
            bpy.data.objects.remove(o, do_unlink=True)


def build_upper(c):
    """A：挂钩 + 外竖板一次挤出（封闭实体），三孔 Ø8.1。"""
    xz = [
        (X_IN0, -INNER_DROP),
        (X_GLASS0, -INNER_DROP),
        (X_GLASS0, 0.0),
        (X_OUT0, 0.0),
        (X_OUT0, Z_UP_BOT),
        (X_OUT1, Z_UP_BOT),
        (X_OUT1, Z_WEB1),
        (X_IN0, Z_WEB1),
    ]
    o = extrude_xz("CamHanger_Upper", c, xz, -BAR_W / 2, BAR_W / 2)
    ax = (X_OUT0 + X_OUT1) / 2.0
    rot = (0.0, math.radians(90.0), 0.0)
    cutters = [
        cyl_obj(c, f"_ah{i}", M8_TAP_R, PLATE + 6, (ax, 0.0, z), rot, segs=HOLE_SEGS)
        for i, z in enumerate((Z_CLAMP, Z_AB1, Z_AB2))
    ]
    bool_exact(o, cutters)
    # 外侧最空处：顶孔与下面两孔之间，沿竖板向下
    txt = make_text_cutter(c, "_engr", TEXT_BODY, TEXT_LEN, TEXT_DEPTH)
    txt.rotation_euler = Euler((0.0, math.radians(90.0), 0.0), "XYZ")
    txt.location = (X_OUT1 + 0.05, 0.0, (Z_CLAMP + Z_AB1) / 2.0)
    bool_exact(o, [txt])
    y0, y1 = -BAR_W / 2.0, BAR_W / 2.0
    fillets = []
    fillets += yz_end_fillets(
        c, "_aib", (X_IN0 + X_GLASS0) / 2.0, PLATE, y0, y1, -INNER_DROP, 1.0, FILLET_R
    )
    fillets += yz_end_fillets(
        c, "_aob", (X_OUT0 + X_OUT1) / 2.0, PLATE, y0, y1, Z_UP_BOT, 1.0, FILLET_R
    )
    bool_exact(o, fillets)
    mat(o, (0.62, 0.70, 0.76, 1))
    return o


def build_lower(c):
    # 竖板
    xz = [
        (X_LO0, Z_LO_BOT),
        (X_LO1, Z_LO_BOT),
        (X_LO1, Z_LO_TOP),
        (X_LO0, Z_LO_TOP),
    ]
    bar = extrude_xz("CamHanger_Lower", c, xz, -BAR_W / 2, BAR_W / 2)
    cx = (X_LO0 + X_PAD1) / 2.0
    cz = (Z_PAD0 + Z_LO_BOT) / 2.0
    pad = box_obj(c, "_pad", PAD, PAD, PLATE, (cx, 0.0, cz))
    bool_exact(bar, [pad], op="UNION")
    z_a = Z_LO_TOP - 10.0 - ADJ_SLOT_LEN
    z_b = Z_LO_TOP - 10.0
    cutters = slot_cutter(c, "_ls", (X_LO0 + X_LO1) / 2.0, z_a, z_b)
    cutters.append(cyl_obj(c, "_pad_m8", M8_TAP_R, PLATE + 4, (cx, 0.0, cz), (0, 0, 0), segs=HOLE_SEGS))
    bool_exact(bar, cutters)
    y0, y1 = -BAR_W / 2.0, BAR_W / 2.0
    py0, py1 = -PAD / 2.0, PAD / 2.0
    fillets = []
    fillets += yz_end_fillets(
        c, "_btop", (X_LO0 + X_LO1) / 2.0, PLATE, y0, y1, Z_LO_TOP, -1.0, FILLET_R
    )
    # 垫板：远离竖板的两角 Ø10；靠近竖板的两角 R2.5，避免切到竖板
    fillets += [
        make_corner_fillet_cutter(c, "_pf0", X_PAD1, py0, cz, PLATE, -1.0, 1.0, FILLET_R),
        make_corner_fillet_cutter(c, "_pf1", X_PAD1, py1, cz, PLATE, -1.0, -1.0, FILLET_R),
        make_corner_fillet_cutter(c, "_pn0", X_LO0, py0, cz, PLATE, 1.0, 1.0, FILLET_R_END),
        make_corner_fillet_cutter(c, "_pn1", X_LO0, py1, cz, PLATE, 1.0, -1.0, FILLET_R_END),
    ]
    bool_exact(bar, fillets)
    bar.name = "CamHanger_Lower"
    mat(bar, (0.58, 0.67, 0.73, 1))
    return bar


def dup_joint(src_name, new_name, c):
    src = bpy.data.objects.get(src_name)
    if src is None:
        raise RuntimeError(f"missing joint part: {src_name}")
    o = src.copy()
    o.data = src.data.copy()
    o.name = new_name
    o.location = (0.0, 0.0, 0.0)
    o.rotation_euler = Euler((0, 0, 0), "XYZ")
    link_obj(o, c)
    return o


def assemble_joint(c):
    """座贴在底垫下表面，杯口朝下；球 + 手拧环夹紧。"""
    cx = (X_LO0 + X_PAD1) / 2
    # Wall-mount 局部：原点在角，杯沿 +Z，底板 z=0
    wall = dup_joint("Wall-mount", "CamH_Wall-mount", c)
    wall.rotation_euler = Euler((math.pi, 0, 0), "XYZ")  # 杯口 -Z
    # RX180: (x,y,z)->(x,-y,-z)。原点世界 = 底板角
    # 想让底板 z=0 贴 Z_PAD0，杯向 -Z；30×30 对齐垫板
    wall.location = (cx - 15.0, 15.0, Z_PAD0)

    # 1×M8 穿过座中心
    cx = (X_LO0 + X_PAD1) / 2
    holes = [cyl_obj(c, "_wh_m8", M8_CLEAR, 16, (cx, 0.0, Z_PAD0 - 5.0), (0, 0, 0), segs=HOLE_SEGS)]
    bool_exact(wall, holes)
    mat(wall, (0.72, 0.74, 0.76, 1))

    ball = dup_joint("ball standard", "CamH_ball", c)
    ball.rotation_euler = Euler((math.pi, 0, 0), "XYZ")
    cup_z = Z_PAD0 - 10.9
    ball.location = (cx - 8.9, 8.9, cup_z + 6.8)

    screw = dup_joint("Finger Screw", "CamH_FingerScrew", c)
    screw.rotation_euler = Euler((math.pi, 0, 0), "XYZ")
    screw.location = (cx - 15.0, 15.0, cup_z + 3.0)
    mat(screw, (0.45, 0.46, 0.48, 1))
    mat(ball, (0.80, 0.82, 0.84, 1))
    return wall, ball, screw


def bool_union(host, others, solver="EXACT"):
    for i, o in enumerate(others):
        mod = host.modifiers.new(f"u{i}", "BOOLEAN")
        mod.operation = "UNION"
        mod.solver = solver
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


def make_hex_nut(c, name, d=8.0, af=13.0, h=6.5):
    o = new_mesh(name, c)
    bm = bmesh.new()
    hex_r = af / math.sqrt(3.0)
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=6, radius1=hex_r, radius2=hex_r, depth=h, matrix=Matrix.Identity(4)
    )
    put(o, bm)
    hole = cyl_obj(c, name + "_h", d / 2 * 0.85, h + 2, (0, 0, 0), (0, 0, 0), segs=20)
    bool_exact(o, [hole])
    mat(o, (0.55, 0.56, 0.58, 1))
    return o


def build_screws(c):
    """短 M8：最上顶玻璃；下面两颗穿 B 槽锁 A；垫板 1×M8。四孔均为内螺纹。"""
    rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    # 顶玻璃：头在 A 外表面，杆只穿过 A，不穿到缸内钩
    clamp = make_iso_hex_bolt(
        c, "CamHanger_M8_clamp", d=8.0, pitch=M8_PITCH, thread_len=M8_CLAMP_THREAD, head_af=M8_HEAD_AF, head_h=M8_HEAD_H
    )
    clamp.rotation_euler = rot
    clamp.location = (X_OUT1, 0.0, Z_CLAMP)

    for i, z in enumerate((Z_AB1, Z_AB2)):
        bolt = make_iso_hex_bolt(
            c, f"CamHanger_M8_{i}", d=8.0, pitch=M8_PITCH, thread_len=M8_THREAD_LEN, head_af=M8_HEAD_AF, head_h=M8_HEAD_H
        )
        bolt.rotation_euler = rot
        bolt.location = (X_LO1, 0.0, z)

    cx = (X_LO0 + X_PAD1) / 2
    pad_bolt = make_iso_hex_bolt(
        c, "CamHanger_M8_pad", d=8.0, pitch=M8_PITCH, thread_len=12.0, head_af=M8_HEAD_AF, head_h=M8_HEAD_H
    )
    pad_bolt.rotation_euler = Euler((math.pi, 0, 0), "XYZ")
    pad_bolt.location = (cx, 0.0, Z_LO_BOT)


def build_cam(c, ball):
    """ESP32-CAM 示意，挂在球杆上。"""
    bpy.context.view_layer.update()
    tip_local = Vector((8.9, 8.9, 23.4))
    tip = ball.matrix_world @ tip_local
    body = box_obj(c, "CamHanger_CAM", 8.0, 27.0, 40.0, (tip.x, tip.y, tip.z - 22.0))
    lens = cyl_obj(c, "CamHanger_LENS", 4.0, 6.0, (tip.x - 6.0, tip.y, tip.z - 22.0), (0, math.radians(90), 0))
    mat(body, (0.18, 0.18, 0.2, 1))
    mat(lens, (0.1, 0.12, 0.18, 1))


def build_glass(c):
    o = new_mesh("Glass_cam_demo", c)
    bm = bmesh.new()
    m = Matrix.Translation(Vector((GLASS_T / 2, 0, -GLASS_H / 2))) @ Matrix.Diagonal(
        Vector((GLASS_T, GLASS_Y, GLASS_H, 1))
    )
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    put(o, bm)
    mat(o, (0.55, 0.75, 0.88, 0.28))


def measure_round_hole(obj, center, axis, r_lo=3.8, r_hi=6.5, along_max=6.0):
    """布尔后内接/外接直径（mm）。内接应对齐 ISO 273 中等 Ø9.0。"""
    mw = obj.matrix_world
    ax = Vector(axis).normalized()
    o = Vector(center)
    radii = []
    for v in obj.data.vertices:
        p = mw @ v.co
        d = p - o
        along = d.dot(ax)
        if abs(along) > along_max:
            continue
        radial = (d - ax * along).length
        if r_lo < radial < r_hi:
            radii.append(radial)
    if not radii:
        return {"n": 0}
    return {
        "n": len(radii),
        "d_inscribed": round(2.0 * min(radii), 3),
        "d_circumscribed": round(2.0 * max(radii), 3),
        "d_mean": round(2.0 * (sum(radii) / len(radii)), 3),
    }


def measure_hanger_holes():
    upper = bpy.data.objects["CamHanger_Upper"]
    lower = bpy.data.objects["CamHanger_Lower"]
    ax = (X_OUT0 + X_OUT1) / 2.0
    cx = (X_LO0 + X_PAD1) / 2.0
    cz = (Z_PAD0 + Z_LO_BOT) / 2.0
    x_axis = (1.0, 0.0, 0.0)
    z_axis = (0.0, 0.0, 1.0)
    return {
        "spec_m8_major_mm": M8_TAP_D,
        "A_clamp": measure_round_hole(upper, (ax, 0.0, Z_CLAMP), x_axis, r_lo=3.8, r_hi=5.0),
        "A_ab1": measure_round_hole(upper, (ax, 0.0, Z_AB1), x_axis, r_lo=3.8, r_hi=5.0),
        "A_ab2": measure_round_hole(upper, (ax, 0.0, Z_AB2), x_axis, r_lo=3.8, r_hi=5.0),
        "pad": measure_round_hole(lower, (cx, 0.0, cz), z_axis, r_lo=3.8, r_hi=5.0, along_max=4.0),
    }


def mesh_print_ok(name):
    o = bpy.data.objects[name]
    bm = bmesh.new()
    bm.from_mesh(o.data)
    nonman = sum(1 for e in bm.edges if not e.is_manifold)
    bound = sum(1 for e in bm.edges if e.is_boundary)
    bm.free()
    return {"verts": len(o.data.vertices), "faces": len(o.data.polygons), "nonmanifold": nonman, "boundary": bound}


def hide_originals():
    for name in ("Wall-mount", "Finger Screw", "ball standard"):
        o = bpy.data.objects.get(name)
        if o:
            o.hide_set(True)


def frame():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "OBJECT"
        sp.overlay.show_object_origins = False
        sp.overlay.show_wireframes = False
        r = sp.region_3d
        r.view_location = Vector((10, 0, -80))
        r.view_distance = 340
        r.view_rotation = Euler((math.radians(78), 0, math.radians(110)), "XYZ").to_quaternion()


def export_stl():
    out = []
    for name in ("CamHanger_Upper", "CamHanger_Lower", "CamHanger_M8_0"):
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
        fn = "M8x1.25x20.stl" if name.startswith("CamHanger_M8") else f"{name}.stl"
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, fn), export_selected_objects=True)
        out.append(fn)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_hanger()
    c = col()
    build_upper(c)
    build_lower(c)
    build_screws(c)
    ball = None
    try:
        _, ball, _ = assemble_joint(c)
        build_cam(c, ball)
    except RuntimeError:
        pass
    build_glass(c)
    hide_originals()
    frame()
    stl = export_stl()
    return {
        "stl": stl,
        "holes": measure_hanger_holes(),
        "print": {"Upper": mesh_print_ok("CamHanger_Upper"), "Lower": mesh_print_ok("CamHanger_Lower")},
    }


if __name__ == "__main__" or True:
    RESULT = build()
