# iAqua 单 TDS 缸沿支架（单独测量）
# 与四孔支架相同的倒 L + H 夹；上横板高出缸沿 20mm；缸内下伸 140mm；总高 170mm。
# 仅 Ø10 TDS 孔，横板按单孔收窄。外竖板 1×M8×1.25 内螺纹（大径 8.5）。1 BU = 1 mm

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_TdsH_Bracket.blend")
COL = "iAqua_TdsH_Bracket"

SHELF_T = 5.0
RISE = 20.0
DROP = 140.0         # 下横板顶；总高 17cm（上顶到下底）
RISER_T = 6.0
WALL_MIN = 2.8
R_TDS = 10.2 / 2
HOLE_X = -(RISER_T + WALL_MIN + R_TDS)
SHELF_X = round(-HOLE_X + R_TDS + WALL_MIN, 1)  # Ø10 + 两侧壁
SHELF_Y = 18.0  # 单颗 M8 + Ø10 孔

GLASS_T = 8.0
SLOT = 12.0
FLANGE_OUT = RISER_T
WEB_T = 8.0
FLANGE_DROP = 40.0

FILLET_D = 10.0
FILLET_R = FILLET_D / 2.0
FILLET_SEGS = 32

M8_TAP_D = 8.5
M8_Y = 0.0  # 单颗，居中
M8_Z_FROM_WEB = 20.0
M8_PITCH = 1.25
M8_THREAD_LEN = 20.0
M8_HEAD_AF = 13.0
M8_HEAD_H = 5.3

GLASS_H = 220.0
GLASS_Y = 160.0
PARK_Y = 110.0  # 与四孔支架错开，同场景可对照


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
    n = "TdsH_" + o.name
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


def _bake_bool(host, cutters, op, solver):
    for i, ct in enumerate(cutters):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = op
        mod.solver = solver
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


def mesh_cleanup(o, fill_holes=False):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bmesh.ops.dissolve_degenerate(bm, dist=0.0005, edges=bm.edges)
    wires = [v for v in bm.verts if not v.link_faces]
    if wires:
        bmesh.ops.delete(bm, geom=wires, context="VERTS")
    loose_e = [e for e in bm.edges if e.is_wire]
    if loose_e:
        bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    if fill_holes:
        holes = [e for e in bm.edges if e.is_boundary]
        if holes:
            bmesh.ops.holes_fill(bm, edges=holes, sides=0)
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    o.data.update()
    o.data.validate()
    bm.free()


def bool_exact(host, cutters, op="DIFFERENCE"):
    _bake_bool(host, cutters, op, "EXACT")


def bool_float(host, cutters, op="DIFFERENCE"):
    _bake_bool(host, cutters, op, "FLOAT")
    mesh_cleanup(host)


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
    """XY 平面直角切成圆弧。dx/dy 为从角指向板内。"""
    r = FILLET_R / math.cos(math.pi / FILLET_SEGS)
    box = box_obj(
        c,
        name + "_b",
        FILLET_R + 0.4,
        FILLET_R + 0.4,
        h + 2.0,
        (x_c + dx * FILLET_R / 2.0, y_c + dy * FILLET_R / 2.0, z_mid),
    )
    cyl = cyl_obj(c, name + "_c", r, h + 4.0, (x_c + dx * FILLET_R, y_c + dy * FILLET_R, z_mid), (0, 0, 0), segs=FILLET_SEGS)
    bool_exact(box, [cyl], "DIFFERENCE")
    return box


def make_yz_fillet_cutter(c, name, x_mid, y_c, z_c, thick, dy, dz):
    """竖板板面（YZ）直角切成圆弧。圆柱沿 X 穿过板厚。"""
    r = FILLET_R / math.cos(math.pi / FILLET_SEGS)
    box = box_obj(
        c,
        name + "_b",
        thick + 2.0,
        FILLET_R + 0.4,
        FILLET_R + 0.4,
        (x_mid, y_c + dy * FILLET_R / 2.0, z_c + dz * FILLET_R / 2.0),
    )
    cyl = cyl_obj(
        c,
        name + "_c",
        r,
        thick + 4.0,
        (x_mid, y_c + dy * FILLET_R, z_c + dz * FILLET_R),
        (0.0, math.radians(90.0), 0.0),
        segs=FILLET_SEGS,
    )
    bool_exact(box, [cyl], "DIFFERENCE")
    return box


