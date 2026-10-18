$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
if($root -ne 'C:\Users\PC\Desktop\AI Workspace\TOGG\attune-cdc-health-final-technical-20261017'){throw 'Wrong workspace'}
$base=Join-Path (Split-Path $root) 'attune-cdc-dental-technical-20261017'
foreach($relative in @('node_modules','apps\vehicle-app\node_modules')){
 $target=Join-Path $root $relative
 $item=Get-Item -LiteralPath $target
 if($item.FullName -ne $target -or $item.LinkType -ne 'Junction' -or $item.Target -ne (Join-Path $base $relative)){throw 'Dependency link ownership mismatch'}
}
& (Join-Path $root 'Stop-Health-Final.ps1')
foreach($relative in @('node_modules','apps\vehicle-app\node_modules')){
 $target=Join-Path $root $relative
 # Delete the verified local junction itself, never recurse into its target.
 Remove-Item -LiteralPath $target -Force
 New-Item -ItemType Directory -Path $target | Out-Null
 $source=Join-Path $base $relative
 & robocopy $source $target /E /XJ /R:0 /W:0 /NFL /NDL /NJH /NJS /NP *> (Join-Path (Split-Path $root) ('cdc-progress\health-final-technical-closeout-20261017\copy-'+($relative -replace '\\','-')+'.log'))
 if($LASTEXITCODE -ge 8){throw 'Private dependency copy failed; source preserved'}
}
New-Item -ItemType Junction -Path (Join-Path $root 'node_modules\vehicle-app') -Target (Join-Path $root 'apps\vehicle-app') | Out-Null
Write-Output 'Private dependencies prepared; protected targets untouched'
