$ErrorActionPreference = 'Stop'
$script:PackageRoot = $PSScriptRoot
$script:Manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
function Resolve-GameDirectory([string]$Requested) {
    if ($Requested) { return [IO.Path]::GetFullPath($Requested) }
    $steam = (Get-ItemProperty 'HKCU:\Software\Valve\Steam' -ErrorAction SilentlyContinue).SteamPath
    $libraries = @($steam)
    if ($steam) {
        $vdf = Join-Path $steam 'steamapps\libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            $content = Get-Content -LiteralPath $vdf -Raw
            foreach ($match in [regex]::Matches($content, '"path"\s+"([^"]+)"')) { $libraries += $match.Groups[1].Value.Replace('\\','\') }
        }
    }
    foreach ($library in ($libraries | Select-Object -Unique)) {
        if (-not $library) { continue }
        $candidate = Join-Path $library 'steamapps\common\How Much for the Body in the Freezer'
        if (Test-Path -LiteralPath (Join-Path $candidate 'How Much for the Body in the Freezer.exe')) { return [IO.Path]::GetFullPath($candidate) }
    }
    throw 'Игра не найдена. Запустите Install.ps1 с параметром -GameDir и путём к игре.'
}
function Get-FileDigest([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Assert-GameClosed([string]$GameDirectory) {
    foreach ($process in Get-Process -Name 'How Much for the Body in the Freezer' -ErrorAction SilentlyContinue) {
        if ($process.Path -and ([IO.Path]::GetDirectoryName($process.Path) -eq $GameDirectory)) { throw 'Закройте игру и повторите запуск.' }
    }
}