def iso_internal_r(frac, r_min, r_maj, pitch):
    u = (frac % 1.0) * pitch
    c_flat = pitch / 8.0
    flank = 5.0 * pitch / 16.0
    a = c_flat
    b = c_flat + flank
    cseg = c_flat + flank + c_flat
    if u <= a:
        return r_min
    if u <= b:
        return r_min + (r_maj - r_min) * (u - a) / flank
    if u <= cseg:
        return r_maj
    return r_maj + (r_min - r_maj) * (u - cseg) / (pitch - cseg)


def make_tapped_flange(c, name, t, w, h, loc, d=8.5, pitch=1.25, steps=24, hole_dz=0.0):
    """外竖板：沿 +X 贯通的 M8×1.25 内螺纹（大径 d），不用布尔。局部原点在板心。"""
    H = pitch * math.sqrt(3.0) / 2.0
    r_maj = d / 2.0
    r_min = r_maj - (5.0 / 8.0) * H
    x0, x1 = -t / 2.0, t / 2.0
    y0, y1 = -w / 2.0, w / 2.0
    z0, z1 = -h / 2.0, h / 2.0
    n_along = max(int(round(t / pitch * steps)) + 1, 8)

    bm = bmesh.new()
    hv = []
    for i in range(n_along):
        x = x0 + (x1 - x0) * i / (n_along - 1)
        row = []
        for j in range(steps):
            ang = 2.0 * math.pi * j / steps
            frac = (x - x0) / pitch - j / float(steps)
            r = iso_internal_r(frac, r_min, r_maj, pitch)
            row.append(bm.verts.new((x, r * math.cos(ang), r * math.sin(ang) + hole_dz)))
        hv.append(row)
    for i in range(n_along - 1):
        for j in range(steps):
            a = hv[i][j]
            b = hv[i][(j + 1) % steps]
            c2 = hv[i + 1][(j + 1) % steps]
            d2 = hv[i + 1][j]
            bm.faces.new((a, d2, c2, b))

    def crn(x, y, z):
        return bm.verts.new((x, y, z))

    # 8 corners: x0/x1, y0/y1, z0/z1
    c0a = crn(x0, y0, z0)
    c0b = crn(x0, y1, z0)
    c0c = crn(x0, y1, z1)
    c0d = crn(x0, y0, z1)
    c1a = crn(x1, y0, z0)
    c1b = crn(x1, y1, z0)
    c1c = crn(x1, y1, z1)
    c1d = crn(x1, y0, z1)
    bm.faces.new((c0a, c1a, c1b, c0b))  # z=z0
    bm.faces.new((c0d, c0c, c1c, c1d))  # z=z1
    bm.faces.new((c0a, c0d, c1d, c1a))  # y=y0
    bm.faces.new((c0b, c1b, c1c, c0c))  # y=y1

    def fill_end(ring, corners_ccw):
        def yang(v):
            return math.atan2(v.co.z - hole_dz, v.co.y)

        c_ang = [yang(p) for p in corners_ccw]
        for j in range(steps):
            a = ring[j]
            b = ring[(j + 1) % steps]
            mid = math.atan2(a.co.z + b.co.z - 2.0 * hole_dz, a.co.y + b.co.y)
            best = min(
                range(4),
                key=lambda k: abs(math.atan2(math.sin(mid - c_ang[k]), math.cos(mid - c_ang[k]))),
            )
            bm.faces.new((a, b, corners_ccw[best]))
        for k in range(4):
            ca = corners_ccw[k]
            cb = corners_ccw[(k + 1) % 4]
            nearest = min(ring, key=lambda v: (v.co - ca.co).length + (v.co - cb.co).length)
            try:
                bm.faces.new((ca, cb, nearest))
            except ValueError:
                pass

    fill_end(hv[0], [c0b, c0c, c0d, c0a])
    fill_end(hv[-1], [c1a, c1d, c1c, c1b])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    o = new_mesh(name, c)
    bm.to_mesh(o.data)
    o.data.update()
    o.data.validate()
    bm.free()
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


def clear_tdsh():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith("TdsH"):
            bpy.data.objects.remove(o, do_unlink=True)


