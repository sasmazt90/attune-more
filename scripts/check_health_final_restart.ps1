$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$out=Join-Path (Split-Path $root) 'cdc-progress\health-final-technical-closeout-20261017'
$record=Join-Path $out 'processes.json'
$before=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
& (Join-Path $root 'Start-Health-Final.ps1') -NoBrowser
$reused=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
if(($before.processes|ConvertTo-Json -Compress) -ne ($reused.processes|ConvertTo-Json -Compress)){throw 'Idempotent start changed owners'}
& (Join-Path $root 'Stop-Health-Final.ps1')
foreach($row in $before.processes){$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)";if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$row.startedUTC).ToUniversalTime().Ticks){throw 'Owned old process remains'}}
& (Join-Path $root 'Start-Health-Final.ps1') -NoBrowser
$after=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
if($after.BUILD_ID -ne $before.BUILD_ID){throw 'Restart changed build'}
@{BUILD_ID=$after.BUILD_ID;idempotentStartVerified=$true;oldExactOwnersExited=$true;before=$before.processes;after=$after.processes;workspace=$root;physicalUserAcceptance=$false}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $out 'restart-proof.tmp') -Encoding utf8
Move-Item -LiteralPath (Join-Path $out 'restart-proof.tmp') -Destination (Join-Path $out 'restart-proof.json') -Force
Write-Output 'PASS exact owned stop/restart, same build'
