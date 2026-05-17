"""CacheMesh → Blender mesh object, with materials and textures."""

import os
import bpy

from . import parser as cache_parser


# Search paths for textures referenced by the cache. Bugsnax stores
# asset-relative paths like "Content/Models/.../foo_D.dds" but the
# user's local file layout might differ.
_TEXTURE_SUBDIRS = ("", "Textures", "tex", "textures", "Content")
_TEXTURE_EXTS = (".png", ".jpg", ".jpeg", ".tga", ".dds",
                 ".bmp", ".tif", ".tiff", ".webp")


def _try_load_image(base_dir: str, asset_path: str):
    """Locate a texture on disk near `base_dir`, falling back to a 1x1
    placeholder image whose `filepath` keeps the original reference so
    it round-trips on export."""
    asset_path = asset_path.replace('\\', '/')
    asset_name = os.path.basename(asset_path)

    # Try the full path, then progressively shorter tails of it.
    tails = [asset_path]
    parts = asset_path.split('/')
    while len(parts) > 1:
        parts = parts[1:]
        tails.append('/'.join(parts))

    candidates = []
    for tail in tails:
        stem, _ = os.path.splitext(tail)
        for sub in _TEXTURE_SUBDIRS:
            for ext in _TEXTURE_EXTS:
                candidates.append(os.path.join(base_dir, sub, stem + ext))
                # Also try up to three parent directories.
                parent = base_dir
                for _ in range(3):
                    parent = os.path.dirname(parent)
                    if not parent:
                        break
                    candidates.append(os.path.join(parent, sub, stem + ext))

    for c in candidates:
        if os.path.isfile(c):
            try:
                return bpy.data.images.load(c, check_existing=True)
            except Exception:
                continue

    placeholder = bpy.data.images.new(asset_name, width=1, height=1, alpha=True)
    placeholder.filepath = os.path.join(base_dir, asset_path)
    placeholder.source = 'FILE'
    return placeholder


