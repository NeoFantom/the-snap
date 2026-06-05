# Platforms & cross-VM recipes

Both the **source** (machine being wiped) and the **reference** (machine that
already has copies) can be Windows, macOS, Linux, or WSL. The pipeline only
ever moves *TSVs and hashes*, never files-just-to-compare, so the golden rule is:

> **Index each tree on its own native OS, then compare the TSVs.**
> Don't walk a tree across a VM / mount boundary — it's slow and loses mtime.

Matching is by basename (+ size/hash), so a source indexed as `C:\Users\me\x`
reconciles with a reference walked as `/mnt/c/Users/me/x` automatically. The
path *style* on each side is irrelevant.

## Indexers

| Tree | Tool | How |
|---|---|---|
| Windows (local or remote) | `index-remote.ps1` | over ssh, or `powershell.exe -File` from WSL — no Python needed on Windows |
| macOS / Linux / WSL, local | `index-local.py` | reads `config.json` (`--side reference` / `source`) |
| macOS / Linux / WSL, remote | `index-local.py` | pipe over ssh: `ssh host python3 - --roots /a /b < scripts/index-local.py` |

`index-local.py` in `--roots` mode is fully self-contained (no `config.json`,
no imports beyond the stdlib), which is what makes the ssh-pipe form work.

## WSL & cross-VM

WSL2 distros are real VMs; `/mnt/c` is a `drvfs` mount onto the Windows host;
other distros appear over `9p`. Walking those from the "wrong" side is slow and
mtime-lossy. `index-local.py` prints a stderr warning if a root sits on a
`drvfs`/`9p`/`cifs` mount. Use these instead:

- **WSL → its own Windows host** (most common). Don't ssh, don't walk `/mnt/c`.
  Run the native Windows indexer directly from WSL:
  ```bash
  powershell.exe -NoProfile -File scripts/index-remote.ps1 > index/source.tsv
  ```
- **WSL → another WSL2 distro.** Index inside that distro natively:
  ```bash
  wsl.exe -d <distro> python3 - --roots /home < scripts/index-local.py > index/source.tsv
  ```
  (or ssh into it if it runs sshd).
- **Windows → a WSL2 distro's files.** Index inside the distro; don't walk
  `\\wsl.localhost\<distro>\...` from Windows.
- **Generic remote (mac/linux over LAN / Tailscale).** ssh + `index-local.py`
  as in the table above.

## Copy step per source OS

- **Windows source:** `tar`-over-ssh with the file list converted to GBK
  (`iconv -t GBK`) — see SKILL.md step 7. Windows 10+ ships `bsdtar`.
- **unix source:** `rsync` is simpler and UTF-8-clean:
  ```bash
  rsync -a --files-from=index/scattered-posix.list user@host:/ "$LANDED_ROOT"/
  ```

`copy-scattered.py` emits one list per root: `scattered-<DRIVE>.list` for
Windows drives, `scattered-posix.list` for a POSIX source.
