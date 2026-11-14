"""Builds the scale objects of the planner view in Blender and writes them as OBJ files.

Own design, made from primitives and turned profiles by this script: a generic four-legged
lander (faceted body in foil, four legs with footpads, descent engine bell, propellant
tanks, a high-gain dish, two upright solar panels, small thrusters), the parts of a
deployable mast (base, a pole of 1 m that the scene stretches to the observer height of
the package, and a camera head) and four boulders. No real vehicle is copied; there are
no logos or markings. The objects only give a sense of scale: they are not part of any
package and take no part in the horizon comparison.

Run inside Blender (4.1 or later):

    blender --background --python make_scale_objects.py

Output: unreal/Content/LsnModels/*.obj, metres, Z up, the origin on the ground under the
object, with smooth normals (sharp where two faces meet at more than 35 degrees) and
bevelled edges. Each face group carries one of the material names of PALETTE; the scene
gives each its colour and reads the normals as written.
"""

import math
import os
import random

import bpy
from mathutils import Vector

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Content", "LsnModels"))
PALETTE = ("foil", "metal", "dark", "panel", "rock")
SHARP = math.radians(35.0)


def material(name):
    return bpy.data.materials.get("lsn_" + name) or bpy.data.materials.new("lsn_" + name)


def finish(obj, mat, bevel=0.0, segments=2):
    """Material, a bevel on the hard edges, smooth shading with those edges kept sharp."""
    obj.data.materials.append(material(mat))
    bpy.context.view_layer.objects.active = obj
    if bevel > 0.0:
        modifier = obj.modifiers.new("bevel", "BEVEL")
        modifier.width = bevel
        modifier.segments = segments
        modifier.limit_method = "ANGLE"
        modifier.angle_limit = SHARP
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.set_sharp_from_angle(angle=SHARP)
    return obj


def cylinder(radius, depth, location, mat, vertices=32, rotation=(0.0, 0.0, 0.0), radius_top=None, bevel=0.0):
    if radius_top is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=radius_top, depth=depth, location=location, rotation=rotation)
    return finish(bpy.context.object, mat, bevel)


def box(size, location, mat, rotation=(0.0, 0.0, 0.0), bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    obj = bpy.context.object
    obj.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, mat, bevel)


def sphere(radius, location, mat, scale=(1.0, 1.0, 1.0), segments=16):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=segments // 2, radius=radius, location=location)
    obj = bpy.context.object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, mat)


def lathe(profile, location, mat, segments=48, rotation=(0.0, 0.0, 0.0)):
    """A body of revolution about Z from a profile of (radius, height) points, open at both ends."""
    verts, faces = [], []
    for radius, height in profile:
        for k in range(segments):
            angle = 2.0 * math.pi * k / segments
            verts.append((radius * math.cos(angle), radius * math.sin(angle), height))
    for row in range(len(profile) - 1):
        for k in range(segments):
            a, b = row * segments + k, row * segments + (k + 1) % segments
            faces.append((a, b, b + segments, a + segments))
    mesh = bpy.data.meshes.new("lathe")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("lathe", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    return finish(obj, mat)


def strut(a, b, radius, mat, vertices=16):
    a, b = Vector(a), Vector(b)
    axis = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=axis.length, location=(a + b) / 2)
    obj = bpy.context.object
    obj.rotation_euler = axis.to_track_quat("Z", "Y").to_euler()
    return finish(obj, mat)


def join(name, parts):
    bpy.ops.object.select_all(action="DESELECT")
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    obj = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    obj.name = name
    return obj


def export(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    path = os.path.join(OUT, obj.name + ".obj")
    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=True, forward_axis="Y", up_axis="Z", export_triangulated_mesh=True,
                          export_normals=True, export_uv=False, export_materials=True, apply_modifiers=True)
    mtl = os.path.join(OUT, obj.name + ".mtl")
    if os.path.exists(mtl):
        os.remove(mtl)  # the scene has its own colours
    return path


def bell(z_top, z_bottom, r_throat, r_exit, steps=14):
    """Profile of a bell nozzle: narrow at the top, opening downwards along a parabola."""
    return [(r_throat + (r_exit - r_throat) * math.sqrt(i / steps), z_top + (z_bottom - z_top) * i / steps) for i in range(steps + 1)]


