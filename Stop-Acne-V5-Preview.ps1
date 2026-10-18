$ErrorActionPreference='Stop'
$record=Join-Path (Split-Path $PSScriptRoot) 'cdc-progress\acne-v5-consistency-fix-20261017\preview-processes.json'
if(-not(Test-Path -LiteralPath $record)){return}
$state=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
if($state.workspace -ne $PSScriptRoot){throw 'Workspace identity mismatch'}
foreach($row in $state.processes){
 $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)"
 if(-not $proc){continue}
 if($proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks -or $proc.CommandLine -ne $row.commandLine){throw 'Process identity changed; preserved'}
 Stop-Process -Id $row.pid
}
Write-Output 'Only verified preview processes stopped. Normal product was not changed.'
