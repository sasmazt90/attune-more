$ErrorActionPreference='Stop'
$record=Join-Path (Split-Path $PSScriptRoot) 'cdc-progress\hearing-technical-closeout-20261017\processes.json'
if(-not(Test-Path -LiteralPath $record)){return}
$state=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
if($state.workspace -ne $PSScriptRoot){throw 'Workspace ownership mismatch'}
foreach($row in $state.processes){$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)";if($proc -and ($proc.CommandLine -ne $row.commandLine -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks)){throw 'Process identity changed; preserved'}}
foreach($row in @($state.processes|Sort-Object @{Expression={if($_.role -eq 'owned-next-child'){0}else{1}}})){
 $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)"
 if($proc){
  if($proc.CommandLine -ne $row.commandLine -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks){throw 'Process identity changed before stop; preserved'}
  Stop-Process -Id $row.pid
 }
}
Write-Output 'Only this isolated health UI delivery processes stopped.'
