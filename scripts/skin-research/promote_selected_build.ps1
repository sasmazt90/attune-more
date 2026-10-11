$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$stageRoot = Join-Path $taskRoot '.runtime/skin-selected-build-20261011-v2'
$receipt = Get-Content -LiteralPath (Join-Path $stageRoot 'source-receipt.json') -Raw | ConvertFrom-Json
foreach ($entry in $receipt.PSObject.Properties) {
    if ((Get-FileHash -LiteralPath (Join-Path $taskRoot $entry.Name) -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) { throw "Source drift: $($entry.Name)" }
}
$launcherRoot = 'C:\Users\PC\Desktop\YENİ İŞ\Applications\7. TOGG\.launcher'
$statePath = Join-Path $launcherRoot 'session.json'
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($state.status -eq 'running') {
    $ownedBrowser = Get-CimInstance Win32_Process -Filter "ProcessId=$($state.browser_pid)"
    if ($ownedBrowser.Name -ne 'chrome.exe' -or -not $ownedBrowser.CommandLine.Contains('--user-data-dir=' + $state.profile)) { throw 'Browser ownership mismatch.' }
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public class SelectedWindowClose {
 public delegate bool Callback(IntPtr window,IntPtr context);
 [DllImport("user32.dll")] public static extern bool EnumWindows(Callback callback,IntPtr context);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window,out uint process);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window,uint message,IntPtr w,IntPtr l);
 public static void Close(uint process) { EnumWindows((window,context)=>{uint owner;GetWindowThreadProcessId(window,out owner);if(owner==process)PostMessage(window,0x0010,IntPtr.Zero,IntPtr.Zero);return true;},IntPtr.Zero); }
}
'@
    [SelectedWindowClose]::Close([uint32]$state.browser_pid)
    $deadline = (Get-Date).AddSeconds(35)
    do {
        Start-Sleep -Milliseconds 500
        $state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    } while ($state.status -ne 'stopped' -and (Get-Date) -lt $deadline)
    if ($state.status -ne 'stopped') { throw 'Normal owned launcher did not drain; no build moved.' }
}
$liveBuild = [IO.Path]::GetFullPath((Join-Path $taskRoot 'apps/vehicle-app/.next'))
$stagedBuild = [IO.Path]::GetFullPath((Join-Path $stageRoot 'apps/vehicle-app/.next'))
$backupBuild = [IO.Path]::GetFullPath((Join-Path $taskRoot '.runtime/skin-selected-previous-next-20261011'))
foreach ($targetPath in @($liveBuild,$stagedBuild,$backupBuild)) {
    if (-not $targetPath.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Move path escapes workspace.' }
}
if (Test-Path -LiteralPath $backupBuild) { throw 'Prior preserved build exists; no overwrite.' }
if (-not (Test-Path -LiteralPath (Join-Path $stagedBuild 'BUILD_ID'))) { throw 'Staged build missing.' }
Move-Item -LiteralPath $liveBuild -Destination $backupBuild
Move-Item -LiteralPath $stagedBuild -Destination $liveBuild
Start-Process -FilePath (Join-Path (Split-Path -Parent $launcherRoot) 'TOGG Başlat.lnk')
Write-Output 'Preserved previous build; launched the promoted build through the normal shortcut.'
