$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot
$out=Join-Path (Split-Path $root) 'cdc-progress\health-final-technical-closeout-20261017'
$node='C:\nvm4w\nodejs\node.exe'
$cli=Join-Path $env:LOCALAPPDATA 'npm-cache\_npx\31e32ef8478fbf80\node_modules\@playwright\cli\playwright-cli.js'
Set-Location -LiteralPath $root
$cases=@(
 @{name='consent';file='health_ui_consent.js'},
 @{name='capture';file='health_ui_capture_revoke.js'},
 @{name='audio';file='health_ui_audio_lifecycle.js'},
 @{name='hearing';file='dental_hearing_preservation.js'},
 @{name='screens';file='health_final_screens.js'}
)
foreach($case in $cases){
 $session='health-delivered-'+$case.name
 $code=(Get-Content -LiteralPath (Join-Path $root ('tests\e2e\'+$case.file)) -Raw).Replace('3308','3311').Replace('3310','3311').Replace('health-ui-consent-audio-followup-20261017','health-final-technical-closeout-20261017').Replace('dental-technical-closeout-20261017','health-final-technical-closeout-20261017').Replace('__PORT__','3311').Replace('__PHASE__',"'delivered'")
 & $node $cli ('-s='+$session) open 'http://127.0.0.1:3311/' --headed *> (Join-Path $out ($case.name+'-final-open.log'))
 try{
  $log=Join-Path $out ($case.name+'-final.log')
  & $node $cli ('-s='+$session) run-code $code *> $log
  if($LASTEXITCODE -ne 0 -or -not(Select-String -LiteralPath $log -SimpleMatch '### Result' -Quiet) -or (Select-String -LiteralPath $log -SimpleMatch '### Error' -Quiet)){throw ('Browser check failed: '+$case.name)}
  Write-Output ('PASS final build '+$case.name)
 }finally{& $node $cli ('-s='+$session) close | Out-Null}
}
