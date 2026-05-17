"""Bugsnax / Horsepower Engine .objcache and .daecache import/export."""

bl_info = {
    "name": "Bugsnax Cache (.objcache, .daecache)",
    "author": "Claude",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import/Export",
    "description": "Import and export Bugsnax .objcache and .daecache mesh caches",
    "category": "Import-Export",
}

import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper

from . import importer
from . import exporter


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

    def execute(self, context):
        result, messages = importer.import_cache(
            context, self.filepath,
            global_scale=self.global_scale,
            import_textures=self.import_textures,
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

    def execute(self, context):
        result, messages = importer.import_cache(
            context, self.filepath,
            global_scale=self.global_scale,
            import_textures=self.import_textures,
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


def _menu_import_objcache(self, _context):
    self.layout.operator(ImportObjcache.bl_idname, text="Bugsnax Cache (.objcache)")


def _menu_import_daecache(self, _context):
    self.layout.operator(ImportDaecache.bl_idname, text="Bugsnax Cache (.daecache)")


def _menu_export_objcache(self, _context):
    self.layout.operator(ExportObjcache.bl_idname, text="Bugsnax Cache (.objcache)")


def _menu_export_daecache(self, _context):
    self.layout.operator(ExportDaecache.bl_idname, text="Bugsnax Cache (.daecache)")


_CLASSES = (ImportObjcache, ImportDaecache, ExportObjcache, ExportDaecache)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import_objcache)
    bpy.types.TOPBAR_MT_file_import.append(_menu_import_daecache)
    bpy.types.TOPBAR_MT_file_export.append(_menu_export_objcache)
    bpy.types.TOPBAR_MT_file_export.append(_menu_export_daecache)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import_objcache)
    bpy.types.TOPBAR_MT_file_import.remove(_menu_import_daecache)
    bpy.types.TOPBAR_MT_file_export.remove(_menu_export_objcache)
    bpy.types.TOPBAR_MT_file_export.remove(_menu_export_daecache)
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
