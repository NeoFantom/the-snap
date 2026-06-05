# apps-extras.ps1 — supplemental app inventory: AppX (UWP / Store) +
# winget + Scoop + Chocolatey. The registry-Uninstall view misses these.
#
# Usage from a Unix host:
#   B64=$(iconv -t UTF-16LE < apps-extras.ps1 | base64 -w0)
#   ssh "$USER@$HOST" "powershell -NoProfile -EncodedCommand $B64" > source.apps-extras.txt

$ProgressPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

"## SECTION: AppX (UWP / Microsoft Store, current user)"
try {
    Get-AppxPackage 2>$null |
        Where-Object { -not $_.IsFramework -and -not $_.IsResourcePackage } |
        Select-Object Name, Version, Publisher |
        Sort-Object Name |
        ForEach-Object { "{0}`t{1}`t{2}" -f $_.Name, $_.Version, $_.Publisher }
} catch { "ERR AppX: $_" }

""
"## SECTION: winget list"
try {
    if (Get-Command winget -EA SilentlyContinue) {
        winget list --accept-source-agreements 2>$null
    } else { "winget not installed" }
} catch { "ERR winget: $_" }

""
"## SECTION: Scoop"
try {
    if (Get-Command scoop -EA SilentlyContinue) { scoop list 2>$null } else { "scoop not installed" }
} catch { "ERR scoop: $_" }

""
"## SECTION: Chocolatey"
try {
    if (Get-Command choco -EA SilentlyContinue) { choco list --local-only 2>$null } else { "choco not installed" }
} catch { "ERR choco: $_" }

# Tip: also run `winget export -o apps.json` on the source — it produces a
# JSON that `winget import` can replay on the new machine (subset of all
# installed apps, only those known to a winget source).
