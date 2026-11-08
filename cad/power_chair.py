"""Full-size concept: a retrofit kit that turns a standard manual wheelchair into an EEG-controlled one
with a supervised autopilot (presentation renders, not for printing).

The chair is an ordinary folding wheelchair (24" rear wheels with push rims, 8" front casters, sling seat
and back, push handles, armrests, swing-away footrests), because the point is to upgrade the chair people
already have. The kit adds: hub-motor rear wheels on quick-release axles, a battery pack under the seat,
a controller/compute box (EEG decoder, co-pilot, motor control) on the back of the backrest, a forward
camera on the front frame, a microphone on a push handle, an SSVEP direction screen on a swing-away arm
(up/down/left/right arrows, STOP in the middle), and anti-tip bars.

Parts are modelled in mm under an empty scaled 1:1000, so lights and cameras work in metres. Run inside Blender:
    exec(open(r"C:\\Coding Projects\\neurotech\\cad\\power_chair.py").read())
Builds the model in collection "power_chair" and renders presentation images to cad/renders/.
"""
import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

OUT = r"C:\Coding Projects\neurotech\cad\renders"
COLL = "power_chair"

# ---------------------------------------------------------------- dimensions (mm); x right, y forward, z up
RAIL_X = 235.0                                   # side-frame tube centres (18" seat)
SEAT_Z, SEAT_Y0, SEAT_Y1 = 485.0, -210.0, 230.0
WHEEL_R, WHEEL_X, WHEEL_Y, WHEEL_Z = 305.0, 292.0, -175.0, 305.0     # 24" rear wheels
CASTER_R, CASTER_Y, CASTER_TRAIL = 100.0, 250.0, 35.0                # 8" front casters

PALETTE = {
    "steel": dict(color=(0.025, 0.025, 0.028), metallic=0.7, rough=0.35),
    "fabric": dict(color=(0.018, 0.018, 0.02), metallic=0.0, rough=0.95),
    "grip": dict(color=(0.03, 0.03, 0.03), metallic=0.0, rough=0.75),
    "tyre": dict(color=(0.015, 0.015, 0.015), metallic=0.0, rough=0.85),
    "alu": dict(color=(0.78, 0.79, 0.8), metallic=1.0, rough=0.28),
    "kit": dict(color=(0.2, 0.21, 0.23), metallic=0.75, rough=0.32),
    "accent": dict(color=(1.0, 0.33, 0.04), metallic=0.1, rough=0.35),
    "glass": dict(color=(0.005, 0.005, 0.008), metallic=0.0, rough=0.25),
    "red": dict(color=(0.75, 0.02, 0.02), metallic=0.0, rough=0.35),
    "yellow": dict(color=(1.0, 0.75, 0.0), metallic=0.0, rough=0.4),
    "led_green": dict(color=(0.1, 1.0, 0.35), emit=6.0),
    "screen_white": dict(color=(1.0, 1.0, 1.0), emit=4.0),
    "screen_red": dict(color=(1.0, 0.08, 0.05), emit=4.0),
    "screen_pad": dict(color=(0.12, 0.13, 0.16), metallic=0.0, rough=0.6),
    "screen_text": dict(color=(1.0, 1.0, 1.0), emit=3.0),
    "led_orange": dict(color=(1.0, 0.45, 0.05), emit=6.0),
    "floor": dict(color=(0.82, 0.83, 0.85), metallic=0.0, rough=0.6),
}


def material(key):
    name = f"pc_{key}"
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    p = PALETTE[key]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    rgba = (*p["color"], 1.0)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Metallic"].default_value = p.get("metallic", 0.0)
    bsdf.inputs["Roughness"].default_value = p.get("rough", 0.5)
    if "emit" in p:
        for nm in ("Emission Color", "Emission"):
            if nm in bsdf.inputs:
                bsdf.inputs[nm].default_value = rgba
                break
        bsdf.inputs["Emission Strength"].default_value = p["emit"]
    mat.diffuse_color = rgba
    return mat


# ---------------------------------------------------------------- mesh helpers
def new_obj(name, bm, mat, smooth=False, bevel=0.0, parent=True):
    if smooth:
        for f in bm.faces:
            f.smooth = len(f.verts) == 4
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.data.collections[COLL].objects.link(ob)
    if parent:
        ob.parent = bpy.data.objects["power_chair_root"]
    me.materials.append(material(mat))
    if bevel:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width, mod.segments = bevel, 3
        mod.limit_method = "ANGLE"
    return ob


