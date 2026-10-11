param([Parameter(Mandatory=$true)][string]$ReceiptPath)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskRuntime=Join-Path $taskRoot '.runtime/storage-20261011'
$taskReceiptFile=(Resolve-Path -LiteralPath $ReceiptPath).Path
if ([IO.Path]::GetDirectoryName($taskReceiptFile) -ne $taskRuntime) {throw 'Receipt outside owned storage runtime'}
$taskReceipt=Get-Content -LiteralPath $taskReceiptFile -Raw | ConvertFrom-Json
$taskPython='C:\Users\PC\AppData\Local\Programs\Python\Python311\python.exe'
$taskPlanJSON=& $taskPython (Join-Path $PSScriptRoot 'checkpoint_archive_plan.py')
if ($LASTEXITCODE -ne 0) {throw 'Fresh checkpoint protection audit failed'}
$taskPlan=$taskPlanJSON | ConvertFrom-Json
$taskCandidate=@($taskPlan.candidates | Where-Object {$_.phase -eq $taskReceipt.phase -and $_.generation -eq $taskReceipt.generation})
if ($taskCandidate.Count -ne 1) {throw 'Checkpoint now protected, incomplete, or not eligible'}
$taskFolder=(Resolve-Path -LiteralPath $taskCandidate[0].sourceFolder).Path
$taskExpectedParent=Join-Path (Join-Path $taskRoot 'audit-results/skin-expanded-20261011') $taskReceipt.phase
if ($taskReceipt.phase -notin @('negative-yolox','negative-mask-continuation') -or [IO.Path]::GetDirectoryName($taskFolder) -ne $taskExpectedParent -or [IO.Path]::GetFileName($taskFolder) -cne $taskReceipt.generation) {throw 'Checkpoint path escaped scope'}
if (@($taskReceipt.files).Count -ne 3) {throw 'Incomplete cloud checkpoint'}
foreach ($taskFile in $taskCandidate[0].files) {
 $taskCloud=@($taskReceipt.files | Where-Object name -CEQ $taskFile.name)
 if ($taskCloud.Count -ne 1 -or $taskCloud[0].cloudDownloadReadCompletely -ne $true -or $taskCloud[0].cloudFileId -notmatch '^[A-Za-z0-9_-]+$' -or $taskCloud[0].sha256 -cne $taskFile.sha256 -or $taskCloud[0].bytes -ne $taskFile.bytes) {throw 'Full cloud SHA/size proof missing'}
 $taskSource=(Resolve-Path -LiteralPath $taskFile.source).Path
 if ([IO.Path]::GetDirectoryName($taskSource) -ne $taskFolder -or $taskFile.name -notin @('model.safetensors','optimizer.safetensors','state.json')) {throw 'Source escaped exact checkpoint'}
 if ((Get-FileHash -LiteralPath $taskSource -Algorithm SHA256).Hash.ToLowerInvariant() -cne $taskFile.sha256) {throw 'Local immutable checkpoint changed'}
}
$taskFreeBefore=(Get-PSDrive C).Free
$taskReceipt | Add-Member -NotePropertyName freeBeforeRemovalBytes -NotePropertyValue $taskFreeBefore
$taskReceipt | Add-Member -NotePropertyName stateReceiptRetainedLocally -NotePropertyValue $true
$taskSaved=Join-Path $taskFolder 'cloud-archive.json'
$taskReceipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $taskSaved -Encoding utf8
# Only cold tensor bytes leave local storage. Folder and full state/history remain.
foreach ($taskName in @('model.safetensors','optimizer.safetensors')) {
 Remove-Item -LiteralPath (Join-Path $taskFolder $taskName)
}
$taskReceipt | Add-Member -NotePropertyName freeAfterRemovalBytes -NotePropertyValue (Get-PSDrive C).Free
$taskReceipt | Add-Member -NotePropertyName localTensorBytesRemoved -NotePropertyValue $true
$taskReceipt | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $taskSaved -Encoding utf8
[pscustomobject]@{phase=$taskReceipt.phase;generation=$taskReceipt.generation;freeBefore=$taskFreeBefore;freeAfter=(Get-PSDrive C).Free;checkpointPreservedInVerifiedCloud=$true;localStateAndDirectoryRetained=$true} | ConvertTo-Json -Compress
