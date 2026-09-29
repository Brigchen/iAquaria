# iAqua auto-feeder: parametric millimetre assembly for Blender 5.x
# 1 Blender unit = 1 mm (scene.unit_settings.scale_length = 0.001)
# Run via Blender MCP execute_blender_code or: blender --python build_feeder.py

import math
import os
from mathutils import Euler, Vector

import bpy
import bmesh

OUT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else r"C:\Users\brigc\WorkBuddy\python\iAqua\iAqua\docs\feeder"
STL_DIR = os.path.join(OUT_DIR, "stl")
BLEND_PATH = os.path.join(OUT_DIR, "iAqua_Feeder.blend")
GLB_PATH = os.path.join(OUT_DIR, "iAqua_Feeder.glb")
os.makedirs(STL_DIR, exist_ok=True)

COL_NAME = "iAqua_Feeder"

# --- dimensions mm ---
HOPPER_R1 = 35.0
HOPPER_R2 = 19.0
HOPPER_H = 80.0
WALL = 1.6
LID_R = 37.0
LID_H = 6.0
HOUSING_R = 31.0
HOUSING_H = 42.0
DISC_R = 25.0
DISC_H = 8.0
POCKET_R = 4.0
PCD = 16.0
N_POCKETS = 8
SHAFT_R = 1.55
MOTOR_XYZ = (12.0, 10.0, 15.0)
GEAR_R, GEAR_H = 6.0, 12.0
CHUTE_R, CHUTE_L = 6.0, 45.0
EXPLODE = True  # screenshot: gap between stages


def mm_units():
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    s.unit_settings.scale_length = 0.001
    s.unit_settings.length_unit = "MILLIMETERS"


