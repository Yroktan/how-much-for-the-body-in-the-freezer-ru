param([string]$GameDir)
. (Join-Path $PSScriptRoot 'Common.ps1')
$game = Resolve-GameDirectory $GameDir
foreach ($file in $Manifest.files) {
    if ((Get-FileDigest (Join-Path $game $file.path)) -ne $file.target_sha256) { throw ('Проверка не пройдена: ' + $file.path) }
}
Write-Host 'Все файлы русификатора прошли проверку SHA-256.'