def box(name, mat, c, size, rot=None, bevel=4.0):
    bm = bmesh.new()
    m = Matrix.Translation(c) @ (rot or Matrix.Identity(4)) @ Matrix.Diagonal((*size, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    return new_obj(name, bm, mat, bevel=bevel)


def cyl(name, mat, c, r, h, axis="Z", seg=48, r2=None, bevel=0.0):
    bm = bmesh.new()
    turn = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
            "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=h,
                          matrix=Matrix.Translation(c) @ turn)
    return new_obj(name, bm, mat, smooth=True, bevel=bevel)


def tube(name, mat, p0, p1, r=12.0):
    """Round frame tube between two points."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    bm = bmesh.new()
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=24, radius1=r, radius2=r, depth=d.length,
                          matrix=Matrix.Translation((p0 + p1) / 2) @ rot)
    return new_obj(name, bm, mat, smooth=True)


def torus(name, mat, c, R, rx, ry=None, axis="X", seg=72, ring=24):
    """Torus around an axis through c: major radius R, cross-section radii rx (along axis) and ry (radial)."""
    ry = ry or rx
    bm = bmesh.new()
    prof = []
    for i in range(ring):
        a = 2 * math.pi * i / ring
        prof.append(bm.verts.new((rx * math.cos(a), R + ry * math.sin(a), 0.0)))
    edges = [bm.edges.new((prof[i], prof[(i + 1) % ring])) for i in range(ring)]
    bmesh.ops.spin(bm, geom=prof + edges, cent=(0, 0, 0), axis=(1, 0, 0), angle=2 * math.pi, steps=seg,
                   use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.01)
    turn = {"X": Matrix.Identity(4), "Y": Matrix.Rotation(math.pi / 2, 4, "Z"),
            "Z": Matrix.Rotation(-math.pi / 2, 4, "Y")}[axis]
    bm.transform(Matrix.Translation(c) @ turn)
    for f in bm.faces:
        f.smooth = True
    return new_obj(name, bm, mat)



# ---------------------------------------------------------------- parts: the standard chair
def rear_wheel(side):
    """24" rear wheel, rebuilt around a hub motor (kit), with the hand push rim kept."""
    x = side * WHEEL_X
    c = Vector((x, WHEEL_Y, WHEEL_Z))
    torus(f"rear_tyre_{side}", "tyre", c, WHEEL_R - 16, 16, 16)
    torus(f"rear_rim_{side}", "steel", c, WHEEL_R - 36, 13, 10)
    torus(f"push_rim_{side}", "alu", c + Vector((side * 40, 0, 0)), WHEEL_R - 42, 7, 7)
    for i in range(6):                                       # push-rim standoffs
        rot = Matrix.Rotation(2 * math.pi * i / 6, 4, "X")
        tube(f"push_rim_tab_{side}_{i}", "alu", c + rot @ Vector((side * 6, 0, WHEEL_R - 40)),
             c + rot @ Vector((side * 36, 0, WHEEL_R - 42)), r=4)
    for i in range(12):                                      # mag spokes
        rot = Matrix.Rotation(2 * math.pi * i / 12 + 0.13, 4, "X")
        box(f"rear_spoke_{side}_{i}", "steel", c + rot @ Vector((0, 0, 190)), (12, 18, 150), rot=rot, bevel=3)
    # kit: hub motor replaces the plain hub (quick-release axle, so it swaps onto any standard chair)
    cyl(f"hub_motor_{side}", "kit", c, 112, 88, axis="X", seg=64, bevel=8)
    for dx in (-26, 0, 26):
        torus(f"hub_rib_{side}_{dx}", "kit", c + Vector((dx, 0, 0)), 112, 4, 4, seg=64, ring=12)
    torus(f"hub_ring_{side}", "accent", c + Vector((side * 45, 0, 0)), 78, 5, 5, seg=64, ring=12)
    cyl(f"hub_cap_{side}", "alu", c + Vector((side * 48, 0, 0)), 26, 10, axis="X", bevel=2)
    cyl(f"axle_{side}", "alu", c - Vector((side * 40, 0, 0)), 10, 50, axis="X")
    box(f"axle_plate_{side}", "steel", (side * (RAIL_X + 6), WHEEL_Y, WHEEL_Z), (10, 110, 130), bevel=4)


def caster(side):
    """8" front caster on a swivel fork."""
    x, y = side * RAIL_X, CASTER_Y
    wy = y - CASTER_TRAIL
    c = Vector((x, wy, CASTER_R))
    torus(f"caster_tyre_{side}", "tyre", c, CASTER_R - 16, 16, 16)
    cyl(f"caster_hub_{side}", "alu", c, 42, 30, axis="X")
    for i in range(5):
        rot = Matrix.Rotation(2 * math.pi * i / 5, 4, "X")
        box(f"caster_spoke_{side}_{i}", "steel", c + rot @ Vector((0, 0, 58)), (24, 12, 40), rot=rot, bevel=2)
    top = 2 * CASTER_R + 25
    for s in (-1, 1):
        tube(f"caster_fork_{side}_{s}", "steel", (x + s * 22, wy, CASTER_R), (x + s * 22, y, top), r=7)
    box(f"caster_crown_{side}", "steel", (x, y, top + 6), (60, 34, 14), bevel=4)
    cyl(f"caster_housing_{side}", "steel", (x, y, top + 45), 20, 70, bevel=3)


def frame(side):
    x = side * RAIL_X
    tube(f"lower_rail_{side}", "steel", (x, CASTER_Y + 5, 300), (x, WHEEL_Y - 40, 300))
    tube(f"front_upright_{side}", "steel", (x, CASTER_Y, 300), (x, SEAT_Y1, SEAT_Z))
    tube(f"seat_rail_{side}", "steel", (x, SEAT_Y0 - 10, SEAT_Z), (x, SEAT_Y1 + 10, SEAT_Z))
    post_top = Vector((x, -240, 920))
    tube(f"back_post_{side}", "steel", (x, -212, 300), post_top)
    tube(f"push_handle_{side}", "steel", post_top, (x, -320, 935))
    tube(f"grip_{side}", "grip", (x, -268, 925), (x, -330, 936), r=16)
    tube(f"arm_post_front_{side}", "steel", (x, 40, SEAT_Z), (x, 40, 700))
    tube(f"arm_post_rear_{side}", "steel", (x, -170, SEAT_Z), (x, -170, 700))
    box(f"armrest_{side}", "grip", (x, -62, 714), (56, 270, 32), bevel=12)
    box(f"side_panel_{side}", "fabric", (x - side * 9, -65, 590), (4, 228, 170), bevel=2)
    fx = side * (RAIL_X - 25)
    tube(f"footrest_hanger_{side}", "steel", (fx, SEAT_Y1 - 5, SEAT_Z - 10), (side * 205, 405, 230))
    tube(f"footrest_lower_{side}", "steel", (side * 205, 405, 230), (side * 195, 445, 150))
    box(f"footplate_{side}", "steel", (side * 115, 480, 142), (150, 115, 10), bevel=3)


def body():
    for a, b in (((-RAIL_X, -10, 310), (RAIL_X, -10, SEAT_Z - 8)), ((RAIL_X, -10, 310), (-RAIL_X, -10, SEAT_Z - 8))):
        tube(f"cross_brace_{a[0]:+.0f}", "steel", a, b, r=11)
    cyl("cross_pivot", "alu", (0, -10, (310 + SEAT_Z - 8) / 2), 9, 40, axis="Y")
    box("sling_seat", "fabric", (0, (SEAT_Y0 + SEAT_Y1) / 2, SEAT_Z + 6), (2 * RAIL_X + 12, SEAT_Y1 - SEAT_Y0, 8), bevel=3)
    lean = Matrix.Rotation(math.atan2(25, 620), 4, "X")
    box("sling_back", "fabric", (0, -224, 735), (2 * RAIL_X + 10, 8, 380), rot=lean, bevel=3)


# ---------------------------------------------------------------- parts: the retrofit kit
def flat(name, mat, pts2d, centre, rot, depth=-1.3):
    """Flat emissive shape on the screen plane: pts2d are (u right, v up) in mm; the screen faces -y locally."""
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(centre) + rot @ Vector((u, depth, v))) for u, v in pts2d]
    bm.faces.new(vs)
    return new_obj(name, bm, mat)


