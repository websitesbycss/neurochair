"""Parametric Sphero-driven tabletop wheelchair, built in Blender.

Main chair: two Sphero BOLTs (73 mm balls) are the front drive wheels, two swivel casters at the back.
Mini chair: one BOLT at the front centre, same casters. Both ride on the balls through a cone seat
("ring"), a low-friction ring contact that lets the ball spin freely underneath while it pushes the
chair along. Every part prints without supports; assembly is glue only (locating ribs/tenons make
the joints self-align and load the glue in shear).

Units: 1 Blender unit = 1 mm. Run inside Blender:
    exec(open(r"C:\\Coding Projects\\neurotech\\cad\\wheelchair.py").read())
Builds both assemblies (main at x=0, mini at x=+350) and writes print-oriented STLs to cad/stl/.
"""
import math
import os
import struct

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = r"C:\Coding Projects\neurotech\cad"
OUT = os.path.join(HERE, "stl")

# ---------------- shared geometry ----------------
BOLT_R = 36.5            # Sphero BOLT radius (73 mm ball)
SEAT_DEG = 50.0          # ring contacts the ball on a circle 50 deg down from its top
RING_R = 40.0            # max footprint radius (clearance checks)
RING_WALL = 3.5          # cone-shell wall thickness
BOSS_R = 12.0            # solid boss on top of the ring (tenon socket / glue face)
RING_Z0 = 55.0           # ring bottom face (ball contact circle is ~5 mm above this)
PLATE_T = 6.0            # side-frame plate thickness
GAP = 0.3                # clearance per side on locating features
BED = (238.0, 200.0)     # Prusa CORE One bed (250 x 220) with a safe margin

# swivel caster (shared by both chairs); local frame: pivot axis at x=y=0, wheel trails toward -y
WHEEL_D, WHEEL_W, TRAIL = 40.0, 10.0, 20.0
AXLE_Z = WHEEL_D / 2
FORK_TOP0, FORK_TOP1 = 43.0, 49.0      # fork top plate (bears against the frame leg at z=49)
PIN_AF = 6.0                           # octagonal pivot pin, across flats
PIN_Z0 = 40.0                          # pin tip
STUB_R = 3.0                           # wheel axle stub radius (wheel bore +0.3)

MAIN = dict(
    name="main", px=75.0, bolts=[(-75.0, 50.0), (75.0, 50.0)], ring_top=104.0, ring_mode="tenon",
    rail_y=(-86.0, 106.0), rail_z=(144.0, 156.0), rear_y=-80.0, leg_w=12.0,
    back=dict(z0=150.0, z1=258.0, lean=12.0, w=12.0), handle=dict(back=18.0, z=(246.0, 256.0)),
    arm=dict(y=(-74.0, 50.0), z=(205.0, 213.0), post_y=(38.0, 50.0)),
    front_leg=dict(w=16.0, tenon=(12.0, 8.0)),
    hanger=dict(y=(94.0, 104.0), z0=52.0, foot_y1=116.0, foot_t=6.0),
    seat=dict(y=(-86.0, 66.0), t=2.0), backpanel=dict(z=(170.0, 250.0), t=2.0),
    foot_t=3.0,
)
MINI = dict(
    name="mini", px=50.0, bolts=[(0.0, 20.0)], ring_top=105.0, ring_mode="flat",
    rail_y=(-72.0, 74.0), rail_z=(92.0, 104.0), rear_y=-66.0, leg_w=10.0,
    back=dict(z0=98.0, z1=190.0, lean=10.0, w=10.0), handle=dict(back=14.0, z=(180.0, 188.0)),
    arm=dict(y=(-60.0, 34.0), z=(140.0, 147.0), post_y=(24.0, 34.0)),
    front_leg=None,
    hanger=dict(y=(66.0, 74.0), z0=44.0, foot_y1=88.0, foot_t=6.0),
    seat=dict(y=(-72.0, 62.0), t=2.4), backpanel=dict(z=(120.0, 185.0), t=2.0),
    foot_t=3.0,
)

COLORS = {"frame": (0.75, 0.75, 0.78, 1), "seat": (0.15, 0.15, 0.18, 1), "ring": (0.95, 0.45, 0.1, 1),
          "caster": (0.08, 0.08, 0.08, 1), "bolt": (0.2, 0.45, 0.95, 1)}


