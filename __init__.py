"""Bugsnax / Horsepower Engine cache import/export.

Handles all three Horsepower-engine cache formats in one addon:

  * .objcache  — static mesh cache (pos/normal/colour/UV)
  * .daecache  — static mesh cache (+ tangent + UV2/UV3)
  * .xcache    — skinned-character cache (mesh + skeleton + skin
                 weights + animation), the SEMS format used by Bugsnax

Each format's code lives in one module per role — parser.py,
importer.py, exporter.py — with the static-cache and the .xcache
implementations consolidated side by side in the same file. The
.xcache half is the FROZEN, reverse-engineered SEMS logic ported from
the io_directx_x addon; it is self-contained within each module so
ongoing DirectX .x work can never regress the hard-won xcache behaviour.
"""

bl_info = {
    "name": "Bugsnax Cache (.objcache, .daecache, .xcache)",
    "author": "Saint Baron",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import/Export",
    "description": "Import and export Bugsnax .objcache, .daecache, and .xcache files",
    "category": "Import-Export",
}

import os

import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import importer            # objcache / daecache / xcache
from . import exporter            # objcache / daecache / xcache


# ---------------------------------------------------------------------------
# .objcache / .daecache  (static mesh caches)
# ---------------------------------------------------------------------------

class _CacheImportProperties:
    global_scale: FloatProperty(
        name="Scale",
        description="Uniform scale applied to imported geometry",
        default=1.0, min=0.0001, max=1000.0,
    )
    import_textures: BoolProperty(
        name="Import Textures",
        description=(
            "Load image files referenced by the cache. Missing files get a "
            "placeholder so the path still round-trips on export"
        ),
        default=True,
    )
    use_diffuse_alpha: BoolProperty(
        name="Use Diffuse Alpha",
        description=(
            "Connect the diffuse texture's alpha channel to material alpha "
            "(alpha-clip cutout) when the texture genuinely contains "
            "transparency. Foliage and other cutout textures use this; "
            "fully opaque textures are left solid"
        ),
        default=True,
    )


