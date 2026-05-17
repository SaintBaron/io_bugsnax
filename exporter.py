"""Blender mesh object → .objcache / .daecache binary.

Reads only current Blender state (geometry, normals, UVs, colour,
material image refs) and writes a fresh cache file. Non-static elements
(armatures, shape keys, animation actions) get baked or stripped via
the depsgraph; the writer just consumes a static mesh.
"""

import os
import bmesh

from . import parser as cache_parser


def _color_to_bytes(c):
    def _clamp(x):
        return max(0, min(255, int(round(x * 255.0))))
    return bytes((_clamp(c[0]), _clamp(c[1]), _clamp(c[2]), _clamp(c[3])))


def _gather_textures_from_material(mat):
    """Pick up to three image-texture paths from a material's Principled
    BSDF (Base Color, Normal, Specular IOR Level). Asset-relative
    "Content/..." paths are preserved verbatim; everything else falls
    back to the image's basename."""
    out = []
    if mat is None or not mat.use_nodes:
        return out

    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        return out

    def _path_from_input(input_names):
        for name in input_names:
            sock = bsdf.inputs.get(name)
            if sock is None or not sock.is_linked:
                continue
            node = sock.links[0].from_node
            # Hop through a Normal Map node when present.
            if node.type == 'NORMAL_MAP' and node.inputs['Color'].is_linked:
                node = node.inputs['Color'].links[0].from_node
            if node.type == 'TEX_IMAGE' and node.image is not None:
                img = node.image
                fp = (img.filepath or img.filepath_raw or '').replace('\\', '/')
                if 'Content/' in fp:
                    return fp[fp.index('Content/'):]
                return os.path.basename(fp) if fp else img.name
        return None

    diffuse = _path_from_input(('Base Color', 'BaseColor'))
    normal  = _path_from_input(('Normal',))
    spec    = _path_from_input(('Specular IOR Level', 'Specular'))

    # Stop at the first gap so we don't write e.g. a normal-map path
    # in slot 0 when there's no diffuse.
    for p in (diffuse, normal, spec):
        if p:
            out.append(p)
        else:
            break
    return out


def _triangulate_mesh_copy(obj, depsgraph):
    """Return a triangulated copy of the depsgraph-evaluated mesh."""
    me_src = obj.evaluated_get(depsgraph).to_mesh()
    me = me_src.copy() if hasattr(me_src, 'copy') else me_src
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.to_mesh(me)
    bm.free()
    me.calc_loop_triangles()
    return me


