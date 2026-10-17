$ErrorActionPreference='Stop'
$record=Join-Path (Split-Path $PSScriptRoot) 'cdc-progress\health-final-technical-closeout-20261017\processes.json'
if(-not(Test-Path -LiteralPath $record)){return}
$state=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
if($state.workspace -ne $PSScriptRoot){throw 'Workspace ownership mismatch'}
foreach($row in $state.processes){$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)";if($proc -and ($proc.CommandLine -ne $row.commandLine -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks)){throw 'Process identity changed; preserved'}}
foreach($row in @($state.processes|Sort-Object @{Expression={if($_.role -in @('owned-next-child','owned-console-helper')){0}else{1}}})){
 $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)"
 if($proc){
  if($proc.CommandLine -ne $row.commandLine -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks){throw 'Process identity changed before stop; preserved'}
  Stop-Process -Id $row.pid
 }
}
Write-Output 'Only this isolated final health delivery processes stopped.'