# ---------------- mesh helpers ----------------
def _material(key):
    name = f"wc_{key}"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = COLORS[key]
    if mat.use_nodes and mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs[0].default_value = COLORS[key]
    return mat


def _obj(name, bm, coll, color=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if color:
        me.materials.append(_material(color))
    return ob


def box(x0, x1, y0, y1, z0, z1, m=None):
    bm = bmesh.new()
    mat = Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)) @ Matrix.Diagonal(
        (x1 - x0, y1 - y0, z1 - z0, 1.0))
    bmesh.ops.create_cube(bm, size=1.0, matrix=(m @ mat) if m else mat)
    return bm


def cyl(r, h, center, axis="Z", seg=64, r2=None, rot=0.0):
    bm = bmesh.new()
    turn = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
            "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    mat = Matrix.Translation(center) @ turn @ Matrix.Rotation(rot, 4, "Z")
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=seg, radius1=r,
                          radius2=r if r2 is None else r2, depth=h, matrix=mat)
    return bm


def _bar_bm(sx, sy, sz, m):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=m @ Matrix.Diagonal((sx, sy, sz, 1.0)))
    return bm


def _solver(mod):
    ids = [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties["solver"].enum_items]
    mod.solver = "EXACT" if "EXACT" in ids else ids[0]


def _bake(ob):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    for m in old.materials:
        me.materials.append(m)
    bpy.data.meshes.remove(old)


