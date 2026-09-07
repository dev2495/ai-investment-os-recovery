"""Project one stored update into a bounded managed Obsidian note."""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
import fcntl

START = '<!-- BEGIN aios-company-update-v1 -->'
END = '<!-- END aios-company-update-v1 -->'


def project_company_note(row: dict) -> dict:
    volume = Path(os.environ.get('AI_OS_SSD_ROOT') or '/Volumes/Devarsh SSD')
    vault = Path(os.environ.get('AI_OS_VAULT_ROOT') or '/Volumes/Devarsh SSD/Obsidian memory ')
    # Deployment accepts the enclosing storage root; Obsidian notes live in
    # its canonical ai memory child. An explicit notes root is also valid.
    if vault.name != 'ai memory':
        vault = vault / 'ai memory'
    if not volume.is_mount() or not vault.is_dir():
        raise RuntimeError('canonical SSD vault unavailable')
    vault.resolve().relative_to(volume.resolve())
    relative = str(row['managed_note_path'])
    if not re.fullmatch(r'00 AI OS/Managed/Company Updates/[0-9a-f]{64}\.md', relative):
        raise ValueError('unexpected managed note path')
    destination = vault / relative
    for parent in [destination, *destination.parents]:
        if parent == vault.parent:
            break
        if parent.is_symlink():
            raise ValueError('symlink in managed note path')
    destination.resolve().relative_to(vault.resolve())
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Directory lock serializes all writers without introducing a replaceable
    # lockfile. Human text outside the bounded block is kept byte-for-byte.
    descriptor = os.open(destination.parent, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        if destination.is_symlink():
            raise ValueError('symlink in managed note path')
        if destination.exists() and destination.stat().st_size > 1_000_000:
            raise ValueError('managed note exceeds size bound')
        previous = destination.read_bytes().decode('utf-8') if destination.exists() else ''
        if previous.count(START) != previous.count(END) or previous.count(START) > 1:
            raise ValueError('ambiguous managed note markers')
        safe = html.escape(json.dumps(row['artifact'], sort_keys=True, indent=2, default=str))
        block = START + '\n<pre>' + safe + '</pre>\n' + END
        if START in previous:
            begin = previous.index(START)
            end = previous.index(END)
            if end < begin:
                raise ValueError('reversed managed note markers')
            body = previous[:begin] + block + previous[end + len(END):]
        else:
            body = previous + ('\n\n' if previous else '') + block + '\n'
        if body != previous:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=destination.parent, delete=False) as temp:
                temp.write(body)
                temp.flush()
                os.fsync(temp.fileno())
                temporary = temp.name
            os.replace(temporary, destination)
        return {'path': relative, 'sha256': hashlib.sha256(body.encode()).hexdigest()}
    finally:
        os.close(descriptor)
