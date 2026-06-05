# hash-remote.ps1 — sha256 a list of files on a Windows SOURCE machine.
# Reads file paths from stdin (UTF-8, one per line), emits: <path>\t<sha256 lower>
#
# Used by hash-confirm.py for layer-2 content checks without pulling files
# back over the network. Invoke like the indexer:
#   B64=$(iconv -t UTF-16LE < hash-remote.ps1 | base64 -w0)
#   printf '%s\n' "C:\a.txt" "C:\b.txt" | ssh host "powershell -NoProfile -EncodedCommand $B64"

[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProgressPreference = 'SilentlyContinue'

while ($null -ne ($line = [Console]::In.ReadLine())) {
  $p = $line.Trim()
  if ($p -eq '') { continue }
  try {
    $h = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLower()
    "{0}`t{1}" -f $p, $h
  } catch {
    "{0}`t{1}" -f $p, 'ERROR'
  }
}
