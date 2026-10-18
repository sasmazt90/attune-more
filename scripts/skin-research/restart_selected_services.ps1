$ErrorActionPreference = 'Stop'
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
    if ($state.status -ne 'stopped') { throw 'Normal owned launcher did not drain; no unrelated process stopped.' }
}
Start-Process -FilePath (Join-Path (Split-Path -Parent $launcherRoot) 'TOGG Başlat.lnk')
Write-Output 'Reloaded current backend through the owned normal shortcut; build and user records preserved.'
