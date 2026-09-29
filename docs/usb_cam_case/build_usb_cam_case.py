# iAqua USB 摄像头外壳。1 BU = 1 mm。
# 坐标：镜头 +Z 朝前，物理顶 +Y（阿卡），物理底 −Y（Type-C）。
# 内腔按 Cam_module 实件外包，单边 0.2 mm。不改 Cam_module。

import math
import os

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
STL_DIR = os.path.join(OUT_DIR, "stl")
os.makedirs(STL_DIR, exist_ok=True)
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_UsbCamCase.blend")
COL = "iAqua_UsbCamCase"

CLR = 0.2
WALL = 2.0
MIN_WALL = 1.6
DRAFT = math.tan(math.radians(1.0))
R_OUT = 0.8
R_IN = 0.5

# Cam_module 实测（不要改那些物体）
PCB_HALF = 16.0
MOUNT_TOP_Z = 3.0
PH_Z1 = -7.6
LENS_R = 7.0

Z_FRONT_IN = MOUNT_TOP_Z + CLR          # 3.2
Z_FRONT_OUT = Z_FRONT_IN + WALL         # 5.2
Z_CAV_BACK = PH_Z1 - CLR                # -7.8
Z_COVER_OUT = Z_FRONT_OUT - 30.0        # -24.8，总厚 30 含后盖
Z_BACK_OUT = Z_COVER_OUT + WALL         # -22.8

CAV_HALF_FRONT = PCB_HALF + CLR         # 16.2，前壁处最紧

OUT_HALF = 25.0
PCB_HOLE_C = 14.0
BOSS_R = 3.0                            # 连接柱外径 6
BOSS_Z1 = Z_FRONT_IN - 0.3              # 柱顶，板与座之间 0.3
BOSS_Z0 = Z_CAV_BACK                    # 柱底接后腔底

LENS_HOLE_R = LENS_R + CLR              # 7.2

# Type-C 面板（原附图）+ 单边 0.2
TC_CZ = -4.6
TC_PORT = (12.34 + 2 * CLR, 6.83 + 2 * CLR)
TC_FLANGE = (19.7 + 2 * CLR, 9.7 + 2 * CLR)
M2_R = (2.2 + 2 * CLR) / 2.0            # Ø2.6
M2_SP = 16.0
TC_RECESS = 1.2
TC_PAD = 0.8                            # 局部加厚，凹台后剩余壁 ≥ 1.6

ARCA_WIDE = 25.0
ARCA_NARROW = 19.0
ARCA_DOV = 6.0
ARCA_T = 10.0

MODULE_NAMES = (
    "CamPCB_Board", "CamLensMount", "CamLensMount_Boss", "CamMount_Thread",
    "CamLens", "CamLens_Thread", "CamLens_Glass", "CamPH_Shell", "CamPH_Pins",
)


def cav_half(z):
    return CAV_HALF_FRONT + DRAFT * (Z_FRONT_IN - z)


def outer_half(z):
    return cav_half(z) + WALL


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
    me = bpy.data.meshes.new(name)
    o = bpy.data.objects.new(name, me)
    link_obj(o, c)
    return o


def mat(o, rgba):
    n = "Cam_" + o.name
    mt = bpy.data.materials.get(n) or bpy.data.materials.new(n)
    mt.use_nodes = True
    bsdf = next(nd for nd in mt.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.45
    o.data.materials.clear()
    o.data.materials.append(mt)


def clear_cam():
    for o in list(bpy.data.objects):
        if o.type == "MESH" and (o.name.startswith("CamCase") or o.name.startswith("_")):
            bpy.data.objects.remove(o, do_unlink=True)


def put_bm(o, bm):
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def box_bm(x0, x1, y0, y1, z0, z1):
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in (
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    )]
    faces = (
        (0, 1, 2, 3), (4, 7, 6, 5),
        (0, 4, 5, 1), (1, 5, 6, 2),
        (2, 6, 7, 3), (3, 7, 4, 0),
    )
    for f in faces:
        bm.faces.new([v[i] for i in f])
    return bm


def frustum_bm(z0, z1, half0, half1):
    """z0 处半宽 half0，z1 处半宽 half1。方盒，四边面。"""
    bm = bmesh.new()
    v = [bm.verts.new(p) for p in (
        (-half0, -half0, z0), (half0, -half0, z0), (half0, half0, z0), (-half0, half0, z0),
        (-half1, -half1, z1), (half1, -half1, z1), (half1, half1, z1), (-half1, half1, z1),
    )]
    faces = (
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
    )
    for f in faces:
        bm.faces.new([v[i] for i in f])
    return bm