def clear_meshes():
    for obj in list(bpy.data.objects):
        if obj.type in {"MESH", "EMPTY"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for mat in list(bpy.data.materials):
        if mat.name.endswith("_mat") or mat.name.startswith("Feeder"):
            bpy.data.materials.remove(mat)


def collection():
    if COL_NAME not in bpy.data.collections:
        col = bpy.data.collections.new(COL_NAME)
        bpy.context.scene.collection.children.link(col)
    return bpy.data.collections[COL_NAME]


def link(obj, col):
    if obj.name not in col.objects:
        col.objects.link(obj)
    sc = bpy.context.scene.collection
    if obj.name in sc.objects:
        sc.objects.unlink(obj)
    return obj


def mat(obj, rgba, rough=0.42):
    name = "Feeder_" + obj.name
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = rough
    obj.data.materials.clear()
    obj.data.materials.append(m)


def new_mesh(name, col):
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    link(obj, col)
    return obj


def bm_to(obj, bm):
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def add_cyl(bm, loc, r, h, segs=32, cap=True):
    return bmesh.ops.create_cone(
        bm,
        cap_ends=cap,
        cap_tris=False,
        segments=segs,
        radius1=r,
        radius2=r,
        depth=h,
        matrix=_t(loc),
    )


def _t(loc, rot=(0, 0, 0)):
    from mathutils import Matrix

    return Matrix.Translation(Vector(loc)) @ Euler(rot, "XYZ").to_matrix().to_4x4()


def boolean_diff(host, cutters):
    for i, c in enumerate(cutters):
        mod = host.modifiers.new(f"bool{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "FLOAT"
        mod.object = c
        c.hide_set(True)
        c.hide_render = True
        c.display_type = "WIRE"
    dg = bpy.context.evaluated_depsgraph_get()
    ev = host.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = host.data
    host.modifiers.clear()
    host.data = baked
    bpy.data.meshes.remove(old)
    for c in cutters:
        mesh = c.data
        bpy.data.objects.remove(c, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def solidify(obj, thick, offset=-1.0):
    mod = obj.modifiers.new("Solidify", "SOLIDIFY")
    mod.thickness = thick
    mod.offset = offset
    mod.use_quality_normals = True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    baked = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = baked
    bpy.data.meshes.remove(old)


def origin_geometry(obj):
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="MEDIAN")
    obj.select_set(False)


def build():
    mm_units()
    clear_meshes()
    col = collection()
    petg = (0.72, 0.82, 0.78, 1)
    disc_c = (0.32, 0.42, 0.52, 1)
    motor_c = (0.18, 0.18, 0.2, 1)
    clamp_c = (0.55, 0.54, 0.48, 1)
    shaft_c = (0.75, 0.75, 0.78, 1)

    # Hopper (thin cone shell)
    hop = new_mesh("Hopper", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=False,
        cap_tris=False,
        segments=40,
        radius1=HOPPER_R1,
        radius2=HOPPER_R2,
        depth=HOPPER_H,
        matrix=_t((0, 0, 0)),
    )
    bm_to(hop, bm)
    solidify(hop, WALL, -1)
    hop.location = (0, 0, 120)
    mat(hop, petg, 0.35)

    # Lid
    lid = new_mesh("Lid", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=40, radius1=LID_R, radius2=LID_R, depth=LID_H, matrix=_t((0, 0, 0))
    )
    inner = bmesh.ops.create_cone(
        bm, cap_ends=True, segments=32, radius1=33, radius2=33, depth=4, matrix=_t((0, 0, -2))
    )
    bmesh.ops.delete(bm, geom=inner["verts"], context="VERTS")  # keep as solid lid + lip via second mesh
    bm_to(lid, bm)
    # lip cutter
    lip = new_mesh("_lid_cut", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=32, radius1=33.5, radius2=33.5, depth=4.5, matrix=_t((0, 0, -1.2))
    )
    bm_to(lip, bm)
    boolean_diff(lid, [lip])
    lid.location = (0, 0, 163)
    mat(lid, (0.85, 0.88, 0.86, 1), 0.3)

    # Housing + bottom plate + outlet
    housing = new_mesh("Housing", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=40,
        radius1=HOUSING_R,
        radius2=HOUSING_R,
        depth=HOUSING_H,
        matrix=_t((0, 0, 0)),
    )
    bm_to(housing, bm)
    inner_h = new_mesh("_h_in", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        segments=36,
        radius1=HOUSING_R - WALL,
        radius2=HOUSING_R - WALL,
        depth=HOUSING_H - 3,
        matrix=_t((0, 0, 1.2)),
    )
    bm_to(inner_h, bm)
    outlet = new_mesh("_outlet", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=16, radius1=4.5, radius2=4.5, depth=12, matrix=_t((16, 0, -HOUSING_H / 2))
    )
    bm_to(outlet, bm)
    boolean_diff(housing, [inner_h, outlet])
    housing.location = (0, 0, 59)
    mat(housing, petg, 0.4)

    # Disc with 8 pockets + D-shaft
    disc = new_mesh("Disc", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=48, radius1=DISC_R, radius2=DISC_R, depth=DISC_H, matrix=_t((0, 0, 0))
    )
    bm_to(disc, bm)
    cutters = []
    for i in range(N_POCKETS):
        ang = i * (2 * math.pi / N_POCKETS)
        x, y = PCD * math.cos(ang), PCD * math.sin(ang)
        c = new_mesh(f"_pkt{i}", col)
        bm = bmesh.new()
        bmesh.ops.create_cone(
            bm, cap_ends=True, segments=16, radius1=POCKET_R, radius2=POCKET_R, depth=DISC_H + 4, matrix=_t((x, y, 0))
        )
        bm_to(c, bm)
        cutters.append(c)
    shaft = new_mesh("_shaft", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=24, radius1=SHAFT_R, radius2=SHAFT_R, depth=DISC_H + 6, matrix=_t((0, 0, 0))
    )
    bm_to(shaft, bm)
    cutters.append(shaft)
    boolean_diff(disc, cutters)
    disc.location = (0, 0, 78)
    mat(disc, disc_c, 0.5)

    # Motor N20 body
    motor = new_mesh("Motor_N20", col)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= MOTOR_XYZ[0]
        v.co.y *= MOTOR_XYZ[1]
        v.co.z *= MOTOR_XYZ[2]
    bm_to(motor, bm)
    motor.location = (0, 0, 28)
    mat(motor, motor_c, 0.55)

    gear = new_mesh("Gearbox", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=20, radius1=GEAR_R, radius2=GEAR_R, depth=GEAR_H, matrix=_t((0, 0, 0))
    )
    bm_to(gear, bm)
    gear.location = (0, 0, 42)
    mat(gear, motor_c, 0.5)

    dshaft = new_mesh("D_Shaft", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=16, radius1=1.5, radius2=1.5, depth=10, matrix=_t((0, 0, 0))
    )
    bm_to(dshaft, bm)
    dshaft.location = (0, 0, 53)
    mat(dshaft, shaft_c, 0.25)

    coupler = new_mesh("Coupler", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=20, radius1=4.5, radius2=4.5, depth=10, matrix=_t((0, 0, 0))
    )
    bm_to(coupler, bm)
    ccut = new_mesh("_cpl", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=True, segments=16, radius1=1.6, radius2=1.6, depth=12, matrix=_t((0, 0, 0))
    )
    bm_to(ccut, bm)
    boolean_diff(coupler, [ccut])
    coupler.location = (0, 0, 62)
    mat(coupler, disc_c, 0.45)

    mount = new_mesh("MotorMount", col)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 28
        v.co.y *= 22
        v.co.z *= 8
    bm_to(mount, bm)
    mcut = new_mesh("_mc", col)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 13
        v.co.y *= 11
        v.co.z *= 10
    bm_to(mcut, bm)
    boolean_diff(mount, [mcut])
    mount.location = (0, 0, 18)
    mat(mount, petg, 0.45)

    chute = new_mesh("Chute", col)
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm, cap_ends=False, segments=20, radius1=CHUTE_R, radius2=CHUTE_R, depth=CHUTE_L, matrix=_t((0, 0, 0))
    )
    bm_to(chute, bm)
    solidify(chute, 1.4, 1)
    chute.location = (28, 0, 18)
    chute.rotation_euler = Euler((0, math.radians(50), 0), "XYZ")
    mat(chute, petg, 0.4)

    clamp = new_mesh("Clamp", col)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 40
        v.co.y *= 12
        v.co.z *= 25
    bm_to(clamp, bm)
    jaw = new_mesh("_jaw", col)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x *= 42
        v.co.y *= 10
        v.co.z *= 12
    bm_to(jaw, bm)
    jaw.location = (0, 6, -4)
    boolean_diff(clamp, [jaw])
    clamp.location = (0, -45, 20)
    mat(clamp, clamp_c, 0.5)

    if EXPLODE:
        lid.location.z += 36
        hop.location.z += 18
        disc.location.z += 10
        coupler.location.z += 4
        chute.location.x += 18
        clamp.location.y -= 18
        motor.location.z -= 8
        mount.location.z -= 10

    frame_view()
    light_setup()
    return [o.name for o in col.objects]


def frame_view():
    target = Vector((0, -10, 90))
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.clip_start = 1
        space.clip_end = 5000
        space.shading.type = "MATERIAL"
        space.overlay.show_overlays = True
        r3d = space.region_3d
        r3d.view_perspective = "PERSP"
        r3d.view_location = target
        r3d.view_distance = 320
        r3d.view_rotation = Euler((math.radians(62), 0, math.radians(42)), "XYZ").to_quaternion()
    cam = bpy.data.objects.get("Camera")
    if cam:
        cam.location = (210, -250, 180)
        cam.rotation_euler = Euler((math.radians(68), 0, math.radians(38)), "XYZ")
        cam.data.clip_start = 1
        cam.data.clip_end = 5000
        cam.data.lens = 50


def light_setup():
    light = bpy.data.objects.get("Light")
    if light:
        light.location = (80, -120, 260)
        light.data.energy = 800
        light.data.type = "AREA"
        try:
            light.data.size = 120
        except Exception:
            pass
    if "Fill" not in bpy.data.objects:
        data = bpy.data.lights.new("Fill", "AREA")
        data.energy = 250
        try:
            data.size = 80
        except Exception:
            pass
        fill = bpy.data.objects.new("Fill", data)
        bpy.context.scene.collection.objects.link(fill)
        fill.location = (-140, 40, 200)


def export_stls():
    names = ["Hopper", "Lid", "Housing", "Disc", "MotorMount", "Chute", "Clamp", "Coupler"]
    col = bpy.data.collections[COL_NAME]
    # restore compact pose for STL? keep exploded — user wants print parts, each object origin independent
    for name in names:
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        path = os.path.join(STL_DIR, f"{name}.stl")
        bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in col.objects:
        if not o.name.startswith("_"):
            o.select_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.export_scene.gltf(filepath=GLB_PATH, export_format="GLB", use_selection=False)
    return os.listdir(STL_DIR)


if __name__ == "__main__" or True:
    parts = build()
    files = export_stls()
    RESULT = {"parts": parts, "stl": files, "blend": BLEND_PATH}