def _build_material(mesh_name: str, textures: list, base_dir: str,
                    tint_rgba: bytes, load_textures: bool):
    """Build a Principled-BSDF material with up to three texture slots
    (diffuse, normal, specular). Missing slots are skipped."""
    mat = bpy.data.materials.new(name=mesh_name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes.get('Principled BSDF')
    if bsdf is None:
        return mat

    if tint_rgba and len(tint_rgba) >= 3:
        bsdf.inputs['Base Color'].default_value = (
            tint_rgba[0] / 255.0,
            tint_rgba[1] / 255.0,
            tint_rgba[2] / 255.0,
            1.0,
        )

    if not load_textures:
        return mat

    def _add_image_node(asset_path, x, y):
        if not asset_path:
            return None
        img = _try_load_image(base_dir, asset_path)
        if img is None:
            return None
        node = nodes.new('ShaderNodeTexImage')
        node.image = img
        node.location = (x, y)
        return node

    if len(textures) >= 1:
        diff = _add_image_node(textures[0], -400, 300)
        if diff is not None:
            links.new(diff.outputs['Color'], bsdf.inputs['Base Color'])

    if len(textures) >= 2:
        norm = _add_image_node(textures[1], -400, 0)
        if norm is not None:
            try:
                norm.image.colorspace_settings.name = 'Non-Color'
            except Exception:
                pass
            nmap = nodes.new('ShaderNodeNormalMap')
            nmap.location = (-180, 0)
            links.new(norm.outputs['Color'], nmap.inputs['Color'])
            links.new(nmap.outputs['Normal'], bsdf.inputs['Normal'])

    if len(textures) >= 3:
        spec = _add_image_node(textures[2], -400, -300)
        if spec is not None:
            try:
                spec.image.colorspace_settings.name = 'Non-Color'
            except Exception:
                pass
            # Blender 4.x renamed "Specular" to "Specular IOR Level".
            for input_name in ('Specular IOR Level', 'Specular'):
                if input_name in bsdf.inputs:
                    links.new(spec.outputs['Color'], bsdf.inputs[input_name])
                    break

    return mat


def _build_mesh_object(mesh_data: cache_parser.CacheMesh,
                       obj_name: str,
                       global_scale: float):
    """Build a Blender Object + Mesh from `mesh_data`."""
    me = bpy.data.meshes.new(obj_name)

    # Cache files are Y-up (DirectX / 3DS Max); rotate +90° about X
    # into Blender's Z-up: (x, y, z) → (x, -z, y). Baked into vertex
    # coordinates so the object's world matrix stays identity.
    s = global_scale
    verts = [(p[0] * s, -p[2] * s, p[1] * s) for p in mesh_data.positions]
    faces = [tuple(f) for f in mesh_data.faces]
    me.from_pydata(verts, [], faces)
    me.update()

    # Per-vertex split normals, rotated to match the position transform.
    if mesh_data.normals and hasattr(me, 'normals_split_custom_set'):
        for poly in me.polygons:
            poly.use_smooth = True
        rotated = [(n[0], -n[2], n[1]) for n in mesh_data.normals]
        loop_normals = []
        for poly in me.polygons:
            for loop_idx in poly.loop_indices:
                vi = me.loops[loop_idx].vertex_index
                loop_normals.append(rotated[vi] if vi < len(rotated)
                                    else (0.0, 0.0, 1.0))
        try:
            if hasattr(me, 'use_auto_smooth'):
                me.use_auto_smooth = True
            me.normals_split_custom_set(loop_normals)
        except Exception:
            pass

    # Primary UV (V-flip to match Blender's convention).
    if mesh_data.uvs:
        uv = me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for loop_idx in poly.loop_indices:
                vi = me.loops[loop_idx].vertex_index
                if vi < len(mesh_data.uvs):
                    u, v = mesh_data.uvs[vi]
                    uv.data[loop_idx].uv = (u, 1.0 - v)

    # Daecache extras as extra UV layers (preserved verbatim for export).
    for layer_name, src in (('UV2', mesh_data.uv2), ('UV3', mesh_data.uv3)):
        if not src:
            continue
        layer = me.uv_layers.new(name=layer_name)
        for poly in me.polygons:
            for loop_idx in poly.loop_indices:
                vi = me.loops[loop_idx].vertex_index
                if vi < len(src):
                    layer.data[loop_idx].uv = src[vi]

    # Per-vertex colour as a corner BYTE_COLOR attribute.
    if mesh_data.colors:
        try:
            attr = me.color_attributes.new(name='Col',
                                           type='BYTE_COLOR',
                                           domain='CORNER')
            for poly in me.polygons:
                for loop_idx in poly.loop_indices:
                    vi = me.loops[loop_idx].vertex_index
                    if vi < len(mesh_data.colors):
                        c = mesh_data.colors[vi]
                        if len(c) >= 4:
                            attr.data[loop_idx].color = (
                                c[0] / 255.0, c[1] / 255.0,
                                c[2] / 255.0, c[3] / 255.0,
                            )
        except Exception:
            pass

    return bpy.data.objects.new(obj_name, me)


def import_cache(context, filepath: str,
                 global_scale: float = 1.0,
                 import_textures: bool = True,
                 **_):
    """Import .objcache or .daecache as a static mesh object."""
    mesh_data = cache_parser.parse_cache_file(filepath)
    base_dir = os.path.dirname(filepath)
    name_hint = os.path.splitext(os.path.basename(filepath))[0]

    obj = _build_mesh_object(mesh_data, name_hint, global_scale)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)

    has_tint = (mesh_data.tint_rgba and mesh_data.tint_rgba[:3]
                not in (b'\xff\xff\xff', b'\x00\x00\x00'))
    if mesh_data.textures or has_tint:
        mat = _build_material(name_hint, mesh_data.textures, base_dir,
                              mesh_data.tint_rgba, import_textures)
        obj.data.materials.append(mat)

    return {'FINISHED'}, []