def cyl_bm(r, z0, z1, segs=48, x=0.0, y=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(z1 - z0),
        matrix=Matrix.Translation(Vector((x, y, (z0 + z1) / 2.0))),
    )
    return bm


def y_cyl_bm(r, y0, y1, segs=32, x=0.0, z=0.0):
    bm = bmesh.new()
    mx = Matrix.Translation(Vector((x, (y0 + y1) / 2.0, z))) @ Euler((math.pi / 2, 0, 0), "XYZ").to_matrix().to_4x4()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=(y1 - y0), matrix=mx,
    )
    return bm


def mesh_from_bm(c, name, bm):
    o = new_mesh(name, c)
    put_bm(o, bm)
    return o


def bake_bool(host, others, op, solver="EXACT"):
    for i, ot in enumerate(others):
        mod = host.modifiers.new(f"b{i}", "BOOLEAN")
        mod.operation = op
        mod.solver = solver
        mod.object = ot
        ot.hide_set(True)
    bpy.context.view_layer.update()
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
    return host


def manifold_counts(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bd = sum(1 for e in bm.edges if e.is_boundary)
    sides = {}
    for f in bm.faces:
        n = len(f.verts)
        sides[n] = sides.get(n, 0) + 1
    bm.free()
    return nm, bd, sides


def bevel_edges(o, offset, segs=3):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.edges.ensure_lookup_table()
    geom = list(bm.edges)
    bmesh.ops.bevel(
        bm, geom=geom, offset=offset, offset_type="OFFSET", segments=segs,
        profile=0.5, affect="EDGES", clamp_overlap=True, loop_slide=True,
    )
    put_bm(o, bm)


def quadrangulate(o):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.001)
    ng = [f for f in bm.faces if len(f.verts) > 4]
    if ng:
        bmesh.ops.triangulate(bm, faces=ng, quad_method="BEAUTY", ngon_method="BEAUTY")
    tris = [f for f in bm.faces if len(f.verts) == 3]
    if tris:
        bmesh.ops.join_triangles(
            bm, faces=tris,
            angle_face_threshold=math.radians(8),
            angle_shape_threshold=math.radians(170),
            cmp_seam=False, cmp_sharp=False, cmp_uvs=False, cmp_vcols=False, cmp_materials=False,
        )
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def build_body(c):
    y_back = outer_half(Z_CAV_BACK)
    tower = mesh_from_bm(
        c, "CamCase_Body",
        frustum_bm(Z_CAV_BACK - 0.25, Z_FRONT_OUT, outer_half(Z_CAV_BACK), outer_half(Z_FRONT_OUT)),
    )
    # 后壁补到 25×25，与后盖同外形
    back_fill = mesh_from_bm(
        c, "_backfill",
        box_bm(-OUT_HALF, OUT_HALF, -OUT_HALF, OUT_HALF, Z_BACK_OUT, Z_CAV_BACK),
    )
    # +Y 阿卡座：宽 38、厚 2.0，贴在顶壁外面
    pad_y0 = y_back - 0.3
    pad = mesh_from_bm(
        c, "_ypad",
        box_bm(-ARCA_NARROW, ARCA_NARROW, pad_y0, pad_y0 + WALL, Z_CAV_BACK, Z_FRONT_OUT),
    )
    # −Y 局部加厚，给 Type-C 法兰凹台留够壁厚
    y_out = outer_half(TC_CZ)
    pad_tc = mesh_from_bm(
        c, "_tcpad",
        box_bm(
            -TC_FLANGE[0] / 2.0 - 1.2, TC_FLANGE[0] / 2.0 + 1.2,
            -(y_out + TC_PAD), -(y_out - 0.4),
            TC_CZ - TC_FLANGE[1] / 2.0 - 1.0, TC_CZ + TC_FLANGE[1] / 2.0 + 1.0,
        ),
    )
    # PCB 四角连接柱，顶到板下，M2 螺丝从后腔拧入
    bosses = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            bosses.append(mesh_from_bm(
                c, f"_boss{sx}{sy}",
                cyl_bm(BOSS_R, BOSS_Z0, BOSS_Z1, segs=32, x=sx * PCB_HOLE_C, y=sy * PCB_HOLE_C),
            ))
    bake_bool(tower, [back_fill, pad, pad_tc] + bosses, "UNION")
    bevel_edges(tower, R_OUT, segs=3)

    cut_back_z = Z_COVER_OUT - 0.4
    cutter = mesh_from_bm(
        c, "_cav",
        frustum_bm(cut_back_z, Z_FRONT_IN, cav_half(cut_back_z), cav_half(Z_FRONT_IN)),
    )
    bevel_edges(cutter, R_IN, segs=2)
    bake_bool(tower, [cutter], "DIFFERENCE")

    lens = mesh_from_bm(c, "_lenshole", cyl_bm(LENS_HOLE_R, Z_FRONT_IN - 0.4, Z_FRONT_OUT + 0.4, segs=48))
    bake_bool(tower, [lens], "DIFFERENCE")

    # 出线槽只开在 −Y 侧壁，底边停在后腔之前
    slot = mesh_from_bm(
        c, "_slot",
        box_bm(-13.2, 7.4, -15.6, -(y_out + TC_PAD + 0.6), -7.45, -1.0),
    )
    bake_bool(tower, [slot], "DIFFERENCE")

    recess = mesh_from_bm(
        c, "_tcrecess",
        box_bm(
            -TC_FLANGE[0] / 2.0, TC_FLANGE[0] / 2.0,
            -(y_out + TC_PAD + 0.4), -(y_out + TC_PAD - TC_RECESS),
            TC_CZ - TC_FLANGE[1] / 2.0, TC_CZ + TC_FLANGE[1] / 2.0,
        ),
    )
    port = mesh_from_bm(
        c, "_tcport",
        box_bm(
            -TC_PORT[0] / 2.0, TC_PORT[0] / 2.0,
            -15.6, -(y_out + TC_PAD + 0.8),
            TC_CZ - TC_PORT[1] / 2.0, TC_CZ + TC_PORT[1] / 2.0,
        ),
    )
    bake_bool(tower, [recess, port], "DIFFERENCE")

    m2s = []
    for sx in (-1, 1):
        m2s.append(mesh_from_bm(
            c, f"_m2{sx}",
            y_cyl_bm(M2_R, -(y_out + TC_PAD + 0.5), -(y_out - 0.2), segs=24, x=sx * M2_SP / 2.0, z=TC_CZ),
        ))
    bake_bool(tower, m2s, "DIFFERENCE")

    # PCB 四角对应的 M2 连接孔，贯穿连接柱
    holes = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            holes.append(mesh_from_bm(
                c, f"_ph{sx}{sy}",
                cyl_bm(M2_R, BOSS_Z0 - 0.3, BOSS_Z1 + 0.3, segs=24, x=sx * PCB_HOLE_C, y=sy * PCB_HOLE_C),
            ))
    bake_bool(tower, holes, "DIFFERENCE")
    quadrangulate(tower)
    mat(tower, (0.16, 0.17, 0.18, 1.0))
    return tower


