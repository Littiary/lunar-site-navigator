"""Creates the material assets of the scene from code.

The project uses no downloaded or marketplace assets and no textures. The materials are
simple enough to be written here, so the binary .uasset files under Content/Lsn are
reproducible: delete them and run this script again.

Run headless from the repository root:

    UnrealEditor-Cmd.exe unreal/LunarSiteNavigator.uproject -run=pythonscript -script=unreal/Scripts/make_materials.py

M_LsnSurface   lit, fully rough, no specular, two-sided (the terrain is an open sheet that
               must also block light arriving from behind it).
               Base colour = vertex colour x a regolith factor 2 / (mu0 + mu), limited to
               4, where mu0 and mu are the cosines of the Sun's and the viewer's direction
               to the surface normal. With the engine's own cosine law this gives the
               Lommel-Seeliger law mu0 / (mu0 + mu), the usual first description of dark,
               dusty surfaces such as lunar regolith. A display model, not a calibrated
               photometric function.
               Detail below the resolution of the elevation data: the shading normal is
               tilted by a procedural height field (two scales of roughness and two sizes
               of small craters, computed in the shader from the position on the ground),
               and the grey value varies by a few per cent. Positions are not changed, so
               the outline of the terrain, its shadows and the horizon stay those of the
               data. The detail is illustrative: it is not measured and stands for the
               kind of surface the data cannot resolve. It fades out with distance.
               Parameters: vector "SunDirection" (world, from the package, set by the
               scene); scalar "RegolithShading" (1 for the Moon, 0 for the plain cosine
               law); scalar "DetailStrength" (1 for the ground, 0 for everything else);
               scalar "Ambient" (emissive share of the grey value: for the scale objects
               only, a stand-in for sunlight reflected from the ground onto their shaded
               sides; 0 for the ground).
M_LsnEmissive  unlit, emissive = vertex colour x scalar parameter "Intensity".
               Used for the Sun disc and the highlight overlays.
M_LsnStar      unlit; one small square per star with UV 0..1: emissive = vertex colour x
               vertex alpha (the display brightness of the star) x "Intensity", falling
               off from the centre of the square to nothing at its edge.
"""

import unreal

FOLDER = "/Game/Lsn"
mel = unreal.MaterialEditingLibrary

# Height field of the detail, in metres on the horizontal plane; the shader returns the tilted
# normal (xyz) and a factor on the grey value (w). All lengths are choices for the look.
DETAIL_CODE = r"""
struct FLsnDetail
{
    float Hash(float2 q) { return frac(sin(dot(q, float2(127.1, 311.7))) * 43758.5453); }
    float2 Hash2(float2 q) { return frac(sin(float2(dot(q, float2(127.1, 311.7)), dot(q, float2(269.5, 183.3)))) * 43758.5453); }
    // Value noise with its gradient: xy = d/dx, d/dy; z = value 0..1.
    float3 Noise(float2 p)
    {
        float2 i = floor(p), f = frac(p);
        float2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
        float2 du = 30.0 * f * f * (f * (f - 2.0) + 1.0);
        float a = Hash(i), b = Hash(i + float2(1, 0)), c = Hash(i + float2(0, 1)), d = Hash(i + float2(1, 1));
        float k1 = b - a, k2 = c - a, k4 = a - b - c + d;
        return float3(du.x * (k1 + k4 * u.y), du.y * (k2 + k4 * u.x), a + k1 * u.x + k2 * u.y + k4 * u.x * u.y);
    }
    // Slope (dh/dx, dh/dy) of a field of bowl-shaped craters with raised rims; Cell = size of a grid cell in metres.
    float2 Craters(float2 p, float Cell)
    {
        float2 g = p / Cell, base = floor(g), slope = 0;
        for (int y = -1; y <= 1; y++)
        {
            for (int x = -1; x <= 1; x++)
            {
                float2 cell = base + float2(x, y);
                float2 r = Hash2(cell);
                if (Hash(cell + 17.0) > 0.36) { continue; }           // about one cell in three has a crater
                float2 centre = cell + 0.25 + 0.5 * r;
                float radius = 0.10 + 0.20 * Hash(cell + 5.0);        // in cells
                float2 d = g - centre;
                float rho = length(d) / radius;
                if (rho >= 1.6 || rho < 1e-4) { continue; }
                float depth = 0.085 * radius;                          // shallow, worn craters
                // Inside: a bowl (height falls towards the centre). Outside: the rim falls away. Blended, so the rim is rounded.
                float edge = smoothstep(0.70, 1.05, rho);
                float dh = lerp(2.0 * depth * rho, -1.2 * depth * (1.6 - rho) / 0.6, edge);
                slope += (d / max(length(d), 1e-5)) * (dh / radius);
            }
        }
        return slope;
    }
};
FLsnDetail L;
float2 p = P.xy * 0.01;                 // centimetres to metres
float metres = D * 0.01;
float fine = saturate(1.0 - metres / 45.0), medium = saturate(1.0 - metres / 260.0);
float small = saturate(1.0 - metres / 320.0), large = saturate(1.0 - metres / 1100.0);
float2 slope = 0;
slope += 0.050 * fine * L.Noise(p * 4.1).xy;
slope += 0.060 * fine * L.Noise(p * 1.3 + 7.7).xy;
slope += 0.070 * medium * L.Noise(p * 0.37 + 3.1).xy;
slope += small * L.Craters(p + 11.3, 3.7);
slope += large * L.Craters(p + 41.9, 14.0);
float3 n = normalize(N + S * float3(-slope.x, -slope.y, 0.0));
float mottle = 1.0 + S * 0.10 * medium * (L.Noise(p * 0.11 + 19.0).z - 0.5);
return float4(n, mottle);
"""

