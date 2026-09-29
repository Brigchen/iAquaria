# iAqua HC-SR04 缸沿支架
# 倒 L：上横板托超声波（盒在板下，12mm 厚）；H 内外竖板与横档均为 5×50。
# 内竖板一通到横板底，顶部 23×12 过线口；外侧 2×M8×1.25 内螺纹（大径 8.5）。
# 1 BU = 1 mm。不删除场景中的 HC-SR04 铰链盒。

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_SR04_Bracket.blend")
COL = "iAqua_SR04_Bracket"

# ----- 闭合盒（由打开件实测）-----
# 打开件两窗口中心距 26.0，耳孔距 58.0，窗口半径 ~9
WIN_PITCH = 26.0
WIN_R = 10.0          # 盒示意窗口，横板不再开此孔
EAR_PITCH = 58.0
EAR_R = 1.6           # M3 通孔
BOX_W = 24.0          # 传感器沿 X
BOX_H = 12.0          # 传感器厚度，固定在上横板下面
FILLET_D = 10.0
FILLET_R = FILLET_D / 2.0
FILLET_SEGS = 32
TEXT_BODY = "iAquaria-JMU"
TEXT_LEN = 50.0
TEXT_DEPTH = 1.0
CABLE_SLOT_W = 23.0   # 内板顶部过线口
CABLE_SLOT_H = 12.0

# ----- 倒 L + H 夹：内外竖板、横档均为 5mm，宽 50mm -----
PLATE = 5.0           # 内竖板 / 外竖板 / H 横档
FLANGE_IN = PLATE
FLANGE_OUT = PLATE
WEB_T = PLATE
SHELF_T = 4.0
HOLE_FROM_INNER = 15.0  # M3 孔心到内竖板缸内面
SHELF_LIP = 2.0         # 传感器体外沿再留边
SHELF_HOLE_X = -(FLANGE_IN + HOLE_FROM_INNER)
SHELF_X = FLANGE_IN + HOLE_FROM_INNER + BOX_W / 2.0 + SHELF_LIP
SHELF_Y = 80.0

GLASS_T = 8.0
SLOT = 12.0
FLANGE_DROP = 40.0
H_Y = 50.0
RISE = 50.0

# M8×1.25 内螺纹（大径 8.5）；两孔靠拢
M8_TAP_D = 8.5
M8_HEAD_AF = 13.0
M8_HEAD_H = 5.3
M8_Y = 11.0           # 孔距 22
M8_Z_FROM_WEB = 20.0
M8_PITCH = 1.25
M8_THREAD_LEN = 20.0