def build_back(c):
    """后盖：50×50 平板 + 定位凸台（PH 插座处让开）。四角不打孔。"""
    half_win = cav_half(Z_CAV_BACK) - CLR
    plate = mesh_from_bm(
        c, "CamCase_Back",
        box_bm(-OUT_HALF, OUT_HALF, -OUT_HALF, OUT_HALF, Z_COVER_OUT, Z_BACK_OUT),
    )
    bevel_edges(plate, R_OUT, segs=2)
    boss = mesh_from_bm(
        c, "_boss",
        box_bm(-half_win, half_win, -half_win, half_win, Z_BACK_OUT - 0.15, Z_BACK_OUT + 1.6),
    )
    # 插座投影：凸台在 PH2.0 处让开，不切穿底板
    notch = mesh_from_bm(
        c, "_notch",
        box_bm(-12.6, -1.6, -half_win - 0.2, -9.8, Z_BACK_OUT + 0.15, Z_BACK_OUT + 2.0),
    )
    bake_bool(plate, [boss], "UNION")
    bake_bool(plate, [notch], "DIFFERENCE")
    quadrangulate(plate)
    mat(plate, (0.22, 0.23, 0.24, 1.0))
    return plate


def build_arca(c):
    y_seat = outer_half(Z_CAV_BACK) - 0.3 + WALL
    y_bot = y_seat - 0.35
    y_stem = y_seat + (ARCA_T - ARCA_DOV)
    y_tip = y_seat + ARCA_T
    z0, z1 = Z_BACK_OUT, Z_FRONT_OUT
    ring = [
        (-ARCA_NARROW, y_bot), (ARCA_NARROW, y_bot),
        (ARCA_NARROW, y_stem), (ARCA_WIDE, y_tip),
        (-ARCA_WIDE, y_tip), (-ARCA_NARROW, y_stem),
    ]
    bm = bmesh.new()
    bot = [bm.verts.new((p[0], p[1], z0)) for p in ring]
    top = [bm.verts.new((p[0], p[1], z1)) for p in ring]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    n = len(ring)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bot[i], bot[j], top[j], top[i]))
    ends = [f for f in bm.faces if len(f.verts) == 6]
    for f in ends:
        vs = list(f.verts)
        bm.faces.remove(f)
        bm.faces.new((vs[0], vs[1], vs[2], vs[3]))
        bm.faces.new((vs[0], vs[3], vs[4], vs[5]))
    o = mesh_from_bm(c, "CamCase_Arca", bm)
    mat(o, (0.12, 0.12, 0.13, 1.0))
    return o


