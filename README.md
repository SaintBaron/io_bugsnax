# io_bugsnax

A Blender addon for importing and exporting the cache formats used by
**Bugsnax** and the **Horsepower Engine** — the static mesh caches
(**`.objcache`** / **`.daecache`**) that ship alongside the engine's
skinned characters, and the skinned-character cache (**`.xcache`**)
itself.

All three share the `SEMS` binary magic. The static caches hold a
single static mesh with up to three texture references (diffuse,
normal, specular); the `.xcache` format additionally carries a
skeleton, skin weights, and animation.

| Format        | Kind            | Per-vertex / payload                                       |
|---------------|-----------------|------------------------------------------------------------|
| `.objcache`   | Static mesh     | position · normal · colour · UV                            |
| `.daecache`   | Static mesh     | position · normal · colour · UV · tangent · UV2 · UV3      |
| `.xcache`     | Skinned character | mesh + skeleton + skin weights + animation               |

> **The `.xcache` code is frozen.** Import/export for `.xcache` lives
> in three self-contained modules (`xcache_parser.py`,
> `xcache_importer.py`, `xcache_exporter.py`) ported verbatim from the
> `io_directx_x` addon at its xcache-validated state. They are kept
> isolated here so that ongoing work on the separate DirectX `.x`
> addon can never regress the hard-won, reverse-engineered SEMS logic.
> Don't edit these modules to accommodate `.x` changes.

---

## Installation

1. Go to **Edit → Preferences → Add-ons → Install…**
2. Select the `io_bugsnax` folder (zip it first if Blender asks for a zip).
3. Tick **"Bugsnax Cache (.objcache, .daecache, .xcache)"** in the add-on list.

You'll get six new menu entries:

- File → Import → **Bugsnax Cache (.objcache)**
- File → Import → **Bugsnax Cache (.daecache)**
- File → Import → **Bugsnax Cache (.xcache)**
- File → Export → **Bugsnax Cache (.objcache)**
- File → Export → **Bugsnax Cache (.daecache)**
- File → Export → **Bugsnax Cache (.xcache)**

---

## Static caches (`.objcache` / `.daecache`)

### Importing

| Option | Default | What it does |
|---|---|---|
| Scale | 1.0 | Uniform scale on the imported mesh |
| Import Textures | On | Loads referenced image files. If a texture isn't found on disk, a 1×1 placeholder is created so the path still round-trips when you export |

The importer creates one mesh object with a Principled-BSDF material.
Texture slots are wired up automatically: diffuse to **Base Color**,
normal to **Normal** (via a Normal Map node), specular to **Specular
IOR Level**. Cache files are Y-up; the importer rotates them to
Blender's Z-up convention so they sit upright in the viewport.

#### Where the importer looks for textures

Cache files store asset-relative paths like
`Content/Models/Environment/Forest/Plants/PalmTree_D.dds`. The
importer searches:

- The cache file's directory
- Common subfolders: `Textures/`, `tex/`, `textures/`, `Content/`
- Up to three parent directories
- These extensions: `.png .jpg .jpeg .tga .dds .bmp .tif .tiff .webp`

### Exporting

| Option | Default | What it does |
|---|---|---|
| Selected Only | Off | Export only the selected mesh; otherwise the first mesh in the scene |
| Scale | 1.0 | Uniform scale on the exported mesh |

Texture paths are read from the active material's Principled-BSDF
inputs (the inverse of what the importer does). Asset-relative
`Content/...` paths are preserved verbatim; anything else falls back
to the file's basename.

#### Static-mesh conformity

Both static cache formats are **single static mesh** binaries. The
exporter silently strips anything else, sampled at the current frame:

- **Armature modifiers** are baked into the vertex positions via the
  depsgraph (current pose is what gets written)
- **Vertex groups / skin weights** are dropped (no skin slot in the format)
- **Shape keys** are evaluated at their current values before write
- **Animation actions** are ignored (single-frame format)