STAR_CODE = r"""
float r = saturate(1.0 - 2.0 * length(UV - 0.5));
return C * (A * I * r * r);
"""


def _new_material(name):
    path = f"{FOLDER}/{name}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = tools.create_asset(name, FOLDER, unreal.Material, unreal.MaterialFactoryNew())
    if material is None:
        raise RuntimeError(f"could not create {path}")
    return material, path


def _link(source, output, target, name):
    if not mel.connect_material_expressions(source, output, target, name):
        raise RuntimeError(f"could not connect '{output}' to input '{name}' of {target.get_class().get_name()}")


def _custom(material, code, output_type, names, x, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionCustom, x, y)
    node.set_editor_property("code", code.strip())
    node.set_editor_property("output_type", output_type)
    inputs = []
    for name in names:
        item = unreal.CustomInput()
        item.set_editor_property("input_name", name)
        inputs.append(item)
    node.set_editor_property("inputs", inputs)
    return node


def _scalar(material, name, default, x, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", default)
    return node


def _constant(material, value, y):
    node = mel.create_material_expression(material, unreal.MaterialExpressionConstant, -400, y)
    node.set_editor_property("r", value)
    return node


def make_surface():
    material, path = _new_material("M_LsnSurface")
    material.set_editor_property("two_sided", True)
    # The detail node gives a world-space normal.
    material.set_editor_property("tangent_space_normal", False)

    def node(cls, x, y):
        return mel.create_material_expression(material, cls, x, y)

    def link(source, target, name, output=""):
        _link(source, output, target, name)

    colour = node(unreal.MaterialExpressionVertexColor, -1900, 0)
    sun = node(unreal.MaterialExpressionVectorParameter, -1400, 200)
    sun.set_editor_property("parameter_name", "SunDirection")
    sun.set_editor_property("default_value", unreal.LinearColor(0.0, 0.0, 1.0, 0.0))
    vertex_normal = node(unreal.MaterialExpressionVertexNormalWS, -2300, 400)
    position = node(unreal.MaterialExpressionWorldPosition, -2300, 500)
    camera = node(unreal.MaterialExpressionCameraPositionWS, -2300, 600)
    distance = node(unreal.MaterialExpressionDistance, -2100, 560)
    link(position, distance, "A")
    link(camera, distance, "B")
    strength = _scalar(material, "DetailStrength", 0.0, -2300, 700)
    detail = _custom(material, DETAIL_CODE, unreal.CustomMaterialOutputType.CMOT_FLOAT4, ["P", "N", "D", "S"], -1900, 450)
    link(position, detail, "P")
    link(vertex_normal, detail, "N")
    link(distance, detail, "D")
    link(strength, detail, "S")
    normal = node(unreal.MaterialExpressionComponentMask, -1650, 420)
    normal.set_editor_property("r", True)
    normal.set_editor_property("g", True)
    normal.set_editor_property("b", True)
    normal.set_editor_property("a", False)
    link(detail, normal, "")
    mottle = node(unreal.MaterialExpressionComponentMask, -1650, 560)
    mottle.set_editor_property("r", False)
    mottle.set_editor_property("g", False)
    mottle.set_editor_property("b", False)
    mottle.set_editor_property("a", True)
    link(detail, mottle, "")

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
    amount = _scalar(material, "RegolithShading", 1.0, -470, 550)
    blend = node(unreal.MaterialExpressionLinearInterpolate, -300, 400)
    link(_constant(material, 1.0, 800), blend, "A")
    link(factor, blend, "B")
    link(amount, blend, "Alpha")
    grey = node(unreal.MaterialExpressionMultiply, -1400, 0)
    link(colour, grey, "A")
    link(mottle, grey, "B")
    base = node(unreal.MaterialExpressionMultiply, -150, 100)
    link(grey, base, "A")
    link(blend, base, "B")
    ambient = _scalar(material, "Ambient", 0.0, -470, 900)
    glow = node(unreal.MaterialExpressionMultiply, -150, 850)
    link(colour, glow, "A")
    link(ambient, glow, "B")
    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(normal, "", unreal.MaterialProperty.MP_NORMAL)
    mel.connect_material_property(glow, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
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
    intensity = _scalar(material, "Intensity", 1.0, -600, 200)
    product = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -300, 100)
    _link(colour, "", product, "A")
    _link(intensity, "", product, "B")
    mel.connect_material_property(product, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return path


def make_star():
    material, path = _new_material("M_LsnStar")
    material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    material.set_editor_property("two_sided", True)
    colour = mel.create_material_expression(material, unreal.MaterialExpressionVertexColor, -800, 0)
    uv = mel.create_material_expression(material, unreal.MaterialExpressionTextureCoordinate, -800, 250)
    intensity = _scalar(material, "Intensity", 1.0, -800, 400)
    star = _custom(material, STAR_CODE, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["UV", "C", "A", "I"], -400, 150)
    _link(uv, "", star, "UV")
    _link(colour, "", star, "C")
    _link(colour, "A", star, "A")
    _link(intensity, "", star, "I")
    mel.connect_material_property(star, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    return path


for made in (make_surface(), make_emissive(), make_star()):
    unreal.log(f"LSN material written: {made}")