# 玻璃演示
GLASS_H = 120.0
GLASS_Y = 140.0


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
    n = "SR04_" + o.name
    mt = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mt.use_nodes = True
    bsdf = next(n for n in mt.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.4
    o.data.materials.clear()
    o.data.materials.append(mt)


def add_box(bm, cx, cy, cz, sx, sy, sz):
    m = Matrix.Translation(Vector((cx, cy, cz))) @ Matrix.Diagonal(Vector((sx, sy, sz, 1)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


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


def bool_diff(host, cutters, solver="FLOAT"):
    for i, c in enumerate(cutters):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = solver
        mod.object = c
        c.hide_set(True)
        c.hide_render = True
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


def make_corner_fillet_cutter(c, name, x_c, y_c, z_mid, h, dx, dy):
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
    bool_diff(box, [cyl])
    return box


def make_m8_tap_cutter(c, name, d=8.5, pitch=1.25, thread_len=10.0, steps=24):
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


def clear_generated():
    keep = {"HC-SR04+ultrasonic+v11"}
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)


def park_open_box():
    box = bpy.data.objects.get("HC-SR04+ultrasonic+v11")
    if box:
        box.location = (-140, 0, 0)
        box.rotation_euler = Euler((0, 0, 0), "XYZ")


def build_bracket(c):
    """
    玻璃 X=0..GLASS_T，缸沿 Z=0；缸内 −X。
    整段 H 一次挤出（外竖板与横档同体，避免交接处缺面）。
    内竖板主体到过线口底；两侧立柱顶到上横板，中间留 23×12 口。
    """
    x_in0 = -FLANGE_IN
    x_g = 0.0
    x_s = SLOT
    x_out = SLOT + FLANGE_OUT
    z_bot = -FLANGE_DROP
    z_w0, z_w1 = 0.0, WEB_T
    z_slot = RISE - CABLE_SLOT_H
    # 横档一次做到外沿；下垂外板另做并先攻丝，避免在整段 H 上打孔失败
    xz = [
        (x_in0, z_bot),
        (x_g, z_bot),
        (x_g, z_w0),
        (x_out, z_w0),
        (x_out, z_w1),
        (x_g, z_w1),
        (x_g, z_slot),
        (x_in0, z_slot),
    ]
    br = extrude_xz("SR04_Bracket", c, xz, -H_Y / 2.0, H_Y / 2.0)

    # 内板顶部两侧立柱，中间 23mm 开口紧贴上横板底
    post_w = (H_Y - CABLE_SLOT_W) / 2.0
    post_h = CABLE_SLOT_H + 0.5
    posts = []
    for i, sign in enumerate((-1.0, 1.0)):
        yc = sign * (H_Y / 2.0 - post_w / 2.0)
        posts.append(
            box_obj(
                c,
                f"_post{i}",
                FLANGE_IN,
                post_w,
                post_h,
                (-FLANGE_IN / 2.0, yc, z_slot + post_h / 2.0 - 0.25),
            )
        )
    bool_union(br, posts)
    br.name = "SR04_Bracket"

    shelf_z0 = RISE
    shelf_z1 = RISE + SHELF_T
    shelf = box_obj(
        c,
        "_shelf",
        SHELF_X,
        SHELF_Y,
        SHELF_T,
        (-SHELF_X / 2.0, 0.0, (shelf_z0 + shelf_z1) / 2.0),
    )
    bool_union(br, [shelf])
    br.name = "SR04_Bracket"

    win_x = SHELF_HOLE_X
    win_z = (shelf_z0 + shelf_z1) / 2.0
    ears = [
        cyl_obj(c, "_ear", EAR_R, SHELF_T + 2, (win_x, y, win_z), (0, 0, 0))
        for y in (-EAR_PITCH / 2.0, EAR_PITCH / 2.0)
    ]
    bool_diff(br, ears)

    y0, y1 = -SHELF_Y / 2.0, SHELF_Y / 2.0
    fillets = [
        make_corner_fillet_cutter(c, "_f0", -SHELF_X, y0, win_z, SHELF_T, 1.0, 1.0),
        make_corner_fillet_cutter(c, "_f1", -SHELF_X, y1, win_z, SHELF_T, 1.0, -1.0),
        make_corner_fillet_cutter(c, "_f2", 0.0, y0, win_z, SHELF_T, -1.0, 1.0),
        make_corner_fillet_cutter(c, "_f3", 0.0, y1, win_z, SHELF_T, -1.0, -1.0),
    ]
    bool_diff(br, fillets)

    txt = make_text_cutter(c, "_engr", TEXT_BODY, TEXT_LEN, TEXT_DEPTH)
    txt.rotation_euler = Euler((0.0, 0.0, math.pi / 2.0), "XYZ")
    txt.location = (-SHELF_X / 2.0, 0.0, RISE + SHELF_T + 0.05)
    bool_diff(br, [txt])

    # 干净外竖板先 EXACT 攻 M8，再并上（上沿伸进横档 0.3mm）
    hang_h = FLANGE_DROP + 0.3
    flange = box_obj(
        c,
        "_flange",
        FLANGE_OUT,
        H_Y,
        hang_h,
        (SLOT + FLANGE_OUT / 2.0, 0.0, 0.3 - hang_h / 2.0),
    )
    m8_z = -M8_Z_FROM_WEB
    x_outer = SLOT + FLANGE_OUT
    tap_len = 16.0
    tap_rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    for i, y in enumerate((-M8_Y, M8_Y)):
        tap = make_m8_tap_cutter(c, f"_m8tap_{i}", d=M8_TAP_D, pitch=M8_PITCH, thread_len=tap_len)
        tap.rotation_euler = tap_rot
        tap.location = (x_outer + 1.5, y, m8_z)
        bool_diff(flange, [tap], solver="EXACT")
    bool_union(br, [flange])
    br.name = "SR04_Bracket"

    mat(br, (0.62, 0.70, 0.76, 1))
    return br


def build_closed_box_proxy(c):
    """传感器 12mm 厚，挂在上横板下面，窗口朝 −Z。"""
    bm = bmesh.new()
    add_box(bm, SHELF_HOLE_X, 0, RISE - BOX_H / 2, BOX_W, 50.0, BOX_H)
    for y in (-EAR_PITCH / 2, EAR_PITCH / 2):
        add_box(bm, SHELF_HOLE_X, y, RISE - 3, 10, 12, 6)
    o = new_mesh("ClosedBox_proxy", c)
    put(o, bm)
    cutters = []
    for y in (-WIN_PITCH / 2, WIN_PITCH / 2):
        cutters.append(
            cyl_obj(c, "_bw", 8.0, 8, (SHELF_HOLE_X, y, RISE - BOX_H + 1), (0, 0, 0))
        )
    for y in (-EAR_PITCH / 2, EAR_PITCH / 2):
        cutters.append(
            cyl_obj(c, "_be", EAR_R, 10, (SHELF_HOLE_X, y, RISE - 3), (0, 0, 0))
        )
    bool_diff(o, cutters)
    mat(o, (0.55, 0.55, 0.58, 1))


def build_glass(c):
    o = new_mesh("Glass_demo", c)
    bm = bmesh.new()
    add_box(bm, GLASS_T / 2, 0, -GLASS_H / 2, GLASS_T, GLASS_Y, GLASS_H)
    put(o, bm)
    mat(o, (0.55, 0.75, 0.88, 0.28))


def bool_union(host, others, solver="FLOAT"):
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
    """ISO 公制外螺纹六角头螺栓。局部 +Z 为螺杆方向（牙尖朝 +Z）。"""
    H = pitch * math.sqrt(3.0) / 2.0
    r_maj = d / 2.0
    r_min = r_maj - (5.0 / 8.0) * H
    neck = 1.6
    head_h = head_h
    af = head_af

    # --- helical thread ridge + core (one mesh) ---
    n_rings = int(round(thread_len / pitch * steps)) + 1
    # closed quad profile (r, z) within one pitch
    c_flat = pitch / 8.0
    root_flat = pitch / 4.0
    flank = 5.0 * pitch / 16.0
    prof = [
        (r_min, c_flat),
        (r_maj, c_flat + flank),
        (r_maj, c_flat + flank + c_flat),
        (r_min, c_flat + flank + c_flat + flank),
    ]

    verts = []
    faces = []
    n_p = len(prof)
    for i in range(n_rings):
        ang = 2.0 * math.pi * i / steps
        ca, sa = math.cos(ang), math.sin(ang)
        z_base = neck + pitch * i / steps
        for r, zp in prof:
            z = z_base + zp
            if z > neck + thread_len + pitch:
                z = neck + thread_len + pitch
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

    # core cylinder (fills minor diameter)
    core = new_mesh(name + "_core", c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=steps,
        radius1=r_min,
        radius2=r_min,
        depth=thread_len + 0.4,
        matrix=Matrix.Translation(Vector((0, 0, neck + thread_len / 2))),
    )
    put(core, bm)

    # unthreaded under-head
    under = new_mesh(name + "_neck", c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=steps,
        radius1=r_maj,
        radius2=r_maj,
        depth=neck + 0.2,
        matrix=Matrix.Translation(Vector((0, 0, neck / 2))),
    )
    put(under, bm)

    # hex head (z negative)
    head = new_mesh(name + "_head", c)
    bm = bmesh.new()
    hex_r = af / math.sqrt(3.0)
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=6,
        radius1=hex_r,
        radius2=hex_r,
        depth=head_h,
        matrix=Matrix.Translation(Vector((0, 0, -head_h / 2))),
    )
    put(head, bm)

    # washer face
    wash = new_mesh(name + "_wf", c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=32,
        radius1=d * 0.72,
        radius2=d * 0.72,
        depth=0.4,
        matrix=Matrix.Translation(Vector((0, 0, 0.15))),
    )
    put(wash, bm)

    # tip chamfer
    tip = new_mesh(name + "_tip", c)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=steps,
        radius1=r_min * 0.55,
        radius2=r_maj,
        depth=1.2,
        matrix=Matrix.Translation(Vector((0, 0, neck + thread_len + 0.2))),
    )
    put(tip, bm)

    bool_union(thread, [core, under, head, wash, tip])
    thread.name = name
    mat(thread, (0.55, 0.56, 0.58, 1))
    return thread


