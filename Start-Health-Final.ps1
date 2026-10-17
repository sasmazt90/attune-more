param([switch]$NoBrowser,[switch]$Dev)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$out=Join-Path (Split-Path $root) 'cdc-progress\health-final-technical-closeout-20261017'
$record=Join-Path $out 'processes.json'
$python='C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe'
$node='C:\nvm4w\nodejs\node.exe'
foreach($asset in (Get-Content -LiteralPath (Join-Path $out 'local-assets.json') -Raw | ConvertFrom-Json)){
 if((Get-FileHash -LiteralPath (Join-Path $root $asset.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset.sha256){throw 'Local model or existing guidance bank identity changed; preserved'}
}
if(-not $Dev){
 $build=Get-Content -LiteralPath (Join-Path $out 'build-receipt.json') -Raw | ConvertFrom-Json
 if((Get-Content -LiteralPath (Join-Path $root 'apps\vehicle-app\.next\BUILD_ID') -Raw).Trim() -ne $build.BUILD_ID){throw 'Isolated build identity mismatch'}
 foreach($file in $build.files){if((Get-FileHash -LiteralPath (Join-Path $root $file.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256){throw 'Isolated build/source hash mismatch'}}
}
$deliveredBuild=if($Dev){'dev'}else{$build.BUILD_ID}
function Open-IsolatedHealthUI {
 if($NoBrowser){return}
 $chrome=Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
 if(-not(Test-Path -LiteralPath $chrome)){throw 'Chrome missing; open the isolated URL with a separate test profile.'}
 Start-Process -FilePath $chrome -ArgumentList @(('--user-data-dir="'+(Join-Path $out 'browser-profile')+'"'),'--new-window','http://127.0.0.1:3311/')
}
$listeners=@(Get-NetTCPConnection -LocalPort 3311,8311 -State Listen -ErrorAction SilentlyContinue)
if($listeners.Count){
 if(-not(Test-Path -LiteralPath $record)){throw 'Isolated port occupied by an unverified owner; preserved'}
 $prior=Get-Content -LiteralPath $record -Raw|ConvertFrom-Json
 if($prior.workspace -ne $root -or $prior.dev -ne [bool]$Dev -or $prior.BUILD_ID -ne $deliveredBuild){throw 'Existing runtime identity differs; preserved'}
 foreach($row in $prior.processes){$proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($row.pid)";if(-not $proc -or $proc.CommandLine -ne $row.commandLine -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$row.startedUTC).ToUniversalTime().Ticks){throw 'Existing process identity differs; preserved'}}
 if(@($listeners|Where-Object{$_.OwningProcess -notin @($prior.processes.pid)}).Count){throw 'Port belongs to another process; preserved'}
 $api=Invoke-WebRequest 'http://127.0.0.1:8311/api/vehicle/state' -UseBasicParsing
 $web=Invoke-WebRequest 'http://127.0.0.1:3311/' -UseBasicParsing
 if($api.StatusCode -ne 200 -or $web.StatusCode -ne 200){throw 'Owned runtime is not ready'}
 Write-Output 'Verified existing isolated health UI: http://127.0.0.1:3311/'
 Open-IsolatedHealthUI
 return
}
$keys=@('ATTUNE_LOAD_LOCAL_ENV','ATTUNE_TRUSTED_ORIGINS','NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT','NEXT_TELEMETRY_DISABLED','OPENAI_API_KEY','NEXT_PUBLIC_ATTUNE_ACNE_V5','NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT');$saved=@{}
foreach($key in $keys){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
$rows=@()
try{
 $env:ATTUNE_LOAD_LOCAL_ENV='0';$env:ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3311';$env:NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8311';$env:NEXT_TELEMETRY_DISABLED='1';$env:NEXT_PUBLIC_ATTUNE_ACNE_V5='1';$env:NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8311'
 foreach($port in @(8311,3311)){
  if($port -eq 8311){$exe=$python;$args=@('-u',('"'+(Join-Path $root 'scripts\health-final-api.py')+'"'));$cwd=$root}
  else{$env:OPENAI_API_KEY=$null;$exe=$node;$args=@(('"'+(Join-Path $root 'node_modules\next\dist\bin\next')+'"'),$(if($Dev){'dev'}else{'start'}),'--hostname','127.0.0.1','-p','3311');$cwd=Join-Path $root 'apps\vehicle-app'}
  $child=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $out "server-$port.log") -RedirectStandardError (Join-Path $out "server-$port.err.log")
  Start-Sleep -Milliseconds 400
  $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($child.Id)"
  if(-not $proc){throw "Isolated server $port exited"}
  $rows+=@{pid=$child.Id;startedUTC=$proc.CreationDate.ToUniversalTime().ToString('o');commandLine=$proc.CommandLine;role="root-$port"}
  @{workspace=$root;dev=[bool]$Dev;BUILD_ID=$deliveredBuild;processes=$rows}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath "$record.tmp" -Encoding utf8
  Move-Item -LiteralPath "$record.tmp" -Destination $record -Force
 }
 $ready=$false
 for($attempt=0;$attempt -lt 60;$attempt++){
  try{$api=Invoke-WebRequest 'http://127.0.0.1:8311/api/vehicle/state' -UseBasicParsing;$web=Invoke-WebRequest 'http://127.0.0.1:3311/' -UseBasicParsing;if($api.StatusCode -eq 200 -and $web.StatusCode -eq 200){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 500
 }
 foreach($parent in @($rows)){
  foreach($proc in Get-CimInstance Win32_Process -Filter "ParentProcessId=$($parent.pid)"){
   $role=if($proc.Name -eq 'conhost.exe'){'owned-console-helper'}else{'owned-next-child'}
   $rows+=@{pid=$proc.ProcessId;startedUTC=$proc.CreationDate.ToUniversalTime().ToString('o');commandLine=$proc.CommandLine;role=$role;parentPid=$parent.pid}
  }
 }
 @{workspace=$root;dev=[bool]$Dev;BUILD_ID=$deliveredBuild;processes=$rows}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath "$record.tmp" -Encoding utf8
 Move-Item -LiteralPath "$record.tmp" -Destination $record -Force
 if(-not $ready){throw 'Isolated server readiness failed; exact owned processes are recorded.'}
 Write-Output 'Isolated Sağlık Merkezi: http://127.0.0.1:3311/'
 Open-IsolatedHealthUI
}finally{foreach($key in $keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}}
