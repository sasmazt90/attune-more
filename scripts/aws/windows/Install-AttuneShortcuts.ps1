<#
.SYNOPSIS
  Installs the Attune.more control tool for this Windows user and adds desktop shortcuts.

.DESCRIPTION
  Copies the tool to %LOCALAPPDATA%\AttuneMore\bin, so it keeps working if the Git clone
  moves, and creates START, STOP and STATUS shortcuts. No administrator rights are needed.
  Re-run after updating the repository to refresh the installed copy.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$bin = Join-Path $env:LOCALAPPDATA 'AttuneMore\bin'
New-Item -ItemType Directory -Force -Path $bin | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'AttuneControl.ps1') -Destination $bin -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\host_ready.py') -Destination $bin -Force

$desktop = [Environment]::GetFolderPath('Desktop')
$shell = New-Object -ComObject WScript.Shell
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$items = @(
    @{ Name = 'START ATTUNE.MORE'; Arguments = '-Action Start -OpenBrowser'; Icon = 'imageres.dll,101'; About = 'Start both AWS instances and verify every Attune.more service' },
    @{ Name = 'STOP ATTUNE.MORE'; Arguments = '-Action Stop'; Icon = 'imageres.dll,100'; About = 'Stop both AWS instances and show the session cost' },
    @{ Name = 'STATUS ATTUNE.MORE'; Arguments = '-Action Status'; Icon = 'imageres.dll,76'; About = 'Show instance state, service health and cost without changing anything' },
    @{ Name = 'LOGIN ATTUNE.MORE'; Arguments = '-Action ShowLogin'; Icon = 'imageres.dll,77'; About = 'Show the web page login. Needs the instances running.' }
)
foreach ($item in $items) {
    $shortcut = $shell.CreateShortcut((Join-Path $desktop ($item.Name + '.lnk')))
    $shortcut.TargetPath = $powershell
    $shortcut.Arguments = '-NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $bin 'AttuneControl.ps1') + '" ' + $item.Arguments
    $shortcut.WorkingDirectory = $bin
    $shortcut.IconLocation = Join-Path $env:SystemRoot ('System32\' + $item.Icon)
    $shortcut.Description = $item.About
    $shortcut.Save()
    Write-Host "Created shortcut: $($item.Name)"
}
Write-Host "Installed to $bin" -ForegroundColor Green
