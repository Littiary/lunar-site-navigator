"""Creates the two material assets of the stage 1 scene from code.

The project uses no downloaded or marketplace assets. The materials are simple
enough to be written here, so the binary .uasset files under Content/Lsn are
reproducible: delete them and run this script again.

Run headless from the repository root:

    UnrealEditor-Cmd.exe unreal/LunarSiteNavigator.uproject -run=pythonscript -script=unreal/Scripts/make_materials.py

M_LsnSurface   lit, base colour = vertex colour, fully rough, no specular,
               two-sided (the terrain is an open sheet that must also block
               light arriving from behind it).
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
    colour = mel.create_material_expression(material, unreal.MaterialExpressionVertexColor, -400, 0)
    mel.connect_material_property(colour, "", unreal.MaterialProperty.MP_BASE_COLOR)
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
