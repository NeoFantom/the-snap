"""_paths.py — separator-agnostic path helpers.

The pipeline reconciles paths coming from different OSes: Windows sources
emit ``C:\\Users\\me\\x``; mac/linux/WSL sources emit ``/home/me/x``. We never
rely on the running OS's separator — every helper here accepts both ``\\`` and
``/`` so the same TSV row parses identically wherever the script runs.

Match keys are always basename-based, so a file indexed as ``C:\\a\\report.pdf``
on the source and walked as ``/mnt/c/a/report.pdf`` on the reference still
reconcile — this is what lets each machine index itself natively (incl. across
a WSL/VM boundary) and only the TSVs travel.
"""
import re

_SEP = re.compile(r"[\\/]+")
_DRIVE = re.compile(r"^[A-Za-z]:$")


def segments(p):
    """Split a path into non-empty segments, accepting / and \\ alike.

    ``C:\\a\\b`` -> ['C:', 'a', 'b']; ``/a/b`` -> ['a', 'b']; ``a/b`` -> ['a','b'].
    A leading separator does not produce an empty leading segment.
    """
    p = p.strip()
    p = re.sub(r"[\\/]+$", "", p)          # drop trailing separators
    parts = _SEP.split(p)
    if parts and parts[0] == "":           # drop empty from a leading separator
        parts = parts[1:]
    return parts


def basename(p):
    segs = segments(p)
    return segs[-1] if segs else ""


def segs_drive(p):
    """Return the drive segment ('C:') if the path is Windows-drive-rooted."""
    segs = segments(p)
    return segs[0] if segs and _DRIVE.match(segs[0]) else ""


def split_root(p):
    """Return (root, rel) where rel uses forward slashes and drops the root.

    ``C:\\a\\b`` -> ('C:', 'a/b'); ``/a/b/c`` -> ('/', 'a/b/c'); ``a/b`` -> ('', 'a/b').
    """
    segs = segments(p)
    if not segs:
        return ("", "")
    if _DRIVE.match(segs[0]):
        return (segs[0], "/".join(segs[1:]))
    if p[:1] in ("/", "\\"):
        return ("/", "/".join(segs))
    return ("", "/".join(segs))


def top_dir(p, n=3):
    """First n segments, rejoined for human-readable grouping in reports."""
    segs = segments(p)
    head = segs[:n]
    if segs and _DRIVE.match(segs[0]):
        return "\\".join(head)
    prefix = "/" if p[:1] in ("/", "\\") else ""
    return prefix + "/".join(head)


def norm_key(p):
    """Canonical, case-insensitive comparison key: segments joined by '\\',
    lowercased, separator- and leading-slash-agnostic. Used to match
    user-excluded prefixes (from the web UI) against file paths regardless of
    the source OS's path style."""
    return "\\".join(segments(p)).lower()
