"""_hash.py — sha256 with an (path, size, mtime) cache.

Layer-2 of the comparison only hashes small files whose (name, size) already
matched on the other side (see METHODOLOGY 2.3). Re-runs are cheap because we
cache by (path, size, mtime): if none changed, the file is not re-read.

The cache is a plain JSON dict {path: [size, mtime, sha256]}. Hashing always
happens on the machine that owns the file — this module is for the LOCAL
(reference) side; the remote source side hashes natively via Get-FileHash /
sha256sum and ships back path<TAB>hash (see hash-confirm.py).
"""
import hashlib
import json
import os

_BUF = 1 << 20  # 1 MiB read buffer


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_BUF), b""):
            h.update(chunk)
    return h.hexdigest()


class HashCache:
    """Memoize sha256 by (path, size, mtime)."""

    def __init__(self, cache_path):
        self.path = cache_path
        self.data = {}
        if cache_path and os.path.exists(cache_path):
            try:
                self.data = json.load(open(cache_path, encoding="utf-8"))
            except (ValueError, OSError):
                self.data = {}

    def get(self, path):
        """sha256 of a local file, using/refreshing the cache. None on error."""
        try:
            st = os.stat(path)
        except OSError:
            return None
        size, mtime = st.st_size, int(st.st_mtime)
        hit = self.data.get(path)
        if hit and hit[0] == size and hit[1] == mtime:
            return hit[2]
        try:
            digest = file_sha256(path)
        except OSError:
            return None
        self.data[path] = [size, mtime, digest]
        return digest

    def save(self):
        if not self.path:
            return
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        json.dump(self.data, open(self.path, "w", encoding="utf-8"))
