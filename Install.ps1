param([string]$GameDir)
. (Join-Path $PSScriptRoot 'Common.ps1')
$game = Resolve-GameDirectory $GameDir
Assert-GameClosed $game
$already = $true
foreach ($file in $Manifest.files) {
    $digest = Get-FileDigest (Join-Path $game $file.path)
    if ($digest -ne $file.target_sha256) { $already = $false }
    if ($digest -ne $file.source_sha256 -and $digest -ne $file.target_sha256) { throw ('Неподдерживаемая версия или изменённый файл: ' + $file.path + '. Нужна Steam-сборка 23449904.') }
}
if ($already) { Write-Host 'Русификатор уже установлен. Проверка файлов пройдена.'; exit 0 }
$backup = Join-Path $game '.freezer-ru-backup-23449904'
$stageRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$stage = Join-Path $stageRoot ('freezer-ru-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -Force | Out-Null
try {
    foreach ($file in $Manifest.files) {
        $original = Join-Path $game $file.path
        $saved = Join-Path $backup $file.path
        if (Test-Path -LiteralPath $saved) {
            if ((Get-FileDigest $saved) -ne $file.source_sha256) { throw ('Повреждена резервная копия: ' + $file.path) }
        } else {
            if ((Get-FileDigest $original) -ne $file.source_sha256) { throw ('Нет оригинальной резервной копии: ' + $file.path) }
            New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
            Copy-Item -LiteralPath $original -Destination $saved
        }
        $output = Join-Path $stage $file.path
        New-Item -ItemType Directory -Path (Split-Path -Parent $output) -Force | Out-Null
        & (Join-Path $PSScriptRoot 'tools\xdelta3.exe') -d -s $saved (Join-Path $PSScriptRoot $file.patch) $output
        if ($LASTEXITCODE -ne 0) { throw ('Не удалось применить патч: ' + $file.path) }
        if ((Get-FileDigest $output) -ne $file.target_sha256) { throw ('Ошибка проверки результата: ' + $file.path) }
    }
    try {
        foreach ($file in $Manifest.files) { Copy-Item -LiteralPath (Join-Path $stage $file.path) -Destination (Join-Path $game $file.path) -Force }
    } catch {
        foreach ($file in $Manifest.files) { Copy-Item -LiteralPath (Join-Path $backup $file.path) -Destination (Join-Path $game $file.path) -Force }
        throw
    }
    Write-Host 'Русификатор установлен. В настройках выберите Русский (бывший English).'
    Write-Host 'Сохранения не изменены. Для удаления запустите Uninstall.cmd.'
} finally {
    $resolvedStage = [IO.Path]::GetFullPath($stage)
    $prefix = $stageRoot.TrimEnd('\') + '\freezer-ru-'
    if ($resolvedStage.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedStage)) { Remove-Item -LiteralPath $resolvedStage -Recurse -Force }
}
