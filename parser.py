"""Read/write Bugsnax .objcache and .daecache binary mesh files.

Both share the SEMS magic with .xcache but carry only a static mesh
with optional texture references. Type byte at +0x10 picks the variant
(0 = obj, 2 = dae); daecache uses a 64-byte vertex stride that adds
tangents and two extra UV channels to objcache's 36-byte stride.
"""

import struct
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CacheMesh:
    """Parsed cache mesh, used as the exchange format between
    parser/writer and the Blender importer/exporter."""
    cache_type: str = "obj"
    aabb_min: tuple = (0.0, 0.0, 0.0)
    aabb_max: tuple = (0.0, 0.0, 0.0)
    # Per-asset tint, RGBA bytes. Objcache stores it at +0x40; daecache
    # doesn't have a tint slot.
    tint_rgba: bytes = b'\xff\xff\xff\xff'
    # Daecache-only bounding-radius-ish float at +0x44.
    dae_extent: float = 0.0
    # Up to three texture paths in the order: diffuse, normal, specular.
    textures: list = field(default_factory=list)
    # Per-vertex data; UVs are NOT V-flipped here.
    positions: list = field(default_factory=list)
    normals:   list = field(default_factory=list)
    colors:    list = field(default_factory=list)
    uvs:       list = field(default_factory=list)
    # Daecache-only per-vertex extras. Tangents are zero in every shipped
    # sample; uv2/uv3 look like wind/LOD parameters and are constant
    # within a mesh.
    tangents:  list = field(default_factory=list)
    uv2:       list = field(default_factory=list)
    uv3:       list = field(default_factory=list)
    # Triangle list, u16 indices.
    faces: list = field(default_factory=list)


_TEXTURE_PATH_RE = re.compile(rb'Content/[\x20-\x7e]+?\.(?:dds|tga|png|jpg|bmp)',
                              re.IGNORECASE)


