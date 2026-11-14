param([string]$GameDir)
. (Join-Path $PSScriptRoot 'Common.ps1')
$game = Resolve-GameDirectory $GameDir
Assert-GameClosed $game
$backup = Join-Path $game '.freezer-ru-backup-23449904'
foreach ($file in $Manifest.files) {
    if ((Get-FileDigest (Join-Path $backup $file.path)) -ne $file.source_sha256) { throw ('Нет исправной резервной копии: ' + $file.path) }
    $current = Get-FileDigest (Join-Path $game $file.path)
    if ($current -ne $file.source_sha256 -and $current -ne $file.target_sha256) { throw ('Файл изменён после установки. Автоматическое восстановление отменено: ' + $file.path) }
}
foreach ($file in $Manifest.files) { Copy-Item -LiteralPath (Join-Path $backup $file.path) -Destination (Join-Path $game $file.path) -Force }
Write-Host 'Оригинальные файлы восстановлены. Сохранения не изменены.'