def build_tc_dummy(c):
    """示意母口，不参与打印。装在 −Y 凹台里，不突出加厚面。"""
    y_out = outer_half(TC_CZ)
    y_face = -(y_out + TC_PAD)
    body = mesh_from_bm(
        c, "CamCase_TC_Panel",
        box_bm(
            -TC_FLANGE[0] / 2.0 + 0.15, TC_FLANGE[0] / 2.0 - 0.15,
            y_face + 0.05, y_face + TC_RECESS - 0.05,
            TC_CZ - TC_FLANGE[1] / 2.0 + 0.15, TC_CZ + TC_FLANGE[1] / 2.0 - 0.15,
        ),
    )
    mat(body, (0.75, 0.76, 0.78, 1.0))
    return body


def module_fingerprint():
    out = {}
    for n in MODULE_NAMES:
        o = bpy.data.objects.get(n)
        if o is None:
            out[n] = None
            continue
        out[n] = (len(o.data.vertices), tuple(round(v, 3) for v in o.location))
    return out


def aabb(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    xs, ys, zs = [], [], []
    for v in me.vertices:
        p = mw @ v.co
        xs.append(p.x)
        ys.append(p.y)
        zs.append(p.z)
    ev.to_mesh_clear()
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def check_assembly(before):
    body = bpy.data.objects["CamCase_Body"]
    back = bpy.data.objects["CamCase_Back"]
    bb, bk = aabb(body), aabb(back)
    r = {
        "body_z": (round(bb[4], 2), round(bb[5], 2)),
        "back_z": (round(bk[4], 2), round(bk[5], 2)),
        "body_xy": (round(bb[1] - bb[0], 2), round(bb[3] - bb[2], 2)),
        "module_unchanged": module_fingerprint() == before,
        "manifold": {
            "CamCase_Body": manifold_counts(body),
            "CamCase_Back": manifold_counts(back),
            "CamCase_Arca": manifold_counts(bpy.data.objects["CamCase_Arca"]),
        },
    }
    pcb = aabb(bpy.data.objects["CamPCB_Board"])
    ph = aabb(bpy.data.objects["CamPH_Shell"])
    lens = aabb(bpy.data.objects["CamLens"])
    r["pcb_inside_x"] = pcb[0] > -CAV_HALF_FRONT and pcb[1] < CAV_HALF_FRONT
    r["pcb_inside_y"] = pcb[2] > -CAV_HALF_FRONT and pcb[3] < CAV_HALF_FRONT
    r["ph_behind_cleared"] = ph[4] > Z_CAV_BACK - 0.05
    r["lens_through_front"] = lens[5] > Z_FRONT_OUT
    r["front_xy"] = (round(bb[1] - bb[0], 2), round(bb[3] - bb[2], 2))
    r["total_z"] = round(Z_FRONT_OUT - Z_COVER_OUT, 2)
    r["pcb_hole_d"] = M2_R * 2
    r["pcb_hole_c"] = PCB_HOLE_C
    r["boss_d"] = BOSS_R * 2
    r["wall"] = WALL
    r["clearance"] = CLR
    return r


def frame_assembled():
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name.startswith("CamCase_TC"):
            o.hide_set(False)
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "MATERIAL"
        r = sp.region_3d
        r.view_perspective = "PERSP"
        r.view_location = Vector((0, -4, 0))
        r.view_distance = 90
        r.view_rotation = Euler((math.radians(68), 0, math.radians(-32)), "XYZ").to_quaternion()


def export_stl():
    names = [
        ("CamCase_Body", "CamCase_Body.stl"),
        ("CamCase_Back", "CamCase_Back.stl"),
        ("CamCase_Arca", "CamCase_Arca.stl"),
    ]
    out = []
    for name, fn in names:
        o = bpy.data.objects[name]
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.wm.stl_export(filepath=os.path.join(STL_DIR, fn), export_selected_objects=True)
        out.append(fn)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    return out


def build():
    mm_units()
    before = module_fingerprint()
    clear_cam()
    c = col()
    build_body(c)
    build_back(c)
    build_arca(c)
    build_tc_dummy(c)
    frame_assembled()
    stl = export_stl()
    return {"stl": stl, "check": check_assembly(before)}


if __name__ == "__main__":
    RESULT = build()
