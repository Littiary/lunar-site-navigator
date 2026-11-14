"""Creates the two materials of the scene from code, so that no third-party asset is needed.

Run on the machine that builds the project (binary assets are written only there):

  UnrealEditor-Cmd.exe <project>.uproject -run=pythonscript -script=<this file>

M_LsnSurface  lit, uniform grey, fully rough, no specular. The grey value is a drawing
              choice, not a measured albedo.
M_LsnEmissive unlit, emissive colour parameter "Color" (Sun and Earth discs).
"""

import unreal

FOLDER = "/Game/Lsn"
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()


def new_material(name):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    return tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())


def constant(material, value, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionConstant, -300, y)
    node.set_editor_property("r", value)
    return node


def color_parameter(material, default):
    node = mel.create_material_expression(material, unreal.MaterialExpressionVectorParameter, -300, 0)
    node.set_editor_property("parameter_name", "Color")
    node.set_editor_property("default_value", default)
    return node


surface = new_material("M_LsnSurface")
mel.connect_material_property(color_parameter(surface, unreal.LinearColor(0.12, 0.12, 0.12, 1.0)), "", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(constant(surface, 1.0, 250), "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.connect_material_property(constant(surface, 0.0, 350), "", unreal.MaterialProperty.MP_SPECULAR)
mel.recompile_material(surface)

emissive = new_material("M_LsnEmissive")
emissive.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
mel.connect_material_property(color_parameter(emissive, unreal.LinearColor(1.0, 1.0, 1.0, 1.0)), "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(emissive)

for material in (surface, emissive):
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    unreal.log(f"Lsn: saved {material.get_path_name()}")
