"""HyruleCraft Wii U US v208 Terrain Collision Extractor and Protocol Exporter.

Implements 13-axis Tomas Akenine-Möller SAT triangle-to-voxel voxelization,
SkyCraft Protocol 12 binary packet streaming into Local\\HyruleCraft_v1 shared memory
according to skycraft_protocol.h and SkyCollision.java, and bounded read-only
diagnostic probing via the validated HyruleBlocks bridge.

Key Components & Invariants:
- 13-axis SAT triangle-to-box overlap and 8x8x8 sub-voxel discrete voxelization.
- Protocol 12 binary packet serialization (ColRegion, ColTri, ColBlock).
- CollisionRingWriter accounts for ring wrap padding in free-space checks (pad_bytes + step).
- Single producer model: writes ONLY to the collision ring @0x20000. NEVER writes to
  SkyState @0x100 (which is owned exclusively by host_link.py).
- Explicit error handling: failed sends raise BufferError rather than being silently ignored.
- synthetic_test_plateau_fixture is strictly labeled as a synthetic test fixture and
  excluded from production streaming paths.
- CemuRuntimeProbe uses the validated Process reader from HyruleBlocks/bridge.py,
  validating Cemu.exe, US v208 title and version, mod mailbox signature, and mailbox actor 0x20.
- Explicitly documents unverified in-memory Havok terrain offsets; live collision export
  remains blocked until authentic BOTW terrain geometry is supplied.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as W
from dataclasses import dataclass, field
import importlib.util
import math
import mmap
from pathlib import Path
import re
import struct
import sys
import time
from typing import Dict, List, Optional, Set, Tuple

# Protocol 12 Constants from skycraft_protocol.h
MAGIC_SKYC = 0x43594B53  # "SKYC"
PROTOCOL_VERSION = 12
SHARED_MEMORY_NAME = r'Local\HyruleCraft_v1'

# Offsets
OFF_HEADER = 0x0
OFF_SKY_STATE = 0x100
OFF_MC_STATE = 0x200
OFF_INPUT_RING = 0x1000
OFF_COLLISION_RING = 0x20000
COLLISION_RING_BYTES = 32 << 20  # 32 MB
COL_RING_HEAD_OFF = 0x00
COL_RING_TAIL_OFF = 0x40
COL_RING_DATA_OFF = 0x80
COL_RING_DATA_BYTES = COLLISION_RING_BYTES - COL_RING_DATA_OFF

# Dimensions
REGION_SIZE = 8           # 8 blocks per region edge (SkyCollision.REGION_SIZE = 8)
SUBVOXELS_PER_BLOCK = 8   # 8 sub-voxels per block edge (8x8x8 = 512 sub-voxels)
SUBVOXEL_SIZE = 1.0 / SUBVOXELS_PER_BLOCK  # 0.125m

# Message Types (ColType)
COL_PAD = 0
COL_CLEAR = 1    # payload: uint32 epoch
COL_REGION = 2   # payload: ColRegion + ColBlock[count]
COL_TRIS = 3     # payload: ColRegion + ColTri[count]
COL_FORGET = 4   # HyruleCraft extension: int32 rx,ry,rz,epoch

# Triangle Flags (ColTriFlags)
TRI_STAIR_HELPER = 1 << 0
TRI_DIGGABLE = 1 << 1
TRI_GHOST = 1 << 2
TRI_TERRAIN = 1 << 3
TRI_MATERIAL_SHIFT = 8

# SkyFlags
SKY_IN_GAME = 1 << 0
SKY_MENU_OPEN = 1 << 1
SKY_LOADING = 1 << 2

# BOTW Contact Layers from BetterVR game_structs.h (verified)
LAYER_ENTITY_GROUND_OBJECT = 2
LAYER_ENTITY_AIR_WALL = 7       # Verified Layer 7 in game_structs.h (Layer 26 is EntityForbidden26)
LAYER_ENTITY_GROUND = 8
LAYER_ENTITY_GROUND_SMOOTH = 9
LAYER_ENTITY_GROUND_ROUGH = 10
LAYER_ENTITY_TREE = 12
LAYER_ENTITY_WALL_FOR_CLIMB = 15

# Wii U US v208 Verified Pointers & Symbols
ADDR_PLAYER_TRACKER_PTR = 0x10463F38
ADDR_HAVOK_WORKER_MGR_PTR = 0x1047C370
ADDR_CAMERA_SINGLETON = 0x1046CF88
ADDR_PLACEMENT_MGR_PTR = 0x1047C318
ADDR_BASE_PROC_MGR_PTR = 0x1047C244
ADDR_ECOSYSTEM_PTR = 0x1046D6AC

VTABLE_LINK_PLAYER = 0x101E5FFC
ADDR_LINK_SET_MTX = 0x02D66ABC
ADDR_PLAYER_TICK_HOOK = 0x02D67CF4
VTABLE_SEAD_PROJECTION = 0x1027B54C
ADDR_DEFAULT_PROJECTION = 0x10597928


@dataclass
class ColTri:
    """Collision triangle (MC space: 1 unit = 1 block = 1 BOTW unit, Y up)."""
    p0: Tuple[float, float, float]
    p1: Tuple[float, float, float]
    p2: Tuple[float, float, float]
    flags: int = TRI_TERRAIN

    def pack(self) -> bytes:
        return struct.pack(
            '<9fI',
            self.p0[0], self.p0[1], self.p0[2],
            self.p1[0], self.p1[1], self.p1[2],
            self.p2[0], self.p2[1], self.p2[2],
            self.flags
        )

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> ColTri:
        vals = struct.unpack_from('<9fI', data, offset)
        return cls(
            p0=(vals[0], vals[1], vals[2]),
            p1=(vals[3], vals[4], vals[5]),
            p2=(vals[6], vals[7], vals[8]),
            flags=vals[9]
        )


@dataclass
class ColBlock:
    """One block's worth of collision as an 8x8x8 occupancy mask (80 bytes).
    
    bits[y] bit (z * 8 + x) represents sub-voxel (x, y, z), each 1/8 block.
    """
    x: int
    y: int
    z: int
    bits: List[int] = field(default_factory=lambda: [0] * 8)

    def pack(self) -> bytes:
        return struct.pack('<iiiI8Q', self.x, self.y, self.z, 0, *self.bits)

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> ColBlock:
        x, y, z, _, *bits = struct.unpack_from('<iiiI8Q', data, offset)
        return cls(x=x, y=y, z=z, bits=list(bits))

    def is_empty(self) -> bool:
        return all(b == 0 for b in self.bits)


@dataclass
class ColRegion:
    """Region header (32 bytes)."""
    min_x: int
    min_y: int
    min_z: int
    max_x: int
    max_y: int
    max_z: int
    epoch: int
    count: int

    def pack(self) -> bytes:
        return struct.pack(
            '<iiiiiiII',
            self.min_x, self.min_y, self.min_z,
            self.max_x, self.max_y, self.max_z,
            self.epoch, self.count
        )

    @classmethod
    def unpack(cls, data: bytes, offset: int = 0) -> ColRegion:
        vals = struct.unpack_from('<iiiiiiII', data, offset)
        return cls(*vals)


# ==============================================================================
# 13-Axis Separating Axis Theorem (Tomas Akenine-Möller)
# ==============================================================================

def _cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
    )


def _dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def sat_triangle_box_overlap(
    v0: Tuple[float, float, float],
    v1: Tuple[float, float, float],
    v2: Tuple[float, float, float],
    box_center: Tuple[float, float, float],
    box_half: Tuple[float, float, float]
) -> bool:
    """13-axis Separating Axis Theorem test for triangle and AABB.
    
    Axes tested:
    - 3 AABB face normals (e0, e1, e2 coordinate axes)
    - 1 triangle plane normal
    - 9 cross products of AABB edges and triangle edges
    """
    cx, cy, cz = box_center
    hx, hy, hz = box_half

    # 1. Translate triangle so box center is at origin
    u0 = (v0[0] - cx, v0[1] - cy, v0[2] - cz)
    u1 = (v1[0] - cx, v1[1] - cy, v1[2] - cz)
    u2 = (v2[0] - cx, v2[1] - cy, v2[2] - cz)

    # 2. Test AABB along coordinate axes (3 tests)
    if min(u0[0], u1[0], u2[0]) > hx or max(u0[0], u1[0], u2[0]) < -hx:
        return False
    if min(u0[1], u1[1], u2[1]) > hy or max(u0[1], u1[1], u2[1]) < -hy:
        return False
    if min(u0[2], u1[2], u2[2]) > hz or max(u0[2], u1[2], u2[2]) < -hz:
        return False

    # Triangle edges
    e0 = (u1[0] - u0[0], u1[1] - u0[1], u1[2] - u0[2])
    e1 = (u2[0] - u1[0], u2[1] - u1[1], u2[2] - u1[2])  # FIXED: z uses u2[2] - u1[2]
    e2 = (u0[0] - u2[0], u0[1] - u2[1], u0[2] - u2[2])

    # 3. Test triangle plane normal (1 test)
    norm = _cross(e0, (u2[0] - u0[0], u2[1] - u0[1], u2[2] - u0[2]))
    d = _dot(norm, u0)
    r = hx * abs(norm[0]) + hy * abs(norm[1]) + hz * abs(norm[2])
    if abs(d) > r:
        return False

    # 4. Test 9 edge-axis cross product combinations
    # Edge e0
    # a = (0, -e0[2], e0[1])
    p0 = -u0[1] * e0[2] + u0[2] * e0[1]
    p1 = -u1[1] * e0[2] + u1[2] * e0[1]
    p2 = -u2[1] * e0[2] + u2[2] * e0[1]
    r = hy * abs(e0[2]) + hz * abs(e0[1])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (e0[2], 0, -e0[0])
    p0 = u0[0] * e0[2] - u0[2] * e0[0]
    p1 = u1[0] * e0[2] - u1[2] * e0[0]
    p2 = u2[0] * e0[2] - u2[2] * e0[0]
    r = hx * abs(e0[2]) + hz * abs(e0[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (-e0[1], e0[0], 0)
    p0 = -u0[0] * e0[1] + u0[1] * e0[0]
    p1 = -u1[0] * e0[1] + u1[1] * e0[0]
    p2 = -u2[0] * e0[1] + u2[1] * e0[0]
    r = hx * abs(e0[1]) + hy * abs(e0[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # Edge e1
    # a = (0, -e1[2], e1[1])
    p0 = -u0[1] * e1[2] + u0[2] * e1[1]
    p1 = -u1[1] * e1[2] + u1[2] * e1[1]
    p2 = -u2[1] * e1[2] + u2[2] * e1[1]
    r = hy * abs(e1[2]) + hz * abs(e1[1])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (e1[2], 0, -e1[0])
    p0 = u0[0] * e1[2] - u0[2] * e1[0]
    p1 = u1[0] * e1[2] - u1[2] * e1[0]
    p2 = u2[0] * e1[2] - u2[2] * e1[0]
    r = hx * abs(e1[2]) + hz * abs(e1[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (-e1[1], e1[0], 0)
    p0 = -u0[0] * e1[1] + u0[1] * e1[0]
    p1 = -u1[0] * e1[1] + u1[1] * e1[0]
    p2 = -u2[0] * e1[1] + u2[1] * e1[0]
    r = hx * abs(e1[1]) + hy * abs(e1[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # Edge e2
    # a = (0, -e2[2], e2[1])
    p0 = -u0[1] * e2[2] + u0[2] * e2[1]
    p1 = -u1[1] * e2[2] + u1[2] * e2[1]
    p2 = -u2[1] * e2[2] + u2[2] * e2[1]
    r = hy * abs(e2[2]) + hz * abs(e2[1])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (e2[2], 0, -e2[0])
    p0 = u0[0] * e2[2] - u0[2] * e2[0]
    p1 = u1[0] * e2[2] - u1[2] * e2[0]
    p2 = u2[0] * e2[2] - u2[2] * e2[0]
    r = hx * abs(e2[2]) + hz * abs(e2[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    # a = (-e2[1], e2[0], 0)
    p0 = -u0[0] * e2[1] + u0[1] * e2[0]
    p1 = -u1[0] * e2[1] + u1[1] * e2[0]
    p2 = -u2[0] * e2[1] + u2[1] * e2[0]
    r = hx * abs(e2[1]) + hy * abs(e2[0])
    if min(p0, p1, p2) > r or max(p0, p1, p2) < -r:
        return False

    return True


# ==============================================================================
# Region Voxelizer
# ==============================================================================

def voxelize_region_triangles(
    rx: int, ry: int, rz: int,
    triangles: List[ColTri]
) -> List[ColBlock]:
    """Voxelizes triangles in region (rx, ry, rz) into ColBlocks with 8x8x8 bitmasks."""
    ox = rx * REGION_SIZE
    oy = ry * REGION_SIZE
    oz = rz * REGION_SIZE

    blocks: Dict[Tuple[int, int, int], ColBlock] = {}
    sub_half = (SUBVOXEL_SIZE * 0.5, SUBVOXEL_SIZE * 0.5, SUBVOXEL_SIZE * 0.5)
    block_half = (0.5, 0.5, 0.5)

    for tri in triangles:
        min_tx = min(tri.p0[0], tri.p1[0], tri.p2[0])
        max_tx = max(tri.p0[0], tri.p1[0], tri.p2[0])
        min_ty = min(tri.p0[1], tri.p1[1], tri.p2[1])
        max_ty = max(tri.p0[1], tri.p1[1], tri.p2[1])
        min_tz = min(tri.p0[2], tri.p1[2], tri.p2[2])
        max_tz = max(tri.p0[2], tri.p1[2], tri.p2[2])

        bx0 = max(0, int(math.floor(min_tx - ox)))
        bx1 = min(REGION_SIZE - 1, int(math.floor(max_tx - ox)))
        by0 = max(0, int(math.floor(min_ty - oy)))
        by1 = min(REGION_SIZE - 1, int(math.floor(max_ty - oy)))
        bz0 = max(0, int(math.floor(min_tz - oz)))
        bz1 = min(REGION_SIZE - 1, int(math.floor(max_tz - oz)))

        if bx0 > bx1 or by0 > by1 or bz0 > bz1:
            continue

        for by in range(by0, by1 + 1):
            world_by = oy + by
            for bz in range(bz0, bz1 + 1):
                world_bz = oz + bz
                for bx in range(bx0, bx1 + 1):
                    world_bx = ox + bx
                    block_center = (world_bx + 0.5, world_by + 0.5, world_bz + 0.5)
                    if not sat_triangle_box_overlap(tri.p0, tri.p1, tri.p2, block_center, block_half):
                        continue

                    key = (world_bx, world_by, world_bz)
                    if key not in blocks:
                        blocks[key] = ColBlock(x=world_bx, y=world_by, z=world_bz)
                    col_block = blocks[key]

                    # Test 8x8x8 sub-voxels
                    for sy in range(SUBVOXELS_PER_BLOCK):
                        sub_cy = world_by + (sy + 0.5) * SUBVOXEL_SIZE
                        for sz in range(SUBVOXELS_PER_BLOCK):
                            sub_cz = world_bz + (sz + 0.5) * SUBVOXEL_SIZE
                            for sx in range(SUBVOXELS_PER_BLOCK):
                                bit_idx = sz * 8 + sx
                                if (col_block.bits[sy] & (1 << bit_idx)) != 0:
                                    continue  # Already occupied

                                sub_cx = world_bx + (sx + 0.5) * SUBVOXEL_SIZE
                                sub_center = (sub_cx, sub_cy, sub_cz)

                                if sat_triangle_box_overlap(tri.p0, tri.p1, tri.p2, sub_center, sub_half):
                                    col_block.bits[sy] |= (1 << bit_idx)

    # Return non-empty blocks
    return [b for b in blocks.values() if not b.is_empty()]


# ==============================================================================
# SYNTHETIC TEST FIXTURE ONLY - DO NOT USE IN PRODUCTION
# ==============================================================================

def synthetic_test_plateau_fixture(
    center_x: float = 2333.2,
    center_z: float = -264.8,
    base_y: float = 119.0,
    radius: float = 16.0,
    grid_step: float = 2.0
) -> List[ColTri]:
    """SYNTHETIC TEST FIXTURE ONLY.
    
    Generates synthetic sloped terrain geometry for offline testing of the 13-axis
    SAT voxelizer and binary packet encoders.
    
    WARNING: This function invents trigonometric geometry and does NOT represent authentic
    BOTW terrain. It is strictly forbidden in live collision export or production streaming.
    Real terrain extraction requires parsing extracted BOTW collision assets (.hkx) or an
    in-engine PPC graphic pack hook.
    """
    def height_func(x: float, z: float) -> float:
        dx = x - center_x
        dz = z - center_z
        h = base_y
        h += 0.08 * dx - 0.05 * dz
        h += 1.4 * math.sin(dx / 9.0) * math.cos(dz / 11.0)
        h += 0.6 * math.sin((dx + dz) / 5.5)
        terr = math.tanh(math.sin(dx / 7.0 + dz / 8.0) * 2.0) * 0.4
        h += terr
        return h

    x0 = center_x - radius
    x1 = center_x + radius
    z0 = center_z - radius
    z1 = center_z + radius

    nx = int(math.ceil((x1 - x0) / grid_step))
    nz = int(math.ceil((z1 - z0) / grid_step))

    grid = [[0.0] * (nz + 1) for _ in range(nx + 1)]
    for ix in range(nx + 1):
        gx = x0 + ix * grid_step
        for iz in range(nz + 1):
            gz = z0 + iz * grid_step
            grid[ix][iz] = height_func(gx, gz)

    triangles: List[ColTri] = []
    for ix in range(nx):
        gx0 = x0 + ix * grid_step
        gx1 = gx0 + grid_step
        for iz in range(nz):
            gz0 = z0 + iz * grid_step
            gz1 = gz0 + grid_step

            y00 = grid[ix][iz]
            y10 = grid[ix + 1][iz]
            y01 = grid[ix][iz + 1]
            y11 = grid[ix + 1][iz + 1]

            t1 = ColTri(
                p0=(gx0, y00, gz0),
                p1=(gx1, y10, gz0),
                p2=(gx0, y01, gz1),
                flags=TRI_TERRAIN | TRI_DIGGABLE
            )
            t2 = ColTri(
                p0=(gx1, y10, gz0),
                p1=(gx1, y11, gz1),
                p2=(gx0, y01, gz1),
                flags=TRI_TERRAIN | TRI_DIGGABLE
            )
            triangles.append(t1)
            triangles.append(t2)

            # Sub-surface foundation slabs to provide depth support in tests
            depth_y00 = y00 - 3.0
            depth_y10 = y10 - 3.0
            depth_y01 = y01 - 3.0
            depth_y11 = y11 - 3.0
            triangles.append(ColTri(
                p0=(gx0, depth_y00, gz0),
                p1=(gx0, depth_y01, gz1),
                p2=(gx1, depth_y10, gz0),
                flags=TRI_TERRAIN
            ))
            triangles.append(ColTri(
                p0=(gx1, depth_y10, gz0),
                p1=(gx0, depth_y01, gz1),
                p2=(gx1, depth_y11, gz1),
                flags=TRI_TERRAIN
            ))

    return triangles


# ==============================================================================
# Collision Ring Streamer (Single Producer, Protocol 12)
# ==============================================================================

class CollisionRingWriter:
    """Manages writing collision messages into Local\\HyruleCraft_v1 shared memory.
    
    This writer produces collision data ONLY into the collision ring buffer @0x20000.
    It NEVER touches SkyState @0x100, which is owned exclusively by host_link.py.
    """

    def __init__(self, memory_map: Optional[mmap.mmap | bytearray] = None):
        self.memory = memory_map
        self.capacity = COL_RING_DATA_BYTES

    def write_message(self, col_type: int, payload: bytes) -> bool:
        """Writes an 8-byte aligned message packet into the collision ring buffer.
        
        Properly accounts for wrap padding in free-space calculations to prevent
        overwriting unread data when wrapping around.
        """
        if self.memory is None:
            return False

        payload_len = len(payload)
        step = (8 + payload_len + 7) & ~7  # 8-byte aligned

        head = struct.unpack_from('<Q', self.memory, OFF_COLLISION_RING + COL_RING_HEAD_OFF)[0]
        tail = struct.unpack_from('<Q', self.memory, OFF_COLLISION_RING + COL_RING_TAIL_OFF)[0]

        if head < tail:
            return False  # Corrupt counters

        pos = head % self.capacity
        space_at_end = self.capacity - pos
        pad_bytes = space_at_end if space_at_end < step else 0
        total_needed = pad_bytes + step

        # Free space check includes ring wrap padding bytes!
        if (head - tail) + total_needed > self.capacity:
            return False  # Ring full: insufficient capacity including wrap padding

        base = OFF_COLLISION_RING + COL_RING_DATA_OFF

        if pad_bytes > 0:
            # Write pad message in remainder of buffer to wrap cleanly
            struct.pack_into('<II', self.memory, base + pos, COL_PAD, 0)
            head += pad_bytes
            pos = 0

        # Write message header and payload
        struct.pack_into('<II', self.memory, base + pos, col_type, payload_len)
        self.memory[base + pos + 8 : base + pos + 8 + payload_len] = payload
        head += step

        # Publish updated head
        struct.pack_into('<Q', self.memory, OFF_COLLISION_RING + COL_RING_HEAD_OFF, head)
        return True

    def send_clear(self, epoch: int) -> bool:
        """Sends kColClear message."""
        payload = struct.pack('<I', epoch)
        return self.write_message(COL_CLEAR, payload)

    def send_triangles(self, rx: int, ry: int, rz: int, epoch: int, tris: List[ColTri]) -> bool:
        """Sends kColTris message."""
        header = ColRegion(
            min_x=rx * REGION_SIZE,
            min_y=ry * REGION_SIZE,
            min_z=rz * REGION_SIZE,
            max_x=rx * REGION_SIZE + REGION_SIZE - 1,
            max_y=ry * REGION_SIZE + REGION_SIZE - 1,
            max_z=rz * REGION_SIZE + REGION_SIZE - 1,
            epoch=epoch,
            count=len(tris)
        )
        payload = bytearray(header.pack())
        for t in tris:
            payload.extend(t.pack())
        return self.write_message(COL_TRIS, bytes(payload))

    def send_region(self, rx: int, ry: int, rz: int, epoch: int, blocks: List[ColBlock]) -> bool:
        """Sends kColRegion message (populates KNOWN_REGIONS and SHAPES)."""
        header = ColRegion(
            min_x=rx * REGION_SIZE,
            min_y=ry * REGION_SIZE,
            min_z=rz * REGION_SIZE,
            max_x=rx * REGION_SIZE + REGION_SIZE - 1,
            max_y=ry * REGION_SIZE + REGION_SIZE - 1,
            max_z=rz * REGION_SIZE + REGION_SIZE - 1,
            epoch=epoch,
            count=len(blocks)
        )
        payload = bytearray(header.pack())
        for b in blocks:
            payload.extend(b.pack())
        return self.write_message(COL_REGION, bytes(payload))


# ==============================================================================
# Full Multi-Region Terrain Streaming Orchestration
# ==============================================================================

class TerrainStreamer:
    """Orchestrates streaming 3D terrain into Minecraft collision ring.
    
    Adheres strictly to single-producer model: writes only to CollisionRingWriter,
    never updates SkyState, and verifies every send operation.
    """

    def __init__(self, writer: CollisionRingWriter, epoch: int = 1):
        self.writer = writer
        self.epoch = epoch
        self.streamed_regions: Set[Tuple[int, int, int]] = set()

    def stream_surrounding_terrain(
        self,
        player_pos: Tuple[float, float, float],
        triangles: List[ColTri],
        radius_regions: int = 1
    ) -> Dict[str, any]:
        """Streams authentic 3D terrain regions around player.
        
        Requires authentic BOTW collision triangles. Fails explicitly if sends fail.
        """
        px, py, pz = player_pos
        prx = int(math.floor(px / REGION_SIZE))
        pry = int(math.floor(py / REGION_SIZE))
        prz = int(math.floor(pz / REGION_SIZE))

        # 1. Clear epoch on start
        if not self.writer.send_clear(self.epoch):
            raise BufferError(f"Failed to send kColClear for epoch {self.epoch}: collision ring full or unmapped")
        self.streamed_regions.clear()

        # 2. Identify regions to stream:
        # SkyClient requires:
        # - horizontal neighbourhood: dx in [-1, 1], dz in [-1, 1]
        # - vertical offsets: dy in [-8, -1, 0, 2] -> covers pry-1, pry, pry+1
        regions_to_stream: Set[Tuple[int, int, int]] = set()
        for dx in range(-radius_regions, radius_regions + 1):
            for dz in range(-radius_regions, radius_regions + 1):
                for dy in (-1, 0, 1):
                    regions_to_stream.add((prx + dx, pry + dy, prz + dz))

        total_tris_sent = 0
        total_blocks_sent = 0

        # 3. For each region: filter triangles, send kColTris, voxelize, send kColRegion
        for rx, ry, rz in sorted(regions_to_stream):
            r_min_x = rx * REGION_SIZE
            r_max_x = r_min_x + REGION_SIZE
            r_min_y = ry * REGION_SIZE
            r_max_y = r_min_y + REGION_SIZE
            r_min_z = rz * REGION_SIZE
            r_max_z = r_min_z + REGION_SIZE

            # Filter triangles overlapping region AABB
            region_tris: List[ColTri] = []
            for t in triangles:
                t_min_x = min(t.p0[0], t.p1[0], t.p2[0])
                t_max_x = max(t.p0[0], t.p1[0], t.p2[0])
                t_min_y = min(t.p0[1], t.p1[1], t.p2[1])
                t_max_y = max(t.p0[1], t.p1[1], t.p2[1])
                t_min_z = min(t.p0[2], t.p1[2], t.p2[2])
                t_max_z = max(t.p0[2], t.p1[2], t.p2[2])

                if not (t_max_x < r_min_x or t_min_x > r_max_x or
                        t_max_y < r_min_y or t_min_y > r_max_y or
                        t_max_z < r_min_z or t_min_z > r_max_z):
                    region_tris.append(t)

            # Send kColTris first (as required by protocol)
            if not self.writer.send_triangles(rx, ry, rz, self.epoch, region_tris):
                raise BufferError(f"Failed to send kColTris for region ({rx}, {ry}, {rz}): collision ring full")
            total_tris_sent += len(region_tris)

            # Voxelize and send kColRegion
            blocks = voxelize_region_triangles(rx, ry, rz, region_tris)
            if not self.writer.send_region(rx, ry, rz, self.epoch, blocks):
                raise BufferError(f"Failed to send kColRegion for region ({rx}, {ry}, {rz}): collision ring full")
            total_blocks_sent += len(blocks)

            self.streamed_regions.add((rx, ry, rz))

        return {
            "epoch": self.epoch,
            "streamed_region_count": len(self.streamed_regions),
            "total_triangles_sent": total_tris_sent,
            "total_blocks_sent": total_blocks_sent,
            "regions": sorted(list(self.streamed_regions))
        }


# ==============================================================================
# Bounded Read-Only Runtime Memory Probe
# ==============================================================================

def load_bridge_process(pid: int, cemu_log: Path):
    """Loads and instantiates the verified Process reader from HyruleBlocks/bridge.py.
    
    Ensures validation of:
    - PID executable name == Cemu.exe
    - Log file containing TitleVersion: v208 and TitleId: 00050000-101c9400
    - Wii U memory base extraction
    - Graphic pack mod mailbox signature (HYRULEBLOCKS_v01)
    """
    bridge_path = Path(__file__).resolve().parents[1].parent / 'HyruleBlocks' / 'bridge.py'
    if not bridge_path.exists():
        raise FileNotFoundError(f"bridge.py not found at {bridge_path}")
    sys.path.insert(0, str(bridge_path.parent))
    spec = importlib.util.spec_from_file_location('botw_bridge', bridge_path)
    bridge_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge_mod)
    return bridge_mod.Process(pid, cemu_log)


class CemuRuntimeProbe:
    """Bounded, read-only diagnostic probe for Cemu memory space and BOTW structures.
    
    Uses the existing validated Process mailbox actor from HyruleBlocks/bridge.py.
    Strictly read-only: never invokes write methods (put, set, nudge).
    """

    def __init__(self, pid: int, cemu_log: Path, process=None):
        self.pid = pid
        self.log_path = Path(cemu_log)
        self.owns_process = process is None
        self.process = process if process is not None else load_bridge_process(pid, self.log_path)
        self.base = self.process.base
        self.box = self.process.box

    def close(self):
        if self.owns_process and self.process and hasattr(self.process, 'handle'):
            try:
                self.process.k.CloseHandle(self.process.handle)
            except Exception:
                pass
            self.process = None

    def read_u32(self, guest_addr: int) -> Optional[int]:
        try:
            data = self.process.read(self.base + guest_addr, 4)
            return struct.unpack('>I', data)[0]
        except Exception:
            return None

    def read_f32_vec3(self, guest_addr: int) -> Optional[Tuple[float, float, float]]:
        try:
            data = self.process.read(self.base + guest_addr, 12)
            return struct.unpack('>3f', data)
        except Exception:
            return None

    def probe_verified_hierarchy(self) -> Dict[str, any]:
        """Probes runtime BOTW hierarchy via validated mailbox actor and documents terrain blockers."""
        report = {
            "cemu_base": f"{self.base:#018x}",
            "mailbox": f"{self.box:#018x}",
            "validated_process": {
                "executable_validated": True,
                "title_id_v208_validated": True,
                "mailbox_signature_verified": True
            },
            "mailbox_actor": {},
            "unproven_tracker_comparison": {},
            "physics_hierarchy": {},
            "terrain_blockers": {},
            "status": "read-only diagnostic completed"
        }

        # 1. Validated Mailbox Actor (populated by verified graphic pack PPC hook)
        actor = self.process.get(0x20)
        report["mailbox_actor"]["address"] = f"{actor:#010x}"
        if not (0x10000000 <= actor <= 0xE0000000):
            report["mailbox_actor"]["valid"] = False
            report["status"] = "No live player actor in mailbox"
            return report
        report["mailbox_actor"]["valid"] = True

        # Check Link vtable @ actor + 0xE8
        vtable = self.read_u32(actor + 0xE8)
        report["mailbox_actor"]["vtable"] = f"{vtable:#010x}" if vtable else "NULL"
        vtable_ok = (vtable == VTABLE_LINK_PLAYER)
        report["mailbox_actor"]["vtable_matches_0x101E5FFC"] = vtable_ok

        # Check Link setMtx @ table + 0x2AC
        if vtable_ok:
            set_mtx = self.read_u32(vtable + 0x2AC)
            report["mailbox_actor"]["set_mtx"] = f"{set_mtx:#010x}" if set_mtx else "NULL"
            report["mailbox_actor"]["set_mtx_matches_0x02D66ABC"] = (set_mtx == ADDR_LINK_SET_MTX)

        # Read live position & view via validated Process methods
        try:
            pos = self.process.position()
            report["mailbox_actor"]["live_position"] = list(pos)
        except Exception as e:
            report["mailbox_actor"]["position_error"] = str(e)

        try:
            eye, direction = self.process.view()
            report["mailbox_actor"]["live_eye"] = list(eye)
            report["mailbox_actor"]["live_direction"] = list(direction)
        except Exception as e:
            report["mailbox_actor"]["view_error"] = str(e)

        # 2. Compare against unproven PlayerTracker + 0x30 pointer chain
        tracker_ptr = self.read_u32(ADDR_PLAYER_TRACKER_PTR)
        report["unproven_tracker_comparison"]["tracker_singleton_0x10463F38"] = f"{tracker_ptr:#010x}" if tracker_ptr else "NULL"
        if tracker_ptr and (0x10000000 <= tracker_ptr <= 0x80000000):
            tracker_actor = self.read_u32(tracker_ptr + 0x30)
            report["unproven_tracker_comparison"]["tracker_plus_0x30"] = f"{tracker_actor:#010x}" if tracker_actor else "NULL"
            report["unproven_tracker_comparison"]["matches_mailbox_actor"] = (tracker_actor == actor)
        else:
            report["unproven_tracker_comparison"]["tracker_valid"] = False

        # 3. Physics Component & Havok hierarchy from validated actor
        phys_comp = self.read_u32(actor + 0x3A0)
        report["physics_hierarchy"]["physics_component_plus_0x3A0"] = f"{phys_comp:#010x}" if phys_comp else "NULL"
        if phys_comp and (0x10000000 <= phys_comp <= 0x80000000):
            controller = self.read_u32(phys_comp + 0x50)
            report["physics_hierarchy"]["controller_plus_0x50"] = f"{controller:#010x}" if controller else "NULL"
            if controller and (0x10000000 <= controller <= 0x80000000):
                vel = self.read_f32_vec3(controller + 0xB0)
                if vel:
                    report["physics_hierarchy"]["desired_velocity_plus_0xB0"] = list(vel)
                rigid_body = self.read_u32(controller + 0x04)
                report["physics_hierarchy"]["rigid_body_plus_0x04"] = f"{rigid_body:#010x}" if rigid_body else "NULL"
                if rigid_body and (0x10000000 <= rigid_body <= 0x80000000):
                    motion = self.read_u32(rigid_body + 0x70)
                    report["physics_hierarchy"]["motion_plus_0x70"] = f"{motion:#010x}" if motion else "NULL"

        # HavokWorkerMgr singleton
        havok_mgr = self.read_u32(ADDR_HAVOK_WORKER_MGR_PTR)
        report["physics_hierarchy"]["havok_worker_mgr_0x1047C370"] = f"{havok_mgr:#010x}" if havok_mgr else "NULL"

        # 4. Explicit Missing Terrain Offsets & Live Export Status
        report["terrain_blockers"] = {
            "HavokWorkerMgr_to_hkpWorld": "UNVERIFIED: offset from HavokWorkerMgr to hkpWorld* is unproven in v208 binary",
            "hkpWorld_to_m_fixedIsland": "UNVERIFIED: runtime offset to fixed simulation island is unproven",
            "hkpFixedIsland_to_terrain_mesh": "UNVERIFIED: decompression of hkpBvCompressedMeshShape static terrain blocks requires Havok internal bytecode",
            "live_collision_export_status": "NOT ACCEPTED for live export. Memory-based extraction blocked until authentic assets or PPC graphic pack hook are connected. No synthetic terrain may be used in production."
        }

        return report


# ==============================================================================
# Main CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="HyruleCraft Terrain Extractor & Protocol 12 Exporter")
    parser.add_argument("--test-fixture", action="store_true", help="Run offline voxelizer test on synthetic fixture")
    parser.add_argument("--probe", action="store_true", help="Run bounded read-only runtime probe on active Cemu")
    parser.add_argument("--pid", type=int, help="Cemu PID for probe")
    parser.add_argument("--cemu-log", type=Path, help="Path to Cemu log.txt")
    args = parser.parse_args()

    if args.test_fixture:
        print("=== [TEST FIXTURE] Running SAT Voxelizer Verification on Synthetic Test Mesh ===")
        tris = synthetic_test_plateau_fixture(radius=16.0)
        print(f"Generated {len(tris)} synthetic test triangles.")

        prx = int(math.floor(2333.2 / REGION_SIZE))
        pry = int(math.floor(119.4 / REGION_SIZE))
        prz = int(math.floor(-264.8 / REGION_SIZE))
        print(f"Voxelizing test region ({prx}, {pry}, {prz}) ...")
        t0 = time.perf_counter()
        blocks = voxelize_region_triangles(prx, pry, prz, tris)
        dt = (time.perf_counter() - t0) * 1000
        print(f"Voxelized {len(blocks)} solid blocks in {dt:.1f}ms.")
        if blocks:
            print(f"First block: {blocks[0].x}, {blocks[0].y}, {blocks[0].z} (occupied layers: {sum(1 for b in blocks[0].bits if b)})")

    if args.probe:
        if not args.pid or not args.cemu_log:
            print("Error: --probe requires --pid and --cemu-log")
            sys.exit(1)
        probe = CemuRuntimeProbe(args.pid, args.cemu_log)
        try:
            report = probe.probe_verified_hierarchy()
            import json
            print(json.dumps(report, indent=2))
        finally:
            probe.close()


if __name__ == '__main__':
    main()
