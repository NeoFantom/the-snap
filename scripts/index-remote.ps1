# index-remote.ps1 — full-disk blacklist walker for the SOURCE machine (Windows).
# Emits TSV to stdout: <full path>\t<size bytes>\t<mtime UTC ticks>
#
# Skips junctions/reparse points (avoids re-entering blacklisted regions via
# legacy aliases like All Users -> ProgramData). Skips configured directory
# names anywhere in the tree, and configured roots fully.
#
# Configuration: edit the two arrays below for your machine, OR pass them
# in via the wrapping ssh command (heredoc / -EncodedCommand). The defaults
# are conservative system noise only — review METHODOLOGY.md section 5
# before adding "shared-data roots" like ProgramData / AppData.
#
# Usage from a Unix host:
#   B64=$(iconv -t UTF-16LE < index-remote.ps1 | base64 -w0)
#   ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $B64" > source.tsv

$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Dir names excluded anywhere in the tree (system / noise / deps / build).
# DO NOT blanket-add ProgramData / AppData / Public without auditing first.
$excludeNames = @(
  'Windows','Program Files','Program Files (x86)',
  '$Recycle.Bin','System Volume Information','Recovery','$WinREAgent',
  '$Windows.~BT','$Windows.~WS','PerfLogs','system.sav',
  'OneDriveTemp','Documents and Settings','MSOCache','temp','Temp','tmp',
  'node_modules','.git','__pycache__','.cache',
  'target','dist','build','.gradle','.conda','.venv','venv',
  '.idea','.vscode','.ipynb_checkpoints'
)

# Roots to skip entirely (e.g. already indexed in a prior whitelist pass,
# or handled out-of-band as a bulk tar). Use absolute paths.
$skipFull = @()

# Drives to walk.
$drives = @('C:\', 'D:\')

$exNames = [System.Collections.Generic.HashSet[string]]::new(
  [string[]]$excludeNames, [System.StringComparer]::OrdinalIgnoreCase)
$skip = [System.Collections.Generic.HashSet[string]]::new(
  [string[]]$skipFull, [System.StringComparer]::OrdinalIgnoreCase)

function Walk($dir) {
  $items = Get-ChildItem -LiteralPath $dir -Force -EA SilentlyContinue
  foreach ($it in $items) {
    if ($it.PSIsContainer) {
      if ($it.Attributes -band [IO.FileAttributes]::ReparsePoint) { continue }
      if ($exNames.Contains($it.Name)) { continue }
      if ($skip.Contains($it.FullName)) { continue }
      Walk $it.FullName
    } else {
      "{0}`t{1}`t{2}" -f $it.FullName, $it.Length, $it.LastWriteTimeUtc.Ticks
    }
  }
}

foreach ($root in $drives) { Walk $root }
