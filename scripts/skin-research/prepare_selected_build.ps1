param([string]$BuildName = 'skin-selected-build-20261011-v2', [switch]$SnapshotOnly)
$ErrorActionPreference = 'Stop'
if ($BuildName -notmatch '^skin-[a-z0-9-]+$') { throw 'Invalid staging directory name.' }
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$stageRoot = Join-Path $taskRoot ('.runtime/' + $BuildName)
if (Test-Path -LiteralPath $stageRoot) { throw 'Existing staging build is preserved; inspect it instead of replacing it.' }
New-Item -ItemType Directory -Path $stageRoot | Out-Null
$files = @(& git -C $taskRoot ls-files apps/vehicle-app packages shared package.json package-lock.json)
$receipt = @{}
foreach ($relative in $files) {
    $sourcePath = Join-Path $taskRoot $relative
    $targetPath = [IO.Path]::GetFullPath((Join-Path $stageRoot $relative))
    if (-not $targetPath.StartsWith($stageRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Staging target escapes workspace.' }
    New-Item -ItemType Directory -Path (Split-Path -Parent $targetPath) -Force | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $targetPath
    $receipt[$relative] = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
$receipt | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $stageRoot 'source-receipt.json') -Encoding utf8
$rootDependencies = Join-Path $taskRoot 'node_modules'
New-Item -ItemType Junction -Path (Join-Path $stageRoot 'node_modules') -Target $rootDependencies | Out-Null
$appDependencies = Join-Path $taskRoot 'apps/vehicle-app/node_modules'
if (-not (Test-Path -LiteralPath $appDependencies)) { $appDependencies = $rootDependencies }
New-Item -ItemType Junction -Path (Join-Path $stageRoot 'apps/vehicle-app/node_modules') -Target $appDependencies | Out-Null
if ($SnapshotOnly) { Write-Output 'Frozen build source prepared; compilation has not run.'; return }
Push-Location -LiteralPath (Join-Path $stageRoot 'apps/vehicle-app')
try {
    & node (Join-Path $taskRoot 'node_modules/next/dist/bin/next') build .
    if ($LASTEXITCODE -ne 0) { throw 'Staged build failed; normal launcher build remains preserved.' }
} finally { Pop-Location }
