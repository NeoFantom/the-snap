# apps-remote.ps1 — list installed apps from the registry Uninstall keys.
# Run on the source machine (Windows). Output TSV: <DisplayName>\t<Version>\t<InstallLocation>
#
# Usage from a Unix host:
#   B64=$(iconv -t UTF-16LE < apps-remote.ps1 | base64 -w0)
#   ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $B64" > source.apps.tsv

$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$paths = @(
  'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
  'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
)

$apps = @{}
foreach ($p in $paths) {
  Get-ItemProperty $p -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.DisplayName -and -not $_.SystemComponent) {
      $apps[$_.DisplayName] = ("{0}`t{1}" -f $_.DisplayVersion, $_.InstallLocation)
    }
  }
}
foreach ($k in ($apps.Keys | Sort-Object)) {
  "{0}`t{1}" -f $k, $apps[$k]
}