def make_lander():
    """A generic lander, 3.85 m high: faceted body in foil on four legs, with what a lander of that size carries."""
    turn = (0, 0, math.radians(22.5))
    parts = [
        # Body: an eight-sided box in foil with a narrower deck on top, edges bevelled.
        cylinder(1.45, 0.95, (0, 0, 1.55), "foil", vertices=8, rotation=turn, bevel=0.035),
        cylinder(1.05, 0.45, (0, 0, 2.25), "metal", vertices=8, rotation=turn, bevel=0.025),
        cylinder(1.50, 0.05, (0, 0, 1.05), "metal", vertices=8, rotation=turn, bevel=0.012),   # lower frame ring
        cylinder(1.50, 0.05, (0, 0, 2.03), "metal", vertices=8, rotation=turn, bevel=0.012),   # upper frame ring
        # Descent engine: mount, throat and bell, opening down.
        cylinder(0.30, 0.25, (0, 0, 1.12), "metal", vertices=32, bevel=0.01),
        lathe(bell(1.02, 0.42, 0.13, 0.56), (0, 0, 0), "dark"),
        lathe([(0.56, 0.42), (0.585, 0.42), (0.585, 0.46)], (0, 0, 0), "metal"),                 # stiffening ring at the exit
    ]
    for k in range(4):
        angle = math.radians(45 + 90 * k)
        c, s = math.cos(angle), math.sin(angle)
        foot = (2.35 * c, 2.35 * s, 0.10)
        # Main strut in two diameters (the lower one telescopes), two side struts, a dished footpad.
        knee = (1.85 * c, 1.85 * s, 0.86)
        parts.append(strut((1.30 * c, 1.30 * s, 1.75), knee, 0.065, "metal", vertices=24))
        parts.append(strut(knee, foot, 0.048, "metal", vertices=24))
        parts.append(sphere(0.075, knee, "metal"))
        for side in (-1, 1):
            a2 = angle + side * math.radians(28)
            parts.append(strut((1.32 * math.cos(a2), 1.32 * math.sin(a2), 1.15), (2.05 * c, 2.05 * s, 0.45), 0.032, "metal"))
        parts.append(lathe([(0.0, 0.05), (0.26, 0.035), (0.36, 0.06), (0.38, 0.10), (0.36, 0.105), (0.25, 0.075), (0.0, 0.085)], (foot[0], foot[1], -0.035), "metal"))
        parts.append(sphere(0.07, foot, "metal"))
        # Propellant tanks between the legs, each under a strap.
        a3 = angle + math.radians(45)
        tank = (1.02 * math.cos(a3), 1.02 * math.sin(a3), 1.55)
        parts.append(sphere(0.42, tank, "metal", scale=(1.0, 1.0, 1.12), segments=40))
        parts.append(lathe([(0.425, -0.03), (0.432, -0.03), (0.432, 0.03), (0.425, 0.03)], tank, "dark"))
        # A cluster of small thrusters at each corner of the deck.
        corner = Vector((1.18 * c, 1.18 * s, 2.36))
        parts.append(box((0.16, 0.16, 0.14), corner, "metal", rotation=(0, 0, angle), bevel=0.01))
        for direction in ((c, s, 0.0), (-s, c, 0.0), (s, -c, 0.0), (0.0, 0.0, 1.0)):
            d = Vector(direction)
            nozzle = lathe(bell(0.0, 0.10, 0.012, 0.038, steps=5), corner + 0.08 * d, "dark", segments=20)
            nozzle.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
            parts.append(nozzle)
    # Upright solar panels on short booms: near the pole the Sun is always low. Cells in a frame.
    for side in (-1, 1):
        y = side * 1.0
        parts.append(strut((0, y, 2.45), (0, y, 2.78), 0.035, "metal"))
        parts.append(box((1.56, 0.035, 1.16), (0, y, 3.30), "metal", bevel=0.008))
        for i in range(6):
            for j in range(4):
                parts.append(box((0.235, 0.012, 0.255), (-0.625 + 0.25 * i, y + side * 0.02, 2.885 + 0.277 * j), "panel"))
                parts.append(box((0.235, 0.012, 0.255), (-0.625 + 0.25 * i, y - side * 0.02, 2.885 + 0.277 * j), "panel"))
    # High-gain dish on a boom with a feed on three thin struts, tilted towards the Earth's side.
    parts.append(strut((0.55, 0, 2.45), (0.55, 0, 3.02), 0.035, "metal"))
    parts.append(sphere(0.06, (0.55, 0, 3.04), "metal"))
    tilt = (0, math.radians(35), 0)
    dish = lathe([(0.0, 0.0)] + [(0.40 * i / 10, 0.16 * (i / 10) ** 2) for i in range(1, 11)] + [(0.405, 0.165), (0.40, 0.17)], (0.55, 0, 3.08), "metal", rotation=tilt)
    parts.append(dish)
    axis = Vector((math.sin(math.radians(35)), 0, math.cos(math.radians(35))))
    feed = Vector((0.55, 0, 3.08)) + 0.36 * axis
    parts.append(sphere(0.035, feed, "dark"))
    for k in range(3):
        a = math.radians(120 * k)
        rim = Vector((0.36 * math.cos(a), 0.36 * math.sin(a), 0.13))
        rim.rotate(bpy.data.objects[dish.name].rotation_euler)
        parts.append(strut(Vector((0.55, 0, 3.08)) + rim, feed, 0.007, "metal", vertices=8))
    # A low-gain antenna and a small camera on the deck.
    parts.append(strut((-0.6, 0.35, 2.47), (-0.6, 0.35, 3.05), 0.012, "metal", vertices=10))
    parts.append(box((0.18, 0.14, 0.14), (-0.75, -0.4, 2.55), "dark", bevel=0.012))
    parts.append(cylinder(0.045, 0.08, (-0.87, -0.4, 2.55), "panel", vertices=20, rotation=(0, math.radians(90), 0)))
    return join("lander", parts)