def build_bracket(c):
    x0, x1, x2 = -SHELF_X, -RISER_T, 0.0
    x3, x4 = SLOT, SLOT + FLANGE_OUT
    z_lo0, z_lo1 = -DROP - SHELF_T, -DROP
    z_out, z_web0, z_web1 = -FLANGE_DROP, 0.0, WEB_T
    z_up0, z_up1 = RISE, RISE + SHELF_T
    xz = [
        (x0, z_lo0),
        (x2, z_lo0),
        (x2, z_web0),
        (x4, z_web0),
        (x4, z_web1),
        (x2, z_web1),
        (x2, z_up1),
        (x0, z_up1),
        (x0, z_up0),
        (x1, z_up0),
        (x1, z_lo1),
        (x0, z_lo1),
    ]
    br = extrude_xz("TdsH_Bracket", c, xz, -SHELF_Y / 2, SHELF_Y / 2)

    cutters = []
    up_z = (z_up0 + z_up1) / 2
    lo_z = (z_lo0 + z_lo1) / 2
    for z in (up_z, lo_z):
        cutters.append(cyl_obj(c, f"_tds_{int(z)}", R_TDS, SHELF_T + 4, (HOLE_X, 0.0, z), (0, 0, 0)))
    bool_exact(br, cutters, "DIFFERENCE")

    # 上下横板只倒缸内游离端两角 Ø10；与竖板相连的角保持直角。
    y0, y1 = -SHELF_Y / 2.0, SHELF_Y / 2.0
    fillets = []
    n = 0
    for z_mid, h in ((up_z, SHELF_T), (lo_z, SHELF_T)):
        for y, dy in ((y0, 1.0), (y1, -1.0)):
            fillets.append(make_corner_fillet_cutter(c, f"_fil_i{n}", -SHELF_X, y, z_mid, h, 1.0, dy))
            n += 1
    bool_exact(br, fillets, "DIFFERENCE")

    # 6×18 板上布尔攻丝会撕网或只留下两端牙型。外竖板按 ISO 牙型直接建模后再并上。
    hang_h = FLANGE_DROP + 0.3
    flange = make_tapped_flange(
        c,
        "_flange",
        FLANGE_OUT,
        SHELF_Y,
        hang_h,
        (SLOT + FLANGE_OUT / 2.0, M8_Y, 0.3 - hang_h / 2.0),
        d=M8_TAP_D,
        pitch=M8_PITCH,
        steps=24,
    )
    # 外竖板只倒底端游离两角；顶上与横档连接处不倒。
    hang_fils = [
        make_yz_fillet_cutter(c, "_fil_ob0", SLOT + FLANGE_OUT / 2.0, y0, -FLANGE_DROP, FLANGE_OUT, 1.0, 1.0),
        make_yz_fillet_cutter(c, "_fil_ob1", SLOT + FLANGE_OUT / 2.0, y1, -FLANGE_DROP, FLANGE_OUT, -1.0, 1.0),
    ]
    bool_float(flange, hang_fils, "DIFFERENCE")
    bool_union(br, [flange], solver="FLOAT")
    mesh_cleanup(br, fill_holes=False)
    br.name = "TdsH_Bracket"
    mat(br, (0.58, 0.68, 0.74, 1))
    return br


def build_probe(c):
    z_top = RISE + SHELF_T + 18.0
    z_bot = -DROP - SHELF_T - 12.0
    h = z_top - z_bot
    o = cyl_obj(c, "TdsH_TDS", R_TDS - 0.4, h, (HOLE_X, 0.0, (z_top + z_bot) / 2), (0, 0, 0), segs=20)
    mat(o, (0.55, 0.58, 0.62, 1))


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


def build_m8_bolts(c):
    rot = Euler((0.0, math.radians(-90.0), 0.0), "XYZ")
    x_head = SLOT + FLANGE_OUT
    m8_z = -M8_Z_FROM_WEB
    bolt = make_iso_hex_bolt(c, "TdsH_M8", d=8.0, pitch=M8_PITCH, thread_len=M8_THREAD_LEN)
    bolt.rotation_euler = rot
    bolt.location = (x_head, M8_Y, m8_z)


def park_along_rim(dy):
    for o in bpy.data.objects:
        if o.name.startswith("TdsH"):
            o.location.y += dy


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
        r.view_location = Vector((-10, PARK_Y, -40))
        r.view_distance = 280
        r.view_rotation = Euler((math.radians(70), 0, math.radians(125)), "XYZ").to_quaternion()


def export_stl():
    out = []
    o = bpy.data.objects.get("TdsH_Bracket")
    if o:
        loc = o.location.copy()
        o.location = (0.0, 0.0, 0.0)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, "TdsH_Bracket.stl"), export_selected_objects=True)
        o.location = loc
        out.append("TdsH_Bracket.stl")
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    clear_tdsh()
    c = col()
    build_bracket(c)
    build_probe(c)
    build_m8_bolts(c)
    park_along_rim(PARK_Y)
    frame()
    return export_stl()


if __name__ == "__main__" or True:
    RESULT = {"stl": build(), "shelf": (SHELF_X, SHELF_Y), "hole_x": HOLE_X}