def combine(name, coll, color, solids, cutters=()):
    """Union a list of bmeshes, then subtract cutters. Returns one object."""
    base = _obj(name, solids[0], coll, color)
    tmp = []
    for bm in solids[1:]:
        o = _obj(name + "_u", bm, coll)
        mod = base.modifiers.new("u", "BOOLEAN")
        mod.operation = "UNION"
        mod.object = o
        _solver(mod)
        tmp.append(o)
    for bm in cutters:
        o = _obj(name + "_c", bm, coll)
        mod = base.modifiers.new("c", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = o
        _solver(mod)
        tmp.append(o)
    if tmp:
        _bake(base)
    for o in tmp:
        bpy.data.objects.remove(o)
    return base


# ---------------- parts ----------------
def ring(name, coll, cx, cy, top, mode):
    a = math.radians(SEAT_DEG)
    zc = BOLT_R + BOLT_R * math.cos(a)
    rc = BOLT_R * math.sin(a)
    k = math.tan(a)
    za = zc + rc * k                      # cone apex (solid above this)
    zb = RING_Z0 - 1.0
    rb = rc + (zc - zb) / k
    dr = RING_WALL / math.sin(a)          # horizontal offset that gives a constant wall
    za_o = za + dr * k
    shell = cyl(rb + dr, za_o - zb, (cx, cy, (za_o + zb) / 2), seg=96, r2=0.0)
    boss = cyl(BOSS_R, top - (za - 6.0), (cx, cy, (top + za - 6.0) / 2), seg=64)
    floor = box(cx - 50, cx + 50, cy - 50, cy + 50, zb - 10, RING_Z0)     # trims the shell flat at its base
    cone = cyl(rb, za - zb, (cx, cy, (za + zb) / 2), seg=96, r2=0.0)
    cut = [cone, floor]
    if mode == "tenon":
        tx, ty, td = PLATE_T / 2 + GAP, MAIN["front_leg"]["tenon"][0] / 2 + GAP, MAIN["front_leg"]["tenon"][1] + 0.5
        assert top - td > za + 1.0, "tenon slot would break into the ball cavity"
        cut.append(box(cx - tx, cx + tx, cy - ty, cy + ty, top - td, top + 1))
    return combine(name, coll, "ring", [shell, boss], cut)


def side_frame(name, coll, P):
    x0, x1 = P["px"] - PLATE_T / 2, P["px"] + PLATE_T / 2
    ry0, ry1 = P["rail_y"]
    rz0, rz1 = P["rail_z"]
    w = P["leg_w"]
    ry = P["rear_y"]
    B = P["back"]
    s = [box(x0, x1, ry0, ry1, rz0, rz1),                                   # seat rail
         box(x0, x1, ry - w / 2, ry + w / 2, FORK_TOP1, rz1)]                # rear leg
    # octagonal swivel pin under the rear leg
    rcorner = PIN_AF / 2 / math.cos(math.pi / 8)
    s.append(cyl(rcorner, FORK_TOP1 - PIN_Z0 + 0.5, (P["px"], ry, (FORK_TOP1 + PIN_Z0 + 0.5) / 2), seg=8,
                 rot=math.pi / 8))
    # backrest post (leans back) and push handle
    top = (ry - B["lean"], B["z1"])
    s.append(_bar_bm(PLATE_T, math.hypot(B["lean"], B["z1"] - B["z0"]), B["w"],
                     Matrix.Translation((P["px"], ry - B["lean"] / 2, (B["z0"] + B["z1"]) / 2))
                     @ Matrix.Rotation(math.atan2(B["z1"] - B["z0"], -B["lean"]), 4, "X")))
    hz0, hz1 = P["handle"]["z"]
    s.append(box(x0, x1, top[0] - P["handle"]["back"], top[0] + B["w"] / 2, hz0, hz1))
    # armrest and its front post
    a = P["arm"]
    s.append(box(x0, x1, a["y"][0], a["y"][1], a["z"][0], a["z"][1]))
    s.append(box(x0, x1, a["post_y"][0], a["post_y"][1], rz0, a["z"][1]))
    # footrest hanger (vertical) and foot bar
    h = P["hanger"]
    s.append(box(x0, x1, h["y"][0], h["y"][1], h["z0"], rz1))
    s.append(box(x0, x1, h["y"][0], h["foot_y1"], h["z0"], h["z0"] + h["foot_t"]))
    # front leg down to the ring, with a glue tenon (main chair only)
    if P["front_leg"]:
        fl = P["front_leg"]
        by = P["bolts"][0][1]
        s.append(box(x0, x1, by - fl["w"] / 2, by + fl["w"] / 2, P["ring_top"], rz1))
        ty, td = fl["tenon"]
        s.append(box(x0, x1, by - ty / 2, by + ty / 2, P["ring_top"] - td, P["ring_top"]))
    return combine(name, coll, "frame", s)


def ribs_between(px, y0, y1, z_top, depth):
    """Two locating ribs that drop just inside the side plates."""
    xi = px - PLATE_T / 2 - GAP
    return [box(-xi, -xi + 3.0, y0, y1, z_top - depth, z_top), box(xi - 3.0, xi, y0, y1, z_top - depth, z_top)]


def seat_pan(name, coll, P):
    xo = P["px"] + PLATE_T / 2 + 3.0
    y0, y1 = P["seat"]["y"]
    z0 = P["rail_z"][1]
    z1 = z0 + P["seat"]["t"]
    solids = [box(-xo, xo, y0, y1, z0, z1)] + ribs_between(P["px"], y0 + 6, y1 - 6, z0, 4.0)
    cut = []
    if P["ring_mode"] == "flat":      # mini: ring top glues into a shallow locating recess
        (bx, by), = P["bolts"]
        cut.append(cyl(BOSS_R + GAP, 2 * (P["ring_top"] - z0), (bx, by, z0), seg=64))
        # keep ribs clear of the ring
    return combine(name, coll, "seat", solids, cut)


def back_panel(name, coll, P):
    B = P["back"]
    ang = math.atan2(B["lean"], B["z1"] - B["z0"])             # lean-back angle
    t = P["backpanel"]["t"]
    z0, z1 = P["backpanel"]["z"]
    xo = P["px"] + PLATE_T / 2 + 3.0
    xi = P["px"] - PLATE_T / 2 - GAP
    # build upright in local coords: panel front face at y=0, back face y=-t, ribs behind it
    solids = [box(-xo, xo, -t, 0, 0, z1 - z0),
              box(-xi, -xi + 3.0, -t - 4.0, -t, 6, z1 - z0 - 6), box(xi - 3.0, xi, -t - 4.0, -t, 6, z1 - z0 - 6)]
    ob = combine(name, coll, "seat", solids)
    # place against the front face of the leaning posts
    zc = z0
    post_y = P["rear_y"] - B["lean"] * (zc - B["z0"]) / (B["z1"] - B["z0"])
    off = B["w"] / 2 + t
    m = Matrix.Translation((0, post_y + off * math.cos(ang), zc + off * math.sin(ang))) @ Matrix.Rotation(ang, 4, "X")
    ob.data.transform(m)
    return ob, m.inverted()


def footplate(name, coll, P):
    h = P["hanger"]
    xo = P["px"] + PLATE_T / 2 + 3.0
    z0 = h["z0"] + h["foot_t"]
    solids = [box(-xo, xo, h["y"][0], h["foot_y1"], z0, z0 + P["foot_t"])] + \
        ribs_between(P["px"], h["y"][0] + 3, h["foot_y1"] - 3, z0, 4.0)
    return combine(name, coll, "seat", solids)


def caster_parts(prefix, coll, px, py):
    """Fork, wheel, wheel cap and pivot cap, placed at the pivot (px, py)."""
    T = Matrix.Translation((px, py, 0))
    fork = combine(prefix + "fork", coll, "caster", [
        box(-7.5, 10.5, -TRAIL - 7.0, 7.0, FORK_TOP0, FORK_TOP1, m=T),                 # top plate
        box(6.5, 10.5, -TRAIL - 6.0, -TRAIL + 6.0, AXLE_Z - 10.0, FORK_TOP0 + 0.01, m=T),  # arm
        cyl(STUB_R, 16.0, (px + 6.5 - 8.0, py - TRAIL, AXLE_Z), axis="X", seg=48)],     # axle stub
        [cyl(PIN_AF / 2 / math.cos(math.pi / 8) + 0.35, 20, (px, py, (FORK_TOP0 + FORK_TOP1) / 2), seg=48)])
    wheel = combine(prefix + "wheel", coll, "caster", [
        cyl(WHEEL_D / 2, WHEEL_W, (px, py - TRAIL, AXLE_Z), axis="X", seg=96)],
        [cyl(STUB_R + 0.3, WHEEL_W + 2, (px, py - TRAIL, AXLE_Z), axis="X", seg=48)] +
        [cyl(3.5, WHEEL_W + 2, (px, py - TRAIL + 12 * math.cos(i * math.pi / 3),
                                AXLE_Z + 12 * math.sin(i * math.pi / 3)), axis="X", seg=24) for i in range(6)])
    wcap = combine(prefix + "wheelcap", coll, "caster", [
        cyl(5.5, 4.5, (px - 6.5 - 2.25, py - TRAIL, AXLE_Z), axis="X", seg=48)],
        [cyl(STUB_R + 0.15, 3.5 * 2, (px - 6.5, py - TRAIL, AXLE_Z), axis="X", seg=48)])
    pcap = combine(prefix + "pivotcap", coll, "caster", [
        cyl(6.0, 5.0, (px, py, PIN_Z0 - 2.5 + 2.5), seg=48)],
        [cyl(PIN_AF / 2 / math.cos(math.pi / 8) + 0.05, 2 * (FORK_TOP0 - 0.5 - (PIN_Z0 - 0.5)),
             (px, py, FORK_TOP0 - 0.5), seg=48)])
    return fork, wheel, wcap, pcap


# ---------------- assembly + export ----------------
def reset_collection(name):
    coll = bpy.data.collections.get(name)
    if coll:
        for o in list(coll.objects):
            bpy.data.objects.remove(o)
    else:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def build_chair(P, offset_x=0.0):
    coll = reset_collection(f"wheelchair_{P['name']}")
    parts = {}  # name -> (object, count, print_rotation)
    n = P["name"]
    sf = side_frame(f"{n}_side_frame", coll, P)
    sf.data.transform(Matrix.Translation((0, 0, 0)))
    parts["side_frame"] = (sf, 2, Matrix.Rotation(-math.pi / 2, 4, "Y"))  # plate flat on the bed
    other = side_frame(f"{n}_side_frame_L", coll, dict(P, px=-P["px"]))    # visual only (identical part)
    for i, (bx, by) in enumerate(P["bolts"]):
        r = ring(f"{n}_ring_{i}", coll, bx, by, P["ring_top"], P["ring_mode"])
        if i == 0:
            parts["ring"] = (r, len(P["bolts"]), Matrix.Identity(4))
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=BOLT_R,
                                  matrix=Matrix.Translation((bx, by, BOLT_R)))
        _obj(f"{n}_REF_sphero_bolt_{i}", bm, coll, "bolt")
    parts["seat_pan"] = (seat_pan(f"{n}_seat_pan", coll, P), 1, Matrix.Rotation(math.pi, 4, "X"))
    bp, pre = back_panel(f"{n}_back_panel", coll, P)
    parts["back_panel"] = (bp, 1, Matrix.Rotation(-math.pi / 2, 4, "X") @ pre)
    parts["footplate"] = (footplate(f"{n}_footplate", coll, P), 1, Matrix.Rotation(math.pi, 4, "X"))
    for side in (1, -1):
        f, w, wc, pc = caster_parts(f"{n}_caster{'R' if side > 0 else 'L'}_", coll, side * P["px"], P["rear_y"])
        if side > 0:
            parts["caster_fork"] = (f, 2, Matrix.Rotation(math.pi / 2, 4, "Y"))
            parts["caster_wheel"] = (w, 2, Matrix.Rotation(math.pi / 2, 4, "Y"))
            parts["caster_wheelcap"] = (wc, 2, Matrix.Rotation(-math.pi / 2, 4, "Y"))
            parts["caster_pivotcap"] = (pc, 2, Matrix.Identity(4))
    for o in coll.objects:
        o.location.x += offset_x
    return parts