def make_mast():
    base_parts = [cylinder(0.09, 0.50, (0, 0, 0.45), "metal", vertices=24, bevel=0.008)]
    for k in range(3):
        angle = math.radians(90 + 120 * k)
        base_parts.append(strut((0.07 * math.cos(angle), 0.07 * math.sin(angle), 0.55), (0.75 * math.cos(angle), 0.75 * math.sin(angle), 0.03), 0.025, "metal"))
        base_parts.append(lathe([(0.0, 0.02), (0.07, 0.012), (0.09, 0.03), (0.0, 0.035)], (0.75 * math.cos(angle), 0.75 * math.sin(angle), 0.0), "metal", segments=24))
    base = join("mast_base", base_parts)
    pole = join("mast_pole", [cylinder(0.035, 1.0, (0, 0, 0.5), "metal", vertices=20)])   # 1 m; stretched by the scene
    head = join("mast_head", [
        # A camera head at the observer height: body, lens barrel with a glass front, a sun shade, a pan and tilt yoke.
        box((0.24, 0.17, 0.17), (0, 0, 0.0), "dark", bevel=0.015),
        cylinder(0.062, 0.12, (0.17, 0, 0.0), "metal", vertices=28, rotation=(0, math.radians(90), 0), bevel=0.004),
        cylinder(0.050, 0.01, (0.232, 0, 0.0), "panel", vertices=28, rotation=(0, math.radians(90), 0)),
        box((0.10, 0.19, 0.012), (0.19, 0, 0.095), "dark", bevel=0.003),
        box((0.06, 0.02, 0.20), (0, 0.105, -0.04), "metal", bevel=0.004),
        box((0.06, 0.02, 0.20), (0, -0.105, -0.04), "metal", bevel=0.004),
        cylinder(0.05, 0.06, (0, 0, -0.14), "metal", vertices=24, bevel=0.004),
        box((0.03, 0.55, 0.38), (-0.06, 0, -0.45), "panel", bevel=0.004),   # small upright solar panel below the head
        strut((0, 0, 0.08), (0, 0, 0.45), 0.008, "metal", vertices=8),      # antenna
    ])
    return [base, pole, head]


def make_boulder(index, radius, seed, flat=0.7):
    """A lump of rock: a sphere pushed out and in by a few broad lumps and many small ones, flattened, sunk a little."""
    rng = random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=radius, location=(0, 0, 0))
    obj = bpy.context.object
    broad = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(), rng.uniform(-0.30, 0.24)) for _ in range(9)]
    small = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(), rng.uniform(-0.07, 0.07)) for _ in range(40)]
    squash = Vector((rng.uniform(0.85, 1.25), rng.uniform(0.75, 1.1), rng.uniform(flat - 0.12, flat + 0.12)))
    for vertex in obj.data.vertices:
        direction = vertex.co.normalized()
        bump = sum(amount * max(direction.dot(axis), 0.0) ** 3 for axis, amount in broad)
        bump += sum(amount * max(direction.dot(axis), 0.0) ** 24 for axis, amount in small)
        vertex.co = Vector((direction.x * squash.x, direction.y * squash.y, direction.z * squash.z)) * radius * (1.0 + bump)
    lowest = min(v.co.z for v in obj.data.vertices)
    for vertex in obj.data.vertices:
        vertex.co.z -= lowest + 0.12 * radius    # sits a little into the ground
    obj.data.materials.append(material("rock"))
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.set_sharp_from_angle(angle=math.radians(50.0))   # a few hard breaks stay
    obj.name = f"boulder_{index}"
    return obj


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = bpy.data.scenes.get("LsnScaleObjects") or bpy.data.scenes.new("LsnScaleObjects")
    if bpy.context.window:
        bpy.context.window.scene = scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    objects = [make_lander()] + make_mast() + [make_boulder(1, 0.55, 11), make_boulder(2, 0.32, 23), make_boulder(3, 0.85, 37, flat=0.6), make_boulder(4, 0.45, 53, flat=0.95)]
    report = {}
    for obj in objects:
        path = export(obj)
        low = [min(v.co[i] for v in obj.data.vertices) for i in range(3)]
        high = [max(v.co[i] for v in obj.data.vertices) for i in range(3)]
        report[obj.name] = {"file": path, "triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons), "size_m": [round(high[i] - low[i], 2) for i in range(3)]}
    # Set out side by side for a look at them.
    for i, obj in enumerate(objects):
        obj.location.x = 4.0 * i
    return report


result = main()
print(result)
