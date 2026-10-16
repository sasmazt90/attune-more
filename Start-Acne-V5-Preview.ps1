param([switch]$NoBrowser,[switch]$ValidationTrace)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$progress=Join-Path (Split-Path $root) 'cdc-progress\acne-v5-integration-20261017'
$record=Join-Path $progress 'preview-processes.json'
$python='C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe'
$node='C:\nvm4w\nodejs\node.exe'
$next=(Resolve-Path -LiteralPath (Join-Path $root 'node_modules\next\dist\bin\next')).Path
if(-not(Test-Path -LiteralPath (Join-Path $root 'apps\vehicle-app\.next\BUILD_ID'))){throw 'Preview build is missing. Do not use the normal product launcher.'}
$build=Get-Content -LiteralPath (Join-Path $progress 'build-receipt.json') -Raw | ConvertFrom-Json
if(-not $build.experimentalFlag -or (Get-Content -LiteralPath (Join-Path $root 'apps\vehicle-app\.next\BUILD_ID') -Raw).Trim() -ne $build.BUILD_ID){throw 'Preview build identity mismatch'}
foreach($file in $build.files){if((Get-FileHash -LiteralPath (Join-Path $root $file.path) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file.sha256){throw 'Preview source or bundle changed; rebuild the isolated preview first'}}
$models=Join-Path $root 'services\core-api\models\acne-v5-preview'
$manifest=Get-Content -LiteralPath (Join-Path $models 'manifest.json') -Raw | ConvertFrom-Json
foreach($model in @($manifest.detector,$manifest.verifier)){
 $path=Join-Path $models $model.file
 if((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $model.sha256){throw 'Preview model hash mismatch'}
}
$prior=if(Test-Path -LiteralPath $record){Get-Content -LiteralPath $record -Raw | ConvertFrom-Json}else{$null}
$running=@()
if($prior -and [bool]$prior.validationTrace -ne [bool]$ValidationTrace){
 foreach($row in $prior.processes){if(Get-Process -Id $row.pid -ErrorAction SilentlyContinue){throw 'Stop the verified preview first before changing its validation mode.'}}
}
foreach($port in @(8305,3305)){
 $listeners=@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
 if($listeners.Count){
  $known=@($prior.processes | Where-Object {$_.port -eq $port})
  foreach($listener in $listeners){
   $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
   if($known.Count -ne 1 -or $proc.ProcessId -ne $known[0].pid -or $proc.CreationDate.ToUniversalTime().Ticks -ne ([datetime]$known[0].startedUTC).ToUniversalTime().Ticks -or $proc.CommandLine -ne $known[0].commandLine){throw "Port $port belongs to an unverified process; preserved."}
  }
  $running+=$known[0]
 }
}
$previewEnvKeys=@('ATTUNE_ACNE_V5_MODEL_DIR','ATTUNE_LOAD_LOCAL_ENV','ATTUNE_EXPERIMENTAL_ACNE_V5','ATTUNE_ACNE_V5_VALIDATION','ATTUNE_TRUSTED_ORIGINS','NEXT_PUBLIC_ATTUNE_ACNE_V5','NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT','NEXT_TELEMETRY_DISABLED')
$savedPreviewEnv=@{}
foreach($key in $previewEnvKeys){$savedPreviewEnv[$key]=[Environment]::GetEnvironmentVariable($key,'Process')}
try {
$env:ATTUNE_ACNE_V5_MODEL_DIR=$models
$env:ATTUNE_LOAD_LOCAL_ENV='0'
$env:ATTUNE_EXPERIMENTAL_ACNE_V5='1'
$env:ATTUNE_ACNE_V5_VALIDATION=if($ValidationTrace){'1'}else{'0'}
$env:ATTUNE_TRUSTED_ORIGINS='http://127.0.0.1:3305'
$env:NEXT_PUBLIC_ATTUNE_ACNE_V5='1'
$env:NEXT_PUBLIC_ATTUNE_PREVIEW_API_PORT='8305'
$env:NEXT_TELEMETRY_DISABLED='1'
foreach($port in @(8305,3305)){
 if($running | Where-Object {$_.port -eq $port}){continue}
 if($port -eq 8305){$exe=$python;$args=@('-u',('"'+(Join-Path $root 'scripts\acne-v5-preview-api.py')+'"'));$cwd=$root}
 else{$exe=$node;$args=@(('"'+$next+'"'),'start','--hostname','127.0.0.1','-p','3305');$cwd=Join-Path $root 'apps\vehicle-app'}
 $child=Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $progress "preview-$port.log") -RedirectStandardError (Join-Path $progress "preview-$port.err.log")
 Start-Sleep -Milliseconds 350
 $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$($child.Id)"
 if(-not $proc){throw "Preview $port exited; inspect its local error log"}
 $running+=@{pid=$child.Id;port=$port;startedUTC=$proc.CreationDate.ToUniversalTime().ToString('o');commandLine=$proc.CommandLine;workspace=$cwd}
 @{workspace=$root;processes=@($running);validationTrace=[bool]$ValidationTrace}|ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$record.tmp" -Encoding utf8
 Move-Item -LiteralPath "$record.tmp" -Destination $record -Force
}
$ready=$false
for($attempt=0;$attempt -lt 40;$attempt++){
 try{$config=Invoke-RestMethod 'http://127.0.0.1:8305/api/local-health/skin/acne-v5-config';$web=Invoke-WebRequest 'http://127.0.0.1:3305/skin' -UseBasicParsing;if($config.enabled -and $web.StatusCode -eq 200){$ready=$true;break}}catch{}
 Start-Sleep -Milliseconds 500
}
if(-not $ready){throw 'Preview readiness failed; own process identities and logs are recorded.'}
Write-Output 'Experimental preview: http://127.0.0.1:3305/skin (no history writes, normal product unchanged)'
if(-not $NoBrowser){Start-Process 'http://127.0.0.1:3305/skin'}

} finally {
 foreach($key in $previewEnvKeys){if($null -eq $savedPreviewEnv[$key]){Remove-Item -LiteralPath ('Env:'+ $key) -ErrorAction SilentlyContinue}else{[Environment]::SetEnvironmentVariable($key,$savedPreviewEnv[$key],'Process')}}
}
