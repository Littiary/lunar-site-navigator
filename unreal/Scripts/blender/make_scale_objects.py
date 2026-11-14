"""Builds the scale objects of the planner view in Blender and writes them as OBJ files.

Own design, made from primitives by this script: a generic four-legged lander, the parts
of a deployable mast (base, a pole of 1 m that the scene stretches to the observer height
of the package, and a head) and three boulders. No real vehicle is copied; there are no
logos or markings. The objects only give a sense of scale: they are not part of any
package and take no part in the horizon comparison.

Run inside Blender (5.x):

    blender --background --python make_scale_objects.py

Output: unreal/Content/LsnModels/*.obj, metres, Z up, the origin on the ground under the
object. Each face group carries one of the material names of PALETTE; the scene gives each
a grey value of its own.
"""

import math
import os
import random

import bpy
from mathutils import Vector

OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "Content", "LsnModels"))
PALETTE = ("foil", "metal", "dark", "panel", "rock")


def material(name):
    return bpy.data.materials.get("lsn_" + name) or bpy.data.materials.new("lsn_" + name)


def finish(obj, mat, smooth=False):
    obj.data.materials.append(material(mat))
    for polygon in obj.data.polygons:
        polygon.use_smooth = smooth
    return obj


def cylinder(radius, depth, location, mat, vertices=16, rotation=(0.0, 0.0, 0.0), radius_top=None):
    if radius_top is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location, rotation=rotation)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius, radius2=radius_top, depth=depth, location=location, rotation=rotation)
    return finish(bpy.context.object, mat)


def box(size, location, mat, rotation=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location, rotation=rotation)
    bpy.context.object.scale = size
    return finish(bpy.context.object, mat)


def sphere(radius, location, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=10, radius=radius, location=location)
    return finish(bpy.context.object, mat, smooth=True)


def strut(a, b, radius, mat):
    a, b = Vector(a), Vector(b)
    axis = b - a
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=radius, depth=axis.length, location=(a + b) / 2)
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
        os.remove(mtl)  # the scene has its own grey values
    return path


def make_lander():
    """A generic lander: eight-sided body in foil, four legs, engine bell, two upright solar panels, a dish."""
    parts = [
        cylinder(1.45, 0.95, (0, 0, 1.55), "foil", vertices=8, rotation=(0, 0, math.radians(22.5))),
        cylinder(1.05, 0.45, (0, 0, 2.25), "metal", vertices=8, rotation=(0, 0, math.radians(22.5))),
        cylinder(0.55, 0.60, (0, 0, 0.78), "dark", vertices=20, radius_top=0.22),      # engine bell, opening down
        cylinder(0.30, 0.25, (0, 0, 1.12), "metal", vertices=12),
    ]
    for k in range(4):
        angle = math.radians(45 + 90 * k)
        c, s = math.cos(angle), math.sin(angle)
        foot = (2.35 * c, 2.35 * s, 0.10)
        parts.append(strut((1.30 * c, 1.30 * s, 1.75), foot, 0.055, "metal"))
        for side in (-1, 1):
            a2 = angle + side * math.radians(28)
            parts.append(strut((1.32 * math.cos(a2), 1.32 * math.sin(a2), 1.15), (2.05 * c, 2.05 * s, 0.45), 0.035, "metal"))
        parts.append(cylinder(0.36, 0.07, (foot[0], foot[1], 0.035), "metal", vertices=16))
        # Propellant tanks between the legs.
        a3 = angle + math.radians(45)
        parts.append(sphere(0.42, (1.05 * math.cos(a3), 1.05 * math.sin(a3), 1.55), "metal"))
    # Upright solar panels: near the pole the Sun is always low.
    for side in (-1, 1):
        parts.append(strut((0, side * 1.0, 2.45), (0, side * 1.0, 2.75), 0.03, "metal"))
        parts.append(box((1.5, 0.04, 1.1), (0, side * 1.0, 3.30), "panel"))
    # Dish on a short boom.
    parts.append(strut((0.55, 0, 2.45), (0.55, 0, 3.05), 0.03, "metal"))
    parts.append(cylinder(0.38, 0.14, (0.55, 0, 3.12), "metal", vertices=20, radius_top=0.05, rotation=(0, math.radians(180), 0)))
    return join("lander", parts)


def make_mast():
    base_parts = [cylinder(0.09, 0.50, (0, 0, 0.45), "metal", vertices=12)]
    for k in range(3):
        angle = math.radians(90 + 120 * k)
        base_parts.append(strut((0.07 * math.cos(angle), 0.07 * math.sin(angle), 0.55), (0.75 * math.cos(angle), 0.75 * math.sin(angle), 0.03), 0.025, "metal"))
        base_parts.append(cylinder(0.08, 0.03, (0.75 * math.cos(angle), 0.75 * math.sin(angle), 0.015), "metal", vertices=10))
    base = join("mast_base", base_parts)
    pole = join("mast_pole", [cylinder(0.035, 1.0, (0, 0, 0.5), "metal", vertices=10)])   # 1 m; stretched by the scene
    head = join("mast_head", [
        box((0.22, 0.16, 0.16), (0, 0, 0.0), "dark"),                 # sensor head at the observer height
        cylinder(0.05, 0.10, (0.14, 0, 0.0), "panel", vertices=12, rotation=(0, math.radians(90), 0)),
        box((0.03, 0.55, 0.38), (-0.06, 0, -0.42), "panel"),          # small upright solar panel below the head
        strut((0, 0, 0.08), (0, 0, 0.45), 0.008, "metal"),            # antenna
    ])
    return [base, pole, head]


def make_boulder(index, radius, seed):
    rng = random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=radius, location=(0, 0, 0))
    obj = bpy.context.object
    lumps = [(Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized(), rng.uniform(-0.28, 0.22)) for _ in range(9)]
    squash = Vector((rng.uniform(0.85, 1.25), rng.uniform(0.75, 1.1), rng.uniform(0.55, 0.8)))
    for vertex in obj.data.vertices:
        direction = vertex.co.normalized()
        bump = sum(amount * max(direction.dot(axis), 0.0) ** 3 for axis, amount in lumps)
        vertex.co = Vector((direction.x * squash.x, direction.y * squash.y, direction.z * squash.z)) * radius * (1.0 + bump)
    lowest = min(v.co.z for v in obj.data.vertices)
    for vertex in obj.data.vertices:
        vertex.co.z -= lowest + 0.12 * radius    # sits a little into the ground
    finish(obj, "rock", smooth=False)
    obj.name = f"boulder_{index}"
    return obj


def main():
    os.makedirs(OUT, exist_ok=True)
    scene = bpy.data.scenes.get("LsnScaleObjects") or bpy.data.scenes.new("LsnScaleObjects")
    if bpy.context.window:
        bpy.context.window.scene = scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    objects = [make_lander()] + make_mast() + [make_boulder(1, 0.55, 11), make_boulder(2, 0.32, 23), make_boulder(3, 0.85, 37)]
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