def _fit(rot, ob):
    """Pick an in-plane rotation so the part fits the bed; return full print matrix and footprint."""
    pts = [rot @ v.co for v in ob.data.vertices]
    best = None
    for deg in range(0, 180, 1):
        rz = Matrix.Rotation(math.radians(deg), 3, "Z")
        q = [rz @ p for p in pts]
        xs, ys = [p.x for p in q], [p.y for p in q]
        sx, sy = max(xs) - min(xs), max(ys) - min(ys)
        ok = (sx <= BED[0] and sy <= BED[1])
        score = (0 if ok else 1, max(sx / BED[0], sy / BED[1]))
        if best is None or score < best[0]:
            best = (score, deg, sx, sy)
        if ok and deg == 0:
            break
    _, deg, sx, sy = best
    rz = Matrix.Rotation(math.radians(deg), 4, "Z")
    q = [rz @ rot @ v.co for v in ob.data.vertices]
    mn = Vector((min(p.x for p in q), min(p.y for p in q), min(p.z for p in q)))
    mx = Vector((max(p.x for p in q), max(p.y for p in q), max(p.z for p in q)))
    t = Matrix.Translation((-(mn.x + mx.x) / 2, -(mn.y + mx.y) / 2, -mn.z))
    return t @ rz @ rot, (mx - mn), best[0][0] == 0


