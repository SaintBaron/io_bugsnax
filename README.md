# io_cache

A Blender addon for importing and exporting Bugsnax / Horsepower Engine
**`.objcache`** and **`.daecache`** files — the binary mesh-cache format
the game ships alongside its `.xcache` skinned characters.

Both formats hold a single static mesh with up to three texture
references (diffuse, normal, specular). The two variants differ only in
per-vertex data:

| Format        | Per-vertex channels                                  |
|---------------|------------------------------------------------------|
| `.objcache`   | position · normal · colour · UV                      |
| `.daecache`   | position · normal · colour · UV · tangent · UV2 · UV3 |

---

## Installation

1. Go to **Edit → Preferences → Add-ons → Install…**
2. Select the `io_cache` folder (zip it first if Blender asks for a zip).
3. Tick **"Bugsnax Cache (.objcache, .daecache)"** in the add-on list.

You'll get four new menu entries:

- File → Import → **Bugsnax Cache (.objcache)**
- File → Import → **Bugsnax Cache (.daecache)**
- File → Export → **Bugsnax Cache (.objcache)**
- File → Export → **Bugsnax Cache (.daecache)**

---

## Importing

| Option | Default | What it does |
|---|---|---|
| Scale | 1.0 | Uniform scale on the imported mesh |
| Import Textures | On | Loads referenced image files. If a texture isn't found on disk, a 1×1 placeholder is created so the path still round-trips when you export |

The importer creates one mesh object with a Principled-BSDF material.
Texture slots are wired up automatically: diffuse to **Base Color**,
normal to **Normal** (via a Normal Map node), specular to **Specular
IOR Level**. Cache files are Y-up; the importer rotates them to
Blender's Z-up convention so they sit upright in the viewport.

### Where the importer looks for textures

Cache files store asset-relative paths like
`Content/Models/Environment/Forest/Plants/PalmTree_D.dds`. The
importer searches:

- The cache file's directory
- Common subfolders: `Textures/`, `tex/`, `textures/`, `Content/`
- Up to three parent directories
- These extensions: `.png .jpg .jpeg .tga .dds .bmp .tif .tiff .webp`

---

## Exporting

| Option | Default | What it does |
|---|---|---|
| Selected Only | Off | Export only the selected mesh; otherwise the first mesh in the scene |
| Scale | 1.0 | Uniform scale on the exported mesh |

Texture paths are read from the active material's Principled-BSDF
inputs (the inverse of what the importer does). Asset-relative
`Content/...` paths are preserved verbatim; anything else falls back
to the file's basename.

### Static-mesh conformity

Both cache formats are **single static mesh** binaries. The exporter
silently strips anything else, sampled at the current frame:

- **Armature modifiers** are baked into the vertex positions via the
  depsgraph (current pose is what gets written)
- **Vertex groups / skin weights** are dropped (no skin slot in the format)
- **Shape keys** are evaluated at their current values before write
- **Animation actions** are ignored (single-frame format)

When any of these is present, the export report (Blender's status bar)
notes what was stripped. `.objcache` mirrors the OBJ format's
limitations; `.daecache` is the DAE *binary cache* — DAE the source
format supports skeletons, but the compiled cache does not.

---

## Round-trip behaviour

Import → export produces a structurally identical file. Vertex counts,
face counts, texture references, AABB, and the daecache extent all
round-trip exactly. Byte-level equality isn't guaranteed (small
metadata bytes are regenerated rather than carried verbatim) but the
engine reads the result identically.

The daecache extras (UV2, UV3) are exposed in Blender as additional UV
layers — keep those layer names intact if you want them preserved on
export.

---

## File layout

```
io_cache/
├── __init__.py    Blender operators and menu registration
├── parser.py      Binary read/write (CacheMesh dataclass)
├── importer.py    CacheMesh → Blender object
└── exporter.py    Blender object → CacheMesh → file
```
