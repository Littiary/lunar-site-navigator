"""Creates the two material assets of the stage 1 scene from code.

The project uses no downloaded or marketplace assets. The materials are simple
enough to be written here, so the binary .uasset files under Content/Lsn are
reproducible: delete them and run this script again.

Run headless from the repository root:

    UnrealEditor-Cmd.exe unreal/LunarSiteNavigator.uproject -run=pythonscript -script=unreal/Scripts/make_materials.py

M_LsnSurface   lit, fully rough, no specular, two-sided (the terrain is an open
               sheet that must also block light arriving from behind it).
               Base colour = vertex colour x a regolith factor 2 / (mu0 + mu),
               limited to 4, where mu0 and mu are the cosines of the Sun's and the
               viewer's direction to the surface normal. With the engine's own
               cosine law this gives the Lommel-Seeliger law mu0 / (mu0 + mu), the
               usual first description of dark, dusty surfaces such as lunar
               regolith: no darkening towards grazing light as on a matt painted
               surface. Vector parameter "SunDirection" (world, from the package,
               set by the scene); scalar parameter "RegolithShading" (1 for the
               Moon, 0 for the plain cosine law, used for the Earth's disc).
               A display model, not a calibrated photometric function.
M_LsnEmissive  unlit, emissive = vertex colour x scalar parameter "Intensity".
               Used for the Sun disc and the horizon line overlay.
"""

import unreal

FOLDER = "/Game/Lsn"
mel = unreal.MaterialEditingLibrary


def _new_material(name):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    return material, path


def _constant(material, value, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionConstant, -400, y)
    node.set_editor_property("r", value)
    return node


def make_surface():
    material, path = _new_material("M_LsnSurface")
    material.set_editor_property("two_sided", True)
    def node(cls, x, y):
        return mel.create_material_expression(material, cls, x, y)

    def link(source, target, name):
        if not mel.connect_material_expressions(source, "", target, name):
            raise RuntimeError(f"could not connect to input '{name}' of {target.get_class().get_name()}")

    colour = node(unreal.MaterialExpressionVertexColor, -1400, 0)
    sun = node(unreal.MaterialExpressionVectorParameter, -1400, 200)
    sun.set_editor_property("parameter_name", "SunDirection")
    sun.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 1.0, 0.0))
    normal = node(unreal.MaterialExpressionVertexNormalWS, -1400, 400)
    view = node(unreal.MaterialExpressionCameraVectorWS, -1400, 500)
    dot_sun = node(unreal.MaterialExpressionDotProduct, -1150, 250)
    link(normal, dot_sun, "A")
    link(sun, dot_sun, "B")
    dot_view = node(unreal.MaterialExpressionDotProduct, -1150, 450)
    link(normal, dot_view, "A")
    link(view, dot_view, "B")
    # The sheet is two-sided: use the size of both cosines, whichever side is seen.
    mu0 = node(unreal.MaterialExpressionAbs, -950, 250)
    link(dot_sun, mu0, "")
    mu = node(unreal.MaterialExpressionAbs, -950, 450)
    link(dot_view, mu, "")
    total = node(unreal.MaterialExpressionAdd, -780, 350)
    link(mu0, total, "A")
    link(mu, total, "B")
    floor = node(unreal.MaterialExpressionMax, -620, 350)
    link(total, floor, "A")
    link(_constant(material, 0.5, 600), floor, "B")  # limits the factor to 4
    factor = node(unreal.MaterialExpressionDivide, -470, 350)
    link(_constant(material, 2.0, 700), factor, "A")
    link(floor, factor, "B")
    amount = node(unreal.MaterialExpressionScalarParameter, -470, 550)
    amount.set_editor_property("parameter_name", "RegolithShading")
    amount.set_editor_property("default_value", 1.0)
    blend = node(unreal.MaterialExpressionLinearInterpolate, -300, 400)
    link(_constant(material, 1.0, 800), blend, "A")
    link(factor, blend, "B")
    link(amount, blend, "Alpha")
    base = node(unreal.MaterialExpressionMultiply, -150, 100)
    link(colour, base, "A")
    link(blend, base, "B")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(_constant(material, 1.0, 200), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(_constant(material, 0.0, 300), "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(_constant(material, 0.0, 400), "", unreal.MaterialProperty.MP_METALLIC)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return path


def make_emissive():
    material, path = _new_material("M_LsnEmissive")
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)
    colour = mel.create_material_expression(material, unreal.MaterialExpressionVertexColor, -600, 0)
    intensity = mel.create_material_expression(material, unreal.MaterialExpressionScalarParameter, -600, 200)
    intensity.set_editor_property("parameter_name", "Intensity")
    intensity.set_editor_property("default_value", 1.0)
    product = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -300, 100)
    mel.connect_material_expressions(colour, "", product, "A")
    mel.connect_material_expressions(intensity, "", product, "B")
    mel.connect_material_property(product, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return path


for made in (make_surface(), make_emissive()):
    unreal.log(f"LSN material written: {made}")