def build_m8_bolts(c):
    m8_z = -M8_Z_FROM_WEB
    rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    x_head = SLOT + FLANGE_OUT
    bolts = []
    for i, y in enumerate((-M8_Y, M8_Y)):
        bolt = make_iso_hex_bolt(
            c,
            f"M8x125_bolt_{i}",
            d=8.0,
            pitch=M8_PITCH,
            thread_len=M8_THREAD_LEN,
            steps=28,
            head_af=M8_HEAD_AF,
            head_h=M8_HEAD_H,
        )
        bolt.rotation_euler = rot
        bolt.location = (x_head, y, m8_z)
        bolts.append(bolt)
    return bolts


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
        r = sp.region_3d
        r.view_location = Vector((-10, 0, 20))
        r.view_distance = 220
        r.view_rotation = Euler((math.radians(70), 0, math.radians(115)), "XYZ").to_quaternion()


def export_stl():
    names = ["SR04_Bracket", "M8x125_bolt_0"]
    out = []
    for name in names:
        o = bpy.data.objects.get(name)
        if not o:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        fname = "M8x1.25x25.stl" if name.startswith("M8") else f"{name}.stl"
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, fname), export_selected_objects=True)
        out.append(fname)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_generated()
    park_open_box()
    c = col()
    build_bracket(c)
    build_closed_box_proxy(c)
    build_glass(c)
    build_m8_bolts(c)
    frame()
    files = export_stl()
    return files


if __name__ == "__main__" or True:
    RESULT = {"stl": build()}