def write_stl(path, ob, m):
    me = ob.data
    me.calc_loop_triangles()
    verts = [m @ v.co for v in me.vertices]
    with open(path, "wb") as f:
        f.write(b"neurotech wheelchair".ljust(80, b" "))
        f.write(struct.pack("<I", len(me.loop_triangles)))
        for tri in me.loop_triangles:
            a, b, c = (verts[i] for i in tri.vertices)
            nrm = (b - a).cross(c - a)
            nrm = nrm.normalized() if nrm.length > 0 else nrm
            f.write(struct.pack("<12fH", *nrm, *a, *b, *c, 0))


def export(parts, tag):
    os.makedirs(OUT, exist_ok=True)
    report = []
    for key, (ob, count, rot) in parts.items():
        m, size, fits = _fit(rot, ob)
        path = os.path.join(OUT, f"{tag}_{key}_x{count}.stl")
        write_stl(path, ob, m)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        vol = bm.calc_volume(signed=False) / 1000.0
        bm.free()
        report.append((os.path.basename(path), count, tuple(round(v, 1) for v in size), round(vol, 1), fits))
    return report


def setup_scene():
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 0.001
    sc.unit_settings.length_unit = "MILLIMETERS"
    for name in ("Cube",):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o)
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == "VIEW_3D":
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.clip_start, sp.clip_end = 0.5, 20000


def build_all():
    setup_scene()
    main = build_chair(MAIN, 0.0)
    mini = build_chair(MINI, 350.0)
    rep = export(main, "main") + export(mini, "mini")
    for r in rep:
        print(r)
    return rep


REPORT = build_all()