When any of these is present, the export report (Blender's status bar)
notes what was stripped. `.objcache` mirrors the OBJ format's
limitations; `.daecache` is the DAE *binary cache* — DAE the source
format supports skeletons, but the compiled cache does not.

If you need to keep the skeleton, animation, and skin weights, use
`.xcache` instead.

---

## Skinned cache (`.xcache`)

The `.xcache` importer builds a full rig: a mesh (optionally split into
its internal sub-meshes), an armature, vertex-group skin weights, and
an animation action. You can select and import several `.xcache` files
at once.

### Importing

| Group | Option | Default | What it does |
|---|---|---|---|
| Transform | Scale | 1.0 | Uniform scale on the imported geometry |
| Transform | Forward Axis | -Z | Forward axis used for the Y-up → Z-up conversion |
| Transform | Up Axis | Y | Up axis used for the conversion |
| Geometry | Import Normals | On | Apply the file's per-vertex normals |
| Geometry | Import UVs | On | Apply the file's UV coordinates |
| Geometry | Split Sub-Meshes | On | Split the xcache's internal multi-mesh structure into separate Blender objects |
| Geometry | Weld Duplicate Vertices | On | Weld coincident verts so bone-deformation boundaries don't separate when animated |
| Geometry | Infer Sharp Edges | On | Derive sharp edges from the imported normals |
| Materials | Import Materials | On | Build Principled-BSDF materials |
| Materials | Import Textures | On | Load referenced image files |
| Materials | Use Diffuse Alpha | On | Connect the diffuse texture's alpha channel to material alpha |
| Rig | Import Armature | On | Build the skeleton |
| Rig | Import Weights | On | Apply skin weights as vertex groups |
| Rig | Import Animation | On | Build an animation action from the file's keyframes |
| Rig | Rest Pose Source | Bind Pose | Where bone rest poses come from (see below) |
| Rig | Animation FPS | 0.0 | Playback rate; `0` lets the importer infer it from the file |
| Rig | Set Scene Frame Range | On | Set the scene's start/end frames to match the animation |

**Rest Pose Source** — *Bind Pose* (the default) reads the
`SkinWeights` `matrixOffset` inverse-bind matrices, which is the
correct interpretation for Bugsnax `.xcache` files. *Frame Hierarchy*
instead walks the `FrameTransformMatrix` chain; use it only if a file
imports with a broken rest pose under the default.

**Texture search** — the xcache importer extends the static-cache
search with a cross-`Content/` lookup: it walks up to find a `Content`
ancestor directory and does a shallow scan of the subtrees beneath it,
so a character in `Content/Characters/Banana/` can still resolve a
texture that actually lives under `Content/Models/Bugs/Banana/`.

### Exporting

| Group | Option | Default | What it does |
|---|---|---|---|
| Include | Selected Only | Off | Export only the selected objects |
| Include | Apply Modifiers | On | Bake modifiers before writing |
| Include | Export Armature | On | Write the skeleton |
| Include | Export Weights | On | Write skin weights |
| Include | Export Animation | On | Write the animation |
| Animation Range | Frame Start | 1 | First frame to sample |
| Animation Range | Frame End | 250 | Last frame to sample |
| Transform | Scale | 1.0 | Uniform scale on the exported geometry |
| Transform | Forward Axis | -Z | Forward axis for the Z-up → Y-up conversion |
| Transform | Up Axis | Y | Up axis for the conversion |

---

## Round-trip behaviour

For the **static caches**, import → export produces a structurally
identical file. Vertex counts, face counts, texture references, AABB,
and the daecache extent all round-trip exactly. Byte-level equality
isn't guaranteed (small metadata bytes are regenerated rather than
carried verbatim) but the engine reads the result identically.

The daecache extras (UV2, UV3) are exposed in Blender as additional UV
layers — keep those layer names intact if you want them preserved on
export.

For **`.xcache`**, the importer/exporter were validated against a large
dev corpus of Bugsnax character files; the mesh, skeleton, skin
weights, and animation round-trip through Blender's armature/pose
system.

---

## File layout

```
io_bugsnax/
├── __init__.py           Blender operators and menu registration (all 3 formats)
├── parser.py             .objcache / .daecache binary read/write (CacheMesh)
├── importer.py           CacheMesh → Blender object
├── exporter.py           Blender object → CacheMesh → file
├── xcache_parser.py      .xcache binary read/write   (frozen)
├── xcache_importer.py    .xcache → Blender rig        (frozen)
└── xcache_exporter.py    Blender rig → .xcache file   (frozen)
```