def _build_cache_mesh_from_object(obj, depsgraph, global_scale: float,
                                  force_type: str) -> cache_parser.CacheMesh:
    """Build a CacheMesh from the depsgraph-evaluated state of `obj`."""
    me = _triangulate_mesh_copy(obj, depsgraph)

    out = cache_parser.CacheMesh()
    out.cache_type = force_type or "obj"
    out.tint_rgba = b'\xff\xff\xff\xff'

    mat = obj.material_slots[0].material if obj.material_slots else None
    out.textures = _gather_textures_from_material(mat)

    n_verts = len(me.vertices)
    inv_scale = 1.0 / global_scale if global_scale != 0.0 else 1.0

    # Cache files are Y-up; Blender is Z-up. Inverse of the importer's
    # +90° X rotation: (x, y, z) → (x, z, -y).
    out.positions = [(v.co.x * inv_scale,
                      v.co.z * inv_scale,
                      -v.co.y * inv_scale) for v in me.vertices]

    # AABB in cache-space (post-rotation), matching what the engine sees.
    if out.positions:
        xs = [p[0] for p in out.positions]
        ys = [p[1] for p in out.positions]
        zs = [p[2] for p in out.positions]
        out.aabb_min = (min(xs), min(ys), min(zs))
        out.aabb_max = (max(xs), max(ys), max(zs))

    # Daecache extent: half the AABB diagonal (a usable culling sphere).
    if out.cache_type == "dae" and out.positions:
        dx = out.aabb_max[0] - out.aabb_min[0]
        dy = out.aabb_max[1] - out.aabb_min[1]
        dz = out.aabb_max[2] - out.aabb_min[2]
        out.dae_extent = (dx * dx + dy * dy + dz * dz) ** 0.5 * 0.5

    # Cache format wants one normal/UV/colour per vertex, but Blender
    # stores them per-loop. Take the first loop encountered per vertex,
    # matching what Bugsnax's own exporter does (verified against the
    # sample files).
    vert_normal = [(0.0, 1.0, 0.0)] * n_verts
    seen_n = [False] * n_verts
    try:
        me.calc_normals_split()
    except Exception:
        pass
    for poly in me.polygons:
        for loop_idx in poly.loop_indices:
            vi = me.loops[loop_idx].vertex_index
            if not seen_n[vi]:
                n = me.loops[loop_idx].normal
                # Same rotation as positions.
                vert_normal[vi] = (n.x, n.z, -n.y)
                seen_n[vi] = True
    out.normals = vert_normal

    # Primary UV (V-flipped to cache convention).
    uv_layer = me.uv_layers.active
    uv_arr = [(0.0, 0.0)] * n_verts
    if uv_layer is not None:
        seen = [False] * n_verts
        for poly in me.polygons:
            for loop_idx in poly.loop_indices:
                vi = me.loops[loop_idx].vertex_index
                if not seen[vi]:
                    uv = uv_layer.data[loop_idx].uv
                    uv_arr[vi] = (uv[0], 1.0 - uv[1])
                    seen[vi] = True
    out.uvs = uv_arr

    # Vertex colours.
    color_arr = [b'\xff\xff\xff\xff'] * n_verts
    if me.color_attributes:
        attr = me.color_attributes.active_color or me.color_attributes[0]
        try:
            if attr.domain == 'CORNER':
                seen = [False] * n_verts
                for poly in me.polygons:
                    for loop_idx in poly.loop_indices:
                        vi = me.loops[loop_idx].vertex_index
                        if not seen[vi]:
                            color_arr[vi] = _color_to_bytes(attr.data[loop_idx].color)
                            seen[vi] = True
            else:
                for vi in range(n_verts):
                    color_arr[vi] = _color_to_bytes(attr.data[vi].color)
        except Exception:
            pass
    out.colors = color_arr

    # Daecache extras from optional UV2 / UV3 layers.
    if out.cache_type == "dae":
        out.tangents = [(0.0, 0.0, 0.0)] * n_verts

        def _gather_uv(layer):
            arr = [(0.0, 0.0)] * n_verts
            if layer is None:
                return arr
            seen = [False] * n_verts
            for poly in me.polygons:
                for loop_idx in poly.loop_indices:
                    vi = me.loops[loop_idx].vertex_index
                    if not seen[vi]:
                        uv = layer.data[loop_idx].uv
                        arr[vi] = (uv[0], uv[1])
                        seen[vi] = True
            return arr

        out.uv2 = _gather_uv(me.uv_layers.get('UV2'))
        out.uv3 = _gather_uv(me.uv_layers.get('UV3'))

    out.faces = [tuple(p.vertices) for p in me.polygons if len(p.vertices) == 3]
    return out


def _conform_notes(obj, cache_type: str) -> list:
    """Return informational notes about source data that the cache
    format can't carry. Stripping happens implicitly: armatures /
    shape keys bake via the depsgraph; vertex groups / animations
    just aren't read by the writer."""
    notes = []
    fmt = "objcache" if cache_type == "obj" else "daecache"
    if any(m.type == 'ARMATURE' for m in obj.modifiers):
        notes.append(f"Armature modifier baked into the {fmt} (no skeleton stored).")
    if obj.vertex_groups and any(v.groups for v in obj.data.vertices):
        notes.append(f"Vertex groups dropped from the {fmt} (no skin-weight slot).")
    if obj.data.shape_keys and len(obj.data.shape_keys.key_blocks) > 1:
        notes.append(f"Shape keys baked into base mesh for the {fmt}.")
    if obj.animation_data and obj.animation_data.action:
        notes.append(f"Animation action dropped from the {fmt} (single-frame format).")
    return notes


def export_cache(context, filepath: str,
                 use_selection: bool = False,
                 global_scale: float = 1.0,
                 force_type: str = "",
                 **_):
    """Export one mesh as .objcache or .daecache."""
    if use_selection:
        candidates = [o for o in context.selected_objects if o.type == 'MESH']
    else:
        candidates = [o for o in context.scene.objects if o.type == 'MESH']

    if not candidates:
        return {'CANCELLED'}, ["No mesh object found to export."]

    # Prefer the active object; the cache format is single-mesh.
    obj = context.view_layer.objects.active
    if obj is None or obj.type != 'MESH' or obj not in candidates:
        obj = candidates[0]
    messages = []
    if len(candidates) > 1:
        messages.append(
            f"{len(candidates)} mesh objects found; only '{obj.name}' written."
        )

    if not force_type:
        ext = os.path.splitext(filepath)[1].lower()
        force_type = "dae" if ext == ".daecache" else "obj"
    if force_type not in ("obj", "dae"):
        force_type = "obj"

    messages.extend(_conform_notes(obj, force_type))

    depsgraph = context.evaluated_depsgraph_get()
    cache_mesh = _build_cache_mesh_from_object(obj, depsgraph,
                                               global_scale, force_type)
    cache_parser.write_cache_file(cache_mesh, filepath)
    return {'FINISHED'}, messages
