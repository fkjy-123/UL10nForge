from pathlib import Path

import UnityPy


def test_tmp_sdf_material_matches_atlas_sampling_contract():
    bundle = Path(__file__).parents[1] / "fonts" / "TMP_Font_AssetBundles" / "notoserif_sdf_u2019"
    env = UnityPy.load(str(bundle))
    textures = []
    materials = []
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            tree = obj.read_typetree()
            textures.append((tree["m_Width"], tree["m_Height"]))
        elif obj.type.name == "Material":
            tree = obj.read_typetree()
            floats = dict(tree["m_SavedProperties"]["m_Floats"])
            materials.append(floats)
    assert textures == [(4096, 4096)]
    assert len(materials) == 1
    assert materials[0]["_TextureWidth"] == 4096.0
    assert materials[0]["_TextureHeight"] == 4096.0
    assert materials[0]["_GradientScale"] == 10.0
