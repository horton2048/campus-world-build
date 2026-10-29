#!/usr/bin/env python3
"""Read-only GLB preflight: stable bytes, SHA, structure, byte limit and metadata.

Does not import, execute author JavaScript, decode images or change the source.
Accessor min/max are LOCAL metadata, never an automatic scale multiplier.
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path


def inspect(path, expected_sha=None, max_mib=20):
    before = path.stat()
    max_bytes = max_mib * 1024 * 1024
    # Reject oversized inputs before loading them, including files replaced during inspection.
    if before.st_size > max_bytes:
        raise ValueError(f'file exceeds configured import byte limit ({max_mib:g} MiB)')
    with path.open('rb') as stream:
        raw = stream.read(int(max_bytes) + 1)
    middle = path.stat()
    if len(raw) > max_bytes or middle.st_size > max_bytes:
        raise ValueError(f'file exceeds configured import byte limit ({max_mib:g} MiB)')
    with path.open('rb') as stream:
        second = stream.read(int(max_bytes) + 1)
    after = path.stat()
    if len(second) > max_bytes:
        raise ValueError(f'file exceeds configured import byte limit ({max_mib:g} MiB)')
    if raw != second or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('source changed during read; retry after generation finishes')
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha and digest.lower() != expected_sha.lower():
        raise ValueError('SHA-256 mismatch; source or selected deployment version changed')
    if len(raw) < 20:
        raise ValueError('too short for a GLB 2.0 container')
    magic, version, declared = struct.unpack_from('<4sII', raw)
    if magic != b'glTF' or version != 2 or declared != len(raw):
        raise ValueError('invalid GLB header/version/declared length')
    chunks = []
    offset = 12
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError('truncated chunk header')
        length, kind = struct.unpack_from('<II', raw, offset)
        offset += 8
        if length % 4 or offset + length > len(raw):
            raise ValueError('invalid chunk alignment or length')
        chunks.append((kind, raw[offset:offset + length]))
        offset += length
    if not chunks or chunks[0][0] != 0x4E4F534A:
        raise ValueError('first chunk must be JSON')
    if sum(kind == 0x4E4F534A for kind, _ in chunks) != 1:
        raise ValueError('GLB must contain one JSON chunk')
    document = json.loads(chunks[0][1].decode('utf-8'))
    if not isinstance(document, dict) or not isinstance(document.get('asset'), dict) or document['asset'].get('version') != '2.0':
        raise ValueError('unsupported glTF asset metadata')
    collections = {}
    for name in ('nodes', 'meshes', 'materials', 'scenes', 'animations', 'skins', 'accessors'):
        value = document.get(name, [])
        if not isinstance(value, list):
            raise ValueError(f'{name} must be an array')
        collections[name] = value
    bounds = []
    for mesh_idx, mesh in enumerate(collections['meshes']):
        if not isinstance(mesh, dict):
            raise ValueError(f'meshes[{mesh_idx}] must be an object')
        primitives = mesh.get('primitives', [])
        if not isinstance(primitives, list):
            raise ValueError(f'meshes[{mesh_idx}].primitives must be an array')
        for primitive_idx, primitive in enumerate(primitives):
            if not isinstance(primitive, dict):
                raise ValueError(f'meshes[{mesh_idx}].primitives[{primitive_idx}] must be an object')
            attributes = primitive.get('attributes', {})
            if not isinstance(attributes, dict):
                raise ValueError(f'meshes[{mesh_idx}].primitives[{primitive_idx}].attributes must be an object')
            accessor_idx = attributes.get('POSITION')
            if accessor_idx is None:
                continue
            accessors = collections['accessors']
            if not isinstance(accessor_idx, int) or isinstance(accessor_idx, bool) or not 0 <= accessor_idx < len(accessors):
                raise ValueError('POSITION references missing accessor')
            accessor = accessors[accessor_idx]
            if not isinstance(accessor, dict):
                raise ValueError(f'accessors[{accessor_idx}] must be an object')
            bounds.append({'mesh': mesh_idx, 'primitive': primitive_idx, 'positionCount': accessor.get('count'),
                           'localMin': accessor.get('min'), 'localMax': accessor.get('max')})
    return {'ok': True, 'path': str(path.resolve()), 'sha256': digest, 'stableRead': True,
            'bytes': len(raw), 'configuredMaxMiB': max_mib,
            'nodes': len(collections['nodes']), 'meshes': len(collections['meshes']),
            'materials': len(collections['materials']), 'scenes': len(collections['scenes']),
            'hasAnimations': bool(collections['animations']), 'hasSkins': bool(collections['skins']),
            'positionAccessors': bounds,
            'verified': 'container metadata and source bytes only',
            'notVerified': ['world-space geometry bounds', 'native import', 'visual orientation and text',
                            'collision', 'scene capacity', 'runtime or mobile play']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--sha256', help='Expected deployment/source SHA-256; mismatch fails')
    parser.add_argument('--max-mib', type=float, default=20,
                        help='Import byte limit from the current editor tool (default: 20 MiB)')
    args = parser.parse_args()
    try:
        if (not math.isfinite(args.max_mib) or args.max_mib <= 0
                or args.max_mib * 1024 * 1024 >= sys.maxsize):
            raise ValueError('--max-mib must be positive and within the platform read limit')
        result = inspect(args.file, args.sha256, args.max_mib)
    except (OSError, ValueError, TypeError, KeyError, struct.error) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