def parse_cache_file(filepath: str) -> CacheMesh:
    """Parse .objcache or .daecache. Variant auto-detected from +0x10."""
    with open(filepath, 'rb') as fh:
        data = fh.read()

    if len(data) < 0x40 or data[:4] != b'SEMS':
        raise ValueError(f"Not a SEMS cache file: magic={data[:4]!r}, size={len(data)}")

    type_flag = struct.unpack('<I', data[0x10:0x14])[0]
    if type_flag == 2:
        cache_type, vert_stride = "dae", 64
    else:
        cache_type, vert_stride = "obj", 36

    out = CacheMesh(cache_type=cache_type)
    out.aabb_min = struct.unpack('<3f', data[0x1C:0x28])
    out.aabb_max = struct.unpack('<3f', data[0x28:0x34])

    # +0x34..+0x54: variant-specific header tail. Both end with the 1.0
    # scale float at +0x50 followed by the texture section at +0x54.
    if cache_type == "dae":
        out.dae_extent = struct.unpack('<f', data[0x44:0x48])[0]
    else:
        out.tint_rgba = data[0x40:0x44]

    # Texture paths are length-prefixed (u32 LE just before each path).
    # Require the prefix length to match the run length so we don't pick
    # up coincidental ASCII inside geometry. Track the end of the last
    # valid path so we can start the vertex-count scan from there.
    last_path_end = 0x54
    for m in _TEXTURE_PATH_RE.finditer(data):
        path = m.group()
        if m.start() < 4:
            continue
        prefix_len = struct.unpack('<I', data[m.start() - 4:m.start()])[0]
        if prefix_len != len(path):
            continue
        try:
            out.textures.append(path.decode('utf-8'))
        except UnicodeDecodeError:
            out.textures.append(path.decode('latin-1'))
        last_path_end = max(last_path_end, m.end())

    # Find the vertex-count u32 by trying candidate offsets after the
    # header and verifying the resulting geometry fits the rest of the
    # file exactly.
    vc_off = _locate_vertex_count(data, last_path_end, vert_stride)
    if vc_off is None:
        raise ValueError(f"Could not locate vertex section in {filepath}")

    n_verts = struct.unpack('<I', data[vc_off:vc_off + 4])[0]
    verts_start = vc_off + 4

    for i in range(n_verts):
        base = verts_start + i * vert_stride
        out.positions.append(struct.unpack('<3f', data[base + 0:base + 12]))
        out.normals.append  (struct.unpack('<3f', data[base + 12:base + 24]))
        out.colors.append   (data[base + 24:base + 28])
        out.uvs.append      (struct.unpack('<2f', data[base + 28:base + 36]))
        if cache_type == "dae":
            out.tangents.append(struct.unpack('<3f', data[base + 36:base + 48]))
            out.uv2.append     (struct.unpack('<2f', data[base + 48:base + 56]))
            out.uv3.append     (struct.unpack('<2f', data[base + 56:base + 64]))

    idx_off = verts_start + n_verts * vert_stride
    idx_count = struct.unpack('<I', data[idx_off:idx_off + 4])[0]
    idx_start = idx_off + 4
    for f in range(idx_count // 3):
        base = idx_start + f * 6
        out.faces.append(struct.unpack('<3H', data[base:base + 6]))

    return out


def _locate_vertex_count(data: bytes, scan_start: int, stride: int) -> Optional[int]:
    """Return the file offset of the vertex-count u32, or None.

    The texture section between +0x54 and the vertex count is
    variable-length, so we try each u32 offset and pick the one where
    geometry + indices line up exactly with EOF and the first vertex's
    normal looks unit-length.
    """
    file_len = len(data)
    for vc_off in range(scan_start, min(scan_start + 256, file_len - 8)):
        n_verts = struct.unpack('<I', data[vc_off:vc_off + 4])[0]
        if n_verts < 3 or n_verts > 5_000_000:
            continue
        verts_start = vc_off + 4
        idx_off = verts_start + n_verts * stride
        if idx_off + 4 >= file_len:
            continue
        idx_count = struct.unpack('<I', data[idx_off:idx_off + 4])[0]
        if idx_count == 0 or idx_count % 3 != 0 or idx_count > 5_000_000:
            continue
        if idx_off + 4 + idx_count * 2 != file_len:
            continue
        try:
            nx, ny, nz = struct.unpack('<3f', data[verts_start + 12:verts_start + 24])
        except struct.error:
            continue
        if 0.95 < nx * nx + ny * ny + nz * nz < 1.05:
            return vc_off
    return None


def write_cache_file(mesh: CacheMesh, filepath: str) -> None:
    """Serialize a CacheMesh back to .objcache or .daecache."""
    cache_type = mesh.cache_type
    vert_stride = 64 if cache_type == "dae" else 36
    out = bytearray()

    # Common header +0x00..+0x34
    out += b'SEMS'
    out += b'\x00' * 8
    out += struct.pack('<I', 1)                              # version
    out += struct.pack('<I', 2 if cache_type == "dae" else 0)
    out += b'\x00' * 8
    out += struct.pack('<3f', *mesh.aabb_min)
    out += struct.pack('<3f', *mesh.aabb_max)

    # Variant-specific tail +0x34..+0x54 (32 bytes). Reconstructs the
    # constant flag bytes observed across every sample and slots in the
    # per-file tint (obj) or extent (dae).
    if cache_type == "dae":
        out += b'\x00\x00\x00\xff\xff\xff\xff\xff'
        out += b'\x00\x00\x00\xff\xff\xff\xff\xff'
        out += struct.pack('<f', mesh.dae_extent)
        out += b'\x00' * 8
        out += struct.pack('<f', 1.0)
    else:
        out += b'\x00\x00\x00\xff\xff\xff\xff\xff'
        out += b'\x00\x00\x00\x00'
        out += (mesh.tint_rgba + b'\xff\xff\xff\xff')[:4]
        out += b'\x00\x00\x00\x43'
        out += b'\x00' * 8
        out += struct.pack('<f', 1.0)

    # Texture section + standard pre-vertex metadata blob.
    out += _synthesize_texture_section(mesh.textures)

    # Vertex stream.
    n_verts = len(mesh.positions)
    out += struct.pack('<I', n_verts)

    def _color(i):
        if i < len(mesh.colors) and mesh.colors[i]:
            return (mesh.colors[i] + b'\xff\xff\xff\xff')[:4]
        return b'\xff\xff\xff\xff'

    def _uv(arr, i):
        return arr[i] if i < len(arr) else (0.0, 0.0)

    for i in range(n_verts):
        out += struct.pack('<3f', *mesh.positions[i])
        out += struct.pack('<3f', *(mesh.normals[i] if i < len(mesh.normals)
                                    else (0.0, 0.0, 1.0)))
        out += _color(i)
        out += struct.pack('<2f', *_uv(mesh.uvs, i))
        if cache_type == "dae":
            tn = mesh.tangents[i] if i < len(mesh.tangents) else (0.0, 0.0, 0.0)
            out += struct.pack('<3f', *tn)
            out += struct.pack('<2f', *_uv(mesh.uv2, i))
            out += struct.pack('<2f', *_uv(mesh.uv3, i))

    # Index stream.
    out += struct.pack('<I', len(mesh.faces) * 3)
    for tri in mesh.faces:
        out += struct.pack('<3H', tri[0], tri[1], tri[2])

    with open(filepath, 'wb') as fh:
        fh.write(out)


def _synthesize_texture_section(textures: list) -> bytes:
    """Write the texture entries plus the standard trailing metadata
    block (the same byte pattern in every shipped sample)."""
    out = bytearray()
    # Each entry: 0x01 flag, u32 LE length, path bytes. Entries are
    # joined by a 6-byte zero pad.
    for i, path in enumerate(textures[:3]):
        if i > 0:
            out += b'\x00' * 6
        path_b = path.encode('utf-8')
        out += b'\x01'
        out += struct.pack('<I', len(path_b))
        out += path_b
    # Trailing metadata, byte-for-byte from the shipped samples.
    out += b'\x00' * 12
    out += b'\x01\x01\x01\x01\x00\x00\x01\x01\x01\x0f\x01'
    out += b'\x00\x00\x00\x00\x00\xff\xff\xff\xff'
    out += b'\x01\x00\x00\x80\x3f\x00\x00\x80\x3f'
    out += b'\x00' * 8
    return bytes(out)
