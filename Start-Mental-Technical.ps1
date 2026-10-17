param([switch]$NoBrowser,[switch]$Dev)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$out=Join-Path (Split-Path $root) 'cdc-progress\mental-technical-closeout-20261017'
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
if(@(Get-NetTCPConnection -LocalPort 3307,8307 -State Listen -ErrorAction SilentlyContinue).Count){throw 'Isolated port already in use; do not replace its owner. Use the verified stop script if it is this delivery.'}
$keys=@('ATTUNE_LOAD_LOCAL_ENV','ATTUNE_TRUSTED_ORIGINS','NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT','NEXT_TELEMETRY_DISABLED','OPENAI_API_KEY');$saved=@{}
foreach($key in $keys){$saved[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
$rows=@()
try{
 $env:ATTUNE_LOAD_LOCAL_ENV='0';$env:ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3307';$env:NEXT_PUBLIC_ATTUNE_LOCAL_API_PORT='8307';$env:NEXT_TELEMETRY_DISABLED='1'
 foreach($port in @(8307,3307)){
  if($port -eq 8307){$exe=$python;$args=@('-u',('"'+(Join-Path $root 'scripts\mental-technical-api.py')+'"'));$cwd=$root}
  else{$env:OPENAI_API_KEY=$null;$exe=$node;$args=@(('"'+(Join-Path $root 'node_modules\next\dist\bin\next')+'"'),$(if($Dev){'dev'}else{'start'}),'--hostname','127.0.0.1','-p','3307');$cwd=Join-Path $root 'apps\vehicle-app'}
  $child=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $out "server-$port.log") -RedirectStandardError (Join-Path $out "server-$port.err.log")
  Start-Sleep -Milliseconds 400
  $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($child.Id)"
  if(-not $proc){throw "Isolated server $port exited"}
  $rows+=@{pid=$child.Id;startedUTC=$proc.CreationDate.ToUniversalTime().ToString('o');commandLine=$proc.CommandLine;role="root-$port"}
  @{workspace=$root;dev=[bool]$Dev;processes=$rows}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath "$record.tmp" -Encoding utf8
  Move-Item -LiteralPath "$record.tmp" -Destination $record -Force
 }
 $ready=$false
 for($attempt=0;$attempt -lt 60;$attempt++){
  try{$api=Invoke-WebRequest 'http://127.0.0.1:8307/api/vehicle/state' -UseBasicParsing;$web=Invoke-WebRequest 'http://127.0.0.1:3307/mental' -UseBasicParsing;if($api.StatusCode -eq 200 -and $web.StatusCode -eq 200){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 500
 }
 foreach($parent in @($rows)){
  foreach($proc in Get-CimInstance Win32_Process -Filter "ParentProcessId=$($parent.pid)"){
   $rows+=@{pid=$proc.ProcessId;startedUTC=$proc.CreationDate.ToUniversalTime().ToString('o');commandLine=$proc.CommandLine;role='owned-next-child';parentPid=$parent.pid}
  }
 }
 @{workspace=$root;dev=[bool]$Dev;processes=$rows}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath "$record.tmp" -Encoding utf8
 Move-Item -LiteralPath "$record.tmp" -Destination $record -Force
 if(-not $ready){throw 'Isolated server readiness failed; exact owned processes are recorded.'}
 Write-Output 'Isolated Ruh Sağlığı: http://127.0.0.1:3307/mental'
 if(-not $NoBrowser){
  $chrome=Join-Path $env:ProgramFiles 'Google\Chrome\Application\chrome.exe'
  if(-not(Test-Path -LiteralPath $chrome)){throw 'Chrome missing; open the isolated URL with a separate test profile.'}
  # A dedicated profile never reads or writes the ordinary user's history.
  Start-Process -FilePath $chrome -ArgumentList @(('--user-data-dir="'+(Join-Path $out 'browser-profile')+'"'),'--new-window','http://127.0.0.1:3307/mental')
 }
}finally{foreach($key in $keys){[Environment]::SetEnvironmentVariable($key,$saved[$key],'Process')}}
