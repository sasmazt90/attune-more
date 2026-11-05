"""Run only the real Connect-Aws function, with synthetic AWS commands and no credentials."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which('pwsh') or shutil.which('powershell')


@pytest.mark.skipif(not POWERSHELL, reason='PowerShell runtime required (available on CI runner)')
@pytest.mark.parametrize('login_throws', [False, True])
def test_login_output_does_not_contaminate_status(tmp_path, login_throws):
    script = tmp_path / 'login-test.ps1'
    script.write_text(r'''
param([string]$Source, [string]$Throws)
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw 'Control script parse failed' }
$function = $ast.Find({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Connect-Aws'}, $true)
# Extract only this function: never execute the startup dispatcher or domain credential loading.
Invoke-Expression $function.Extent.Text
$Account = '123456789012'; $LoginProfile = 'synthetic'; $Region = 'eu-central-1'; $Result = @{}
$script:Calls = 0
function Write-Line { param($Message, $Color) }
function Invoke-Aws {
    $script:Calls++
    if ($script:Calls -eq 1) { return [pscustomobject]@{Ok=$false;Text='expired'} }
    return [pscustomobject]@{Ok=$true;Text='{"Account":"123456789012","Arn":"arn:aws:iam::123456789012:user/synthetic"}'}
}
function aws {
    'Synthetic interactive login banner'
    if ($Throws -eq 'true') { throw 'synthetic login failure' }
}
if ($Throws -eq 'true') {
    $caught = $false
    try { Connect-Aws } catch { $caught = $true }
    if (-not $caught) { throw 'Login failure was swallowed' }
} else {
    $status = @(Connect-Aws; 'READY')
    if ($status.Count -ne 1 -or $status[0] -ne 'READY') { throw 'Login output contaminated status' }
    if ($script:Calls -ne 2 -or -not $Result.identity) { throw 'Identity not rechecked' }
}
if ($ErrorActionPreference -ne 'Stop') { throw 'ErrorActionPreference not restored' }
'PASS'
''')
    done = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(script),
                           str(ROOT / 'scripts/aws/windows/AttuneControl.ps1'), str(login_throws).lower()],
                          capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stdout + done.stderr
    assert 'Synthetic interactive login banner' in done.stdout and 'PASS' in done.stdout