def label(name, text, size, centre, rot, offset, mat="screen_text"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body, cu.size, cu.align_x, cu.align_y = text, size, "CENTER", "CENTER"
    ob = bpy.data.objects.new(name, cu)
    bpy.data.collections[COLL].objects.link(ob)
    ob.parent = bpy.data.objects["power_chair_root"]
    ob.data.materials.append(material(mat))
    ob.matrix_basis = Matrix.Translation(Vector(centre) + rot @ Vector(offset)) @ rot @ Matrix.Rotation(math.pi / 2, 4, "X")
    return ob


def ssvep_screen(xr):
    """SSVEP direction screen: up/down/left/right arrows and STOP in the middle, each flickering at its own rate."""
    tube("kit_screen_post", "kit", (xr, 40, 700), (xr, 40, 728), r=11)              # swing-away arm
    tube("kit_screen_arm", "kit", (xr, 40, 728), (60, 342, 728), r=11)               # passes under the screen
    centre = Vector((0, 320, 840))
    rot = Matrix.Rotation(math.radians(-22), 4, "X")                              # tilted back toward the user
    box("kit_screen_body", "steel", centre, (270, 16, 190), rot=rot, bevel=8)
    box("kit_screen_vesa", "kit", centre + rot @ Vector((60, 12, -20)), (70, 10, 70), rot=rot, bevel=4)
    tube("kit_screen_clamp", "kit", (60, 342, 728), (60, 344, 815), r=9)             # up the back to the VESA plate
    face = centre + rot @ Vector((0, -8.5, 0))
    box("kit_screen_glass", "glass", face, (254, 1, 174), rot=rot, bevel=0)
    s = 34                                                                       # arrow size (mm)
    arrow = [(-0.17 * s, -0.5 * s), (0.17 * s, -0.5 * s), (0.17 * s, 0.05 * s), (0.42 * s, 0.05 * s),
             (0, 0.55 * s), (-0.42 * s, 0.05 * s), (-0.17 * s, 0.05 * s)]
    targets = {"up": ((0, 58), 0), "down": ((0, -58), 180), "left": ((-88, 0), 90), "right": ((88, 0), -90)}
    for name, ((cu, cv), ang) in targets.items():
        a = math.radians(ang)
        pts = [(cu + x * math.cos(a) - y * math.sin(a), cv + x * math.sin(a) + y * math.cos(a)) for x, y in arrow]
        sq = [(cu - 27, cv - 27), (cu + 27, cv - 27), (cu + 27, cv + 27), (cu - 27, cv + 27)]
        flat(f"ssvep_pad_{name}", "screen_pad", sq, face, rot, depth=-1.0)
        flat(f"ssvep_arrow_{name}", "screen_white", pts, face, rot, depth=-1.6)
    flat("ssvep_pad_stop", "screen_pad", [(-27, -27), (27, -27), (27, 27), (-27, 27)], face, rot, depth=-1.0)
    label("ssvep_stop_text", "STOP", 13, face, rot, (0, -2.2, 0), mat="screen_white")
    label("ssvep_hint", "look to move", 7, face, rot, (90, -2.2, -72))


def kit():
    # battery pack hung from the seat rails, under the sling
    box("kit_battery", "kit", (0, -40, 352), (330, 170, 78), bevel=12)
    box("kit_battery_stripe", "accent", (0, 46, 352), (300, 3, 14), bevel=1)
    box("kit_battery_led", "led_green", (130, 47, 372), (16, 3, 8), bevel=1)
    for s in (-1, 1):
        box(f"kit_battery_strap_{s}", "grip", (s * 150, -40, 438), (14, 44, 100), bevel=3)
    # controller + compute box (EEG decoder, co-pilot, motor control) on the back of the backrest
    box("kit_controller", "kit", (0, -262, 760), (250, 55, 175), bevel=12)
    box("kit_controller_stripe", "accent", (0, -290, 700), (200, 3, 12), bevel=1)
    box("kit_controller_leds", "led_green", (0, -290, 835), (150, 3, 8), bevel=1)
    for k in range(5):
        box(f"kit_vent_{k}", "steel", (-80 + 40 * k, -290, 770), (22, 3, 60), bevel=1)
    for side in (-1, 1):                                     # motor cables: controller -> down the back post -> hub
        tube(f"kit_cable_a_{side}", "grip", (side * 110, -262, 680), (side * (RAIL_X - 15), -215, 420), r=5)
        tube(f"kit_cable_b_{side}", "grip", (side * (RAIL_X - 15), -215, 420), (side * (RAIL_X + 20), WHEEL_Y + 40, WHEEL_Z + 60), r=5)
    tube("kit_cable_battery_a", "grip", (60, -125, 352), (60, -268, 420), r=6)      # behind the back sling
    tube("kit_cable_battery_b", "grip", (60, -268, 420), (60, -268, 675), r=6)
    xr = RAIL_X
    ssvep_screen(xr)
    # forward camera (co-pilot eye) clamped to the right front upright
    cam = Vector((xr + 4, CASTER_Y + 45, 430))
    box("kit_camera_clamp", "kit", (xr, CASTER_Y + 8, 430), (34, 40, 34), bevel=5)
    tube("kit_camera_arm", "kit", (xr, CASTER_Y + 20, 430), cam - Vector((0, 12, 0)), r=8)
    box("kit_camera", "steel", cam + Vector((0, 10, 0)), (71.8, 33.6, 50.8), bevel=5)
    cyl("kit_camera_lens", "glass", cam + Vector((-14, 28, 4)), 13, 8, axis="Y", bevel=1)
    # microphone (sound co-pilot) on the left push handle
    cyl("kit_mic", "kit", (-RAIL_X, -300, 962), 11, 40, bevel=2)
    cyl("kit_mic_grille", "alu", (-RAIL_X, -300, 990), 13, 16, bevel=2)
    # anti-tip bars (rear-wheel drive makes these important)
    for side in (-1, 1):
        x = side * RAIL_X
        tube(f"kit_antitip_{side}", "kit", (x, -212, 300), (x, -400, 140), r=10)
        cyl(f"kit_antitip_wheel_{side}", "grip", (x, -412, 110), 30, 24, axis="X")


# ---------------------------------------------------------------- build, stage, render
def reset():
    for o in list(bpy.data.objects):
        if o.name in ("Cube",) or (o.users_collection and o.users_collection[0].name == COLL):
            bpy.data.objects.remove(o)
    for n in ("floor",):
        if bpy.data.objects.get(n):
            bpy.data.objects.remove(bpy.data.objects[n])
    if COLL not in bpy.data.collections:
        bpy.context.scene.collection.children.link(bpy.data.collections.new(COLL))
    root = bpy.data.objects.new("power_chair_root", None)
    bpy.data.collections[COLL].objects.link(root)
    root.scale = (0.001, 0.001, 0.001)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sc.unit_settings.length_unit = "MILLIMETERS"


def stage():
    """Floor, world, lights and cameras for product shots."""
    sc = bpy.context.scene
    for n in ("floor", "key", "fill", "rim", "cam_hero", "cam_side", "cam_rear", "cam_motor", "cam_front", "cam_screen"):
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=6.0)
    new_obj("floor", bm, "floor", parent=False)
    world = sc.world or bpy.data.worlds.new("World")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.9, 0.91, 0.93, 1)
    bg.inputs[1].default_value = 0.55

    def light(name, kind, loc, energy, size, target=(0, 0, 0.45)):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        if kind == "AREA":
            ld.size = size
        ob = bpy.data.objects.new(name, ld)
        bpy.data.collections[COLL].objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    light("key", "AREA", (-1.8, 1.6, 2.2), 260, 1.5)
    light("fill", "AREA", (2.0, 0.9, 1.2), 90, 1.5)
    light("rim", "AREA", (0.3, -2.2, 1.8), 220, 1.2)
    bg.inputs[1].default_value = 0.3
    vs = sc.view_settings                                     # punchier, less washed-out product look
    for look in ("AgX - Punchy", "Punchy", "AgX - Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue
    vs.exposure = -0.2

    def cam(name, loc, target, lens=50):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start, cd.clip_end = 0.01, 50
        ob = bpy.data.objects.new(name, cd)
        bpy.data.collections[COLL].objects.link(ob)
        ob.location = loc
        ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return ob

    cam("cam_hero", (-1.75, 1.95, 1.2), (0, -0.02, 0.5), lens=42)
    cam("cam_side", (-3.0, -0.03, 0.62), (0, -0.03, 0.55), lens=50)
    cam("cam_rear", (1.75, -2.2, 1.35), (0, -0.1, 0.52), lens=42)
    cam("cam_motor", (1.25, 0.45, 0.8), (0.27, -0.17, 0.38), lens=45)
    cam("cam_front", (0.85, 1.25, 0.82), (0.2, 0.25, 0.48), lens=40)
    cam("cam_screen", (0.32, -0.32, 1.32), (0.0, 0.32, 0.83), lens=35)   # over the user's shoulder


def render(names=("cam_hero", "cam_side", "cam_rear", "cam_motor", "cam_front", "cam_screen"), res=(1920, 1080), samples=64):
    sc = bpy.context.scene
    os.makedirs(OUT, exist_ok=True)
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    try:
        sc.eevee.taa_render_samples = samples
    except AttributeError:
        pass
    written = []
    for n in names:
        sc.camera = bpy.data.objects[n]
        sc.render.filepath = os.path.join(OUT, f"power_chair_{n[4:]}.png")
        bpy.ops.render.render(write_still=True)
        written.append(sc.render.filepath)
    return written


def build():
    reset()
    for s in (-1, 1):
        rear_wheel(s)
        caster(s)
        frame(s)
    body()
    kit()
    stage()
    print("objects:", len(bpy.data.collections[COLL].objects))


build()