class ImportObjcache(bpy.types.Operator, ImportHelper, _CacheImportProperties):
    """Import a Bugsnax .objcache file as a static mesh"""
    bl_idname = "import_scene.objcache"
    bl_label = "Import Bugsnax .objcache"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".objcache"
    filter_glob: StringProperty(default="*.objcache", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale")
        box = layout.box()
        box.label(text="Data", icon="MESH_DATA")
        box.prop(self, "import_textures")
        box.prop(self, "use_diffuse_alpha")

    def execute(self, context):
        result, messages = importer.import_cache(
            context, self.filepath,
            global_scale=self.global_scale,
            import_textures=self.import_textures,
            use_diffuse_alpha=self.use_diffuse_alpha,
        )
        for m in messages:
            self.report({'WARNING'}, m)
        return result


class ImportDaecache(bpy.types.Operator, ImportHelper, _CacheImportProperties):
    """Import a Bugsnax .daecache file as a static mesh"""
    bl_idname = "import_scene.daecache"
    bl_label = "Import Bugsnax .daecache"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".daecache"
    filter_glob: StringProperty(default="*.daecache", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale")
        box = layout.box()
        box.label(text="Data", icon="MESH_DATA")
        box.prop(self, "import_textures")
        box.prop(self, "use_diffuse_alpha")

    def execute(self, context):
        result, messages = importer.import_cache(
            context, self.filepath,
            global_scale=self.global_scale,
            import_textures=self.import_textures,
            use_diffuse_alpha=self.use_diffuse_alpha,
        )
        for m in messages:
            self.report({'WARNING'}, m)
        return result


class _CacheExportProperties:
    use_selection: BoolProperty(
        name="Selected Only",
        description="Export only the selected mesh; otherwise the first mesh in the scene",
        default=False,
    )
    global_scale: FloatProperty(
        name="Scale",
        description="Uniform scale applied to exported geometry",
        default=1.0, min=0.0001, max=1000.0,
    )


class ExportObjcache(bpy.types.Operator, ExportHelper, _CacheExportProperties):
    """Export the active mesh as a Bugsnax .objcache file"""
    bl_idname = "export_scene.objcache"
    bl_label = "Export Bugsnax .objcache"
    bl_options = {'PRESET'}

    filename_ext = ".objcache"
    filter_glob: StringProperty(default="*.objcache", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Include", icon="OUTLINER")
        box.prop(self, "use_selection")
        box = layout.box()
        box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale")

    def execute(self, context):
        result, messages = exporter.export_cache(
            context, self.filepath,
            use_selection=self.use_selection,
            global_scale=self.global_scale,
            force_type="obj",
        )
        severity = 'ERROR' if result == {'CANCELLED'} else 'INFO'
        for m in messages:
            self.report({severity}, m)
        return result


class ExportDaecache(bpy.types.Operator, ExportHelper, _CacheExportProperties):
    """Export the active mesh as a Bugsnax .daecache file"""
    bl_idname = "export_scene.daecache"
    bl_label = "Export Bugsnax .daecache"
    bl_options = {'PRESET'}

    filename_ext = ".daecache"
    filter_glob: StringProperty(default="*.daecache", options={'HIDDEN'})

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Include", icon="OUTLINER")
        box.prop(self, "use_selection")
        box = layout.box()
        box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale")

    def execute(self, context):
        result, messages = exporter.export_cache(
            context, self.filepath,
            use_selection=self.use_selection,
            global_scale=self.global_scale,
            force_type="dae",
        )
        severity = 'ERROR' if result == {'CANCELLED'} else 'INFO'
        for m in messages:
            self.report({severity}, m)
        return result


# ---------------------------------------------------------------------------
# .xcache  (skinned-character cache — FROZEN SEMS path)
# ---------------------------------------------------------------------------

class ImportXcache(bpy.types.Operator, ImportHelper):
    """Import a Bugsnax .xcache skinned character (mesh + skeleton + animation)"""
    bl_idname = "import_scene.bugsnax_xcache"
    bl_label = "Import Bugsnax .xcache"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".xcache"
    filter_glob: StringProperty(default="*.xcache;*.XCACHE", options={'HIDDEN'})

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    global_scale: FloatProperty(
        name="Scale", default=1.0, min=0.001, max=1000.0,
        description="Uniform scale applied to imported geometry")
    axis_forward: EnumProperty(
        name="Forward Axis",
        items=[(a, a, "") for a in ("X", "-X", "Y", "-Y", "Z", "-Z")],
        default="-Z")
    axis_up: EnumProperty(
        name="Up Axis",
        items=[(a, a, "") for a in ("X", "-X", "Y", "-Y", "Z", "-Z")],
        default="Y")
    import_normals:   BoolProperty(name="Import Normals",   default=True)
    import_uvs:       BoolProperty(name="Import UVs",       default=True)
    import_materials: BoolProperty(name="Import Materials", default=True)
    import_textures:  BoolProperty(name="Import Textures",  default=True)
    use_diffuse_alpha: BoolProperty(
        name="Use Diffuse Alpha",
        description="Connect the diffuse texture's alpha channel to material alpha",
        default=True)
    split_submeshes: BoolProperty(
        name="Split Sub-Meshes",
        description="Split an xcache's internal multi-mesh structure into separate Blender objects",
        default=True)
    import_armature:  BoolProperty(name="Import Armature",  default=True)
    import_weights:   BoolProperty(name="Import Weights",   default=True)
    import_animation: BoolProperty(name="Import Animation", default=True)
    weld_duplicate_verts: BoolProperty(
        name="Weld Duplicate Vertices",
        description="Weld duplicate-position verts so bone-deformation boundaries don't separate when animated",
        default=True)
    rest_pose_source: EnumProperty(
        name="Rest Pose Source",
        description=(
            "Where to read bone rest poses from. Bind Pose (default) uses "
            "the SkinWeights matrixOffset inverse-bind matrices — the "
            "correct interpretation for Bugsnax xcache files."
        ),
        items=[
            ('BIND',            "Bind Pose",       "Use SkinWeights matrixOffset (correct for xcache)"),
            ('FRAME_TRANSFORM', "Frame Hierarchy", "Use FrameTransformMatrix chain"),
        ],
        default='BIND')
    infer_sharps: BoolProperty(name="Infer Sharp Edges", default=True)
    anim_fps: FloatProperty(name="Animation FPS", default=0.0, min=0.0, max=240.0)
    set_frame_range: BoolProperty(name="Set Scene Frame Range", default=True)

    def draw(self, context):
        layout = self.layout
        box = layout.box(); box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale"); box.prop(self, "axis_forward"); box.prop(self, "axis_up")
        box = layout.box(); box.label(text="Geometry", icon="MESH_DATA")
        box.prop(self, "import_normals"); box.prop(self, "import_uvs")
        box.prop(self, "split_submeshes"); box.prop(self, "weld_duplicate_verts")
        box = layout.box(); box.label(text="Materials", icon="MATERIAL")
        box.prop(self, "import_materials"); box.prop(self, "import_textures")
        box.prop(self, "use_diffuse_alpha")
        box = layout.box(); box.label(text="Rig", icon="ARMATURE_DATA")
        box.prop(self, "import_armature"); box.prop(self, "import_weights")
        box.prop(self, "import_animation"); box.prop(self, "rest_pose_source")
        box.prop(self, "anim_fps"); box.prop(self, "set_frame_range")

    def execute(self, context):
        if self.files and self.directory:
            filepaths = [os.path.join(self.directory, f.name) for f in self.files if f.name]
        else:
            filepaths = [self.filepath]
        seen = set(); unique_paths = []
        for p in filepaths:
            if p not in seen:
                seen.add(p); unique_paths.append(p)

        keywords = self.as_keywords(ignore=("filter_glob", "files", "directory"))
        last_result = {"FINISHED"}; errors = []
        for fp in unique_paths:
            keywords["filepath"] = fp
            try:
                last_result = importer.import_xcache(context, **keywords)
            except Exception as e:
                errors.append((fp, e))
        if errors:
            msg = "; ".join(f"{os.path.basename(fp)}: {e}" for fp, e in errors)
            self.report({'ERROR'}, f"Import failed: {msg}")
            return {'CANCELLED'} if len(errors) == len(unique_paths) else {'FINISHED'}
        return last_result


class ExportXcache(bpy.types.Operator, ExportHelper):
    """Export the scene armature + skin + animation as a Bugsnax .xcache file"""
    bl_idname = "export_scene.bugsnax_xcache"
    bl_label = "Export Bugsnax .xcache"
    bl_options = {'PRESET'}

    filename_ext = ".xcache"
    filter_glob: StringProperty(default="*.xcache;*.XCACHE", options={'HIDDEN'})

    use_selection: BoolProperty(name="Selected Only", default=False)
    use_mesh_modifiers: BoolProperty(name="Apply Modifiers", default=True)
    global_scale: FloatProperty(name="Scale", default=1.0, min=0.001, max=1000.0)
    axis_forward: EnumProperty(
        name="Forward Axis",
        items=[(a, a, "") for a in ("X", "-X", "Y", "-Y", "Z", "-Z")],
        default="-Z")
    axis_up: EnumProperty(
        name="Up Axis",
        items=[(a, a, "") for a in ("X", "-X", "Y", "-Y", "Z", "-Z")],
        default="Y")
    export_armature:  BoolProperty(name="Export Armature",  default=True)
    export_weights:   BoolProperty(name="Export Weights",   default=True)
    export_animation: BoolProperty(name="Export Animation", default=True)
    anim_frame_start: bpy.props.IntProperty(name="Frame Start", default=1)
    anim_frame_end:   bpy.props.IntProperty(name="Frame End",   default=250)

    def draw(self, context):
        layout = self.layout
        box = layout.box(); box.label(text="Include", icon="OUTLINER")
        box.prop(self, "use_selection"); box.prop(self, "use_mesh_modifiers")
        box.prop(self, "export_armature"); box.prop(self, "export_weights")
        box.prop(self, "export_animation")
        box = layout.box(); box.label(text="Animation Range", icon="TIME")
        box.prop(self, "anim_frame_start"); box.prop(self, "anim_frame_end")
        box = layout.box(); box.label(text="Transform", icon="ORIENTATION_GLOBAL")
        box.prop(self, "global_scale"); box.prop(self, "axis_forward"); box.prop(self, "axis_up")

    def execute(self, context):
        keywords = self.as_keywords(ignore=("filter_glob", "check_existing"))
        try:
            result, warnings = exporter.export_xcache_from_blender(context, **keywords)
        except Exception as e:
            self.report({'ERROR'}, f"Export failed: {e}")
            return {'CANCELLED'}
        severity = 'ERROR' if result == {'CANCELLED'} else 'WARNING'
        for msg in warnings:
            self.report({severity}, msg)
        return result


# ---------------------------------------------------------------------------
# Menu entries + registration
# ---------------------------------------------------------------------------

def _menu_import_objcache(self, _c):
    self.layout.operator(ImportObjcache.bl_idname, text="Bugsnax Cache (.objcache)")

def _menu_import_daecache(self, _c):
    self.layout.operator(ImportDaecache.bl_idname, text="Bugsnax Cache (.daecache)")

def _menu_import_xcache(self, _c):
    self.layout.operator(ImportXcache.bl_idname, text="Bugsnax Cache (.xcache)")

def _menu_export_objcache(self, _c):
    self.layout.operator(ExportObjcache.bl_idname, text="Bugsnax Cache (.objcache)")

def _menu_export_daecache(self, _c):
    self.layout.operator(ExportDaecache.bl_idname, text="Bugsnax Cache (.daecache)")

def _menu_export_xcache(self, _c):
    self.layout.operator(ExportXcache.bl_idname, text="Bugsnax Cache (.xcache)")


_CLASSES = (
    ImportObjcache, ImportDaecache, ImportXcache,
    ExportObjcache, ExportDaecache, ExportXcache,
)

_IMPORT_MENUS = (_menu_import_objcache, _menu_import_daecache, _menu_import_xcache)
_EXPORT_MENUS = (_menu_export_objcache, _menu_export_daecache, _menu_export_xcache)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    for fn in _IMPORT_MENUS:
        bpy.types.TOPBAR_MT_file_import.append(fn)
    for fn in _EXPORT_MENUS:
        bpy.types.TOPBAR_MT_file_export.append(fn)


def unregister():
    for fn in _IMPORT_MENUS:
        bpy.types.TOPBAR_MT_file_import.remove(fn)
    for fn in _EXPORT_MENUS:
        bpy.types.TOPBAR_MT_file_export.remove(fn)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
