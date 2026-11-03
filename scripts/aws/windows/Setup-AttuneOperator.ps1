<#
.SYNOPSIS
  Creates the narrow AWS identity that Attune.more operations use instead of root.

.DESCRIPTION
  Run this once, yourself, while signed in with `aws login --profile agent-toolkit`.

  It creates:
    - IAM user  attune-operator       Console sign-in only. NO access keys are ever created.
                                      It can do nothing except assume the two roles below.
    - IAM role  attune-ops-control    Desktop Start/Stop tool and Claude.
    - IAM role  attune-ops-verifier   Antigravity. Same as control, minus Security Group edits.

  Both roles can only start/stop and run commands on the two existing Attune instances.
  Both carry the repository's explicit deny on creating or terminating infrastructure.

  You choose the attune-operator password at a hidden prompt. It is never printed or logged.
  Safe to re-run: anything that already exists is kept and its policies are refreshed.
#>
[CmdletBinding()]
param(
    [string]$AdminProfile = 'agent-toolkit',
    [switch]$SkipPassword
)

$ErrorActionPreference = 'Stop'
$Account = '798886013428'
$Region = 'eu-central-1'
$UserName = 'attune-operator'
$UserArn = "arn:aws:iam::${Account}:user/$UserName"
$ControlRole = 'attune-ops-control'
$VerifierRole = 'attune-ops-verifier'
$IamDir = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\infra\aws\iam')).Path

function Invoke-Aws {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    # Windows PowerShell 5.1 turns native stderr into terminating errors under Stop.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & aws @Arguments --profile $AdminProfile --region $Region --no-cli-pager 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previous
    }
    [pscustomobject]@{ ExitCode = $exitCode; Text = (($output | ForEach-Object { "$_" }) -join "`n") }
}

function Assert-Ok($result, [string]$what) {
    if ($result.ExitCode -ne 0) { throw "$what failed: $($result.Text)" }
}

function Write-Step([string]$text) { Write-Host "`n== $text" -ForegroundColor Cyan }

function Write-TempJson([string]$json) {
    $path = Join-Path $env:TEMP ("attune-iam-" + [guid]::NewGuid().ToString('N') + '.json')
    [IO.File]::WriteAllText($path, $json, (New-Object Text.UTF8Encoding($false)))
    $path
}

function FileUri([string]$path) { 'file://' + ($path -replace '\\', '/') }

Write-Step 'Checking who is signed in'
$identity = Invoke-Aws sts get-caller-identity --output json
if ($identity.ExitCode -ne 0) {
    throw "No active AWS session on profile '$AdminProfile'. Run: aws login --profile $AdminProfile"
}
$caller = $identity.Text | ConvertFrom-Json
if ($caller.Account -ne $Account) { throw "Wrong AWS account: $($caller.Account). Expected $Account." }
Write-Host "Signed in as $($caller.Arn)"

Write-Step "Creating IAM user $UserName (no access keys)"
if ((Invoke-Aws iam get-user --user-name $UserName).ExitCode -eq 0) {
    Write-Host 'Already exists, keeping it.'
} else {
    Assert-Ok (Invoke-Aws iam create-user --user-name $UserName --tags 'Key=Project,Value=attune-more') 'create-user'
    Write-Host 'Created.'
}
Assert-Ok (Invoke-Aws iam attach-user-policy --user-name $UserName --policy-arn 'arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess') 'attach SignInLocalDevelopmentAccess'

$assumePolicy = @{
    Version   = '2012-10-17'
    Statement = @(@{
        Sid      = 'AssumeOnlyTheAttuneOperationsRoles'
        Effect   = 'Allow'
        Action   = 'sts:AssumeRole'
        Resource = @("arn:aws:iam::${Account}:role/$ControlRole", "arn:aws:iam::${Account}:role/$VerifierRole")
    })
} | ConvertTo-Json -Depth 6
$assumeFile = Write-TempJson $assumePolicy
try {
    Assert-Ok (Invoke-Aws iam put-user-policy --user-name $UserName --policy-name AttuneAssumeOperationsRoles --policy-document (FileUri $assumeFile)) 'put-user-policy'
} finally { Remove-Item -LiteralPath $assumeFile -Force -ErrorAction SilentlyContinue }

$trustPolicy = @{
    Version   = '2012-10-17'
    Statement = @(@{
        Effect    = 'Allow'
        Principal = @{ AWS = $UserArn }
        Action    = 'sts:AssumeRole'
    })
} | ConvertTo-Json -Depth 6
$trustFile = Write-TempJson $trustPolicy

Write-Step 'Creating the two operations roles'
try {
    foreach ($role in @(@{ Name = $ControlRole; File = 'attune-ops-control.json' }, @{ Name = $VerifierRole; File = 'attune-ops-verifier.json' })) {
        if ((Invoke-Aws iam get-role --role-name $role.Name).ExitCode -eq 0) {
            # A new IAM user can take a few seconds to become a valid principal.
            Assert-Ok (Invoke-Aws iam update-assume-role-policy --role-name $role.Name --policy-document (FileUri $trustFile)) "update trust on $($role.Name)"
            Write-Host "$($role.Name): already exists, policies refreshed."
        } else {
            $created = $null
            foreach ($attempt in 1..6) {
                $created = Invoke-Aws iam create-role --role-name $role.Name --assume-role-policy-document (FileUri $trustFile) --max-session-duration 43200 --tags 'Key=Project,Value=attune-more'
                if ($created.ExitCode -eq 0 -or $created.Text -notmatch 'MalformedPolicyDocument') { break }
                Start-Sleep -Seconds 5
            }
            Assert-Ok $created "create-role $($role.Name)"
            Write-Host "$($role.Name): created."
        }
        Assert-Ok (Invoke-Aws iam put-role-policy --role-name $role.Name --policy-name AttuneScopedOperations --policy-document (FileUri (Join-Path $IamDir $role.File))) "scoped policy on $($role.Name)"
        Assert-Ok (Invoke-Aws iam put-role-policy --role-name $role.Name --policy-name AttuneNoNewInfrastructure --policy-document (FileUri (Join-Path $IamDir 'no-new-infrastructure.json'))) "deny guard on $($role.Name)"
    }
} finally { Remove-Item -LiteralPath $trustFile -Force -ErrorAction SilentlyContinue }

if (-not $SkipPassword) {
    Write-Step "Setting the console password for $UserName"
    if ((Invoke-Aws iam get-login-profile --user-name $UserName).ExitCode -eq 0) {
        Write-Host 'A password is already set, keeping it.'
    } else {
        Write-Host 'Choose a password. AWS requires at least 8 characters by default. Typing stays hidden.'
        $secure = Read-Host -AsSecureString 'New password'
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try {
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            # A temp file keeps the password out of the process command line.
            $inputFile = Write-TempJson (@{ UserName = $UserName; Password = $plain; PasswordResetRequired = $false } | ConvertTo-Json)
            try {
                Assert-Ok (Invoke-Aws iam create-login-profile --cli-input-json (FileUri $inputFile)) 'create-login-profile'
            } finally { Remove-Item -LiteralPath $inputFile -Force -ErrorAction SilentlyContinue }
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
            $plain = $null
        }
        Write-Host 'Password set.'
    }
}

Write-Step 'Adding local AWS CLI profiles (no secrets are written)'
$profiles = @(
    @{ Name = 'attune-desktop'; Role = $ControlRole; Session = 'desktop' },
    @{ Name = 'attune-claude'; Role = $ControlRole; Session = 'claude' },
    @{ Name = 'attune-ag'; Role = $VerifierRole; Session = 'antigravity' }
)
& aws configure set "profile.$UserName.region" $Region
foreach ($entry in $profiles) {
    & aws configure set "profile.$($entry.Name).region" $Region
    & aws configure set "profile.$($entry.Name).role_arn" "arn:aws:iam::${Account}:role/$($entry.Role)"
    & aws configure set "profile.$($entry.Name).source_profile" $UserName
    & aws configure set "profile.$($entry.Name).role_session_name" $entry.Session
    Write-Host "Profile $($entry.Name) -> $($entry.Role) (session name: $($entry.Session))"
}

Write-Host ''
Write-Host 'Setup finished.' -ForegroundColor Green
Write-Host ''
Write-Host 'Last step: sign in as the new user.' -ForegroundColor Yellow
Write-Host "  1. Your browser may still have a root session. When it opens, choose to sign in with a"
Write-Host "     different account (or use a private window), then sign in as IAM user: $UserName"
Write-Host "     Account ID: $Account"
Write-Host "  2. Recommended: add MFA to $UserName afterwards in the IAM console."
Write-Host ''
$answer = Read-Host "Run 'aws login --profile $UserName' now? [Y/n]"
if ($answer -eq '' -or $answer -match '^[Yy]') {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & aws login --profile $UserName --region $Region
    $ErrorActionPreference = $previous
    $who = (& aws sts get-caller-identity --profile $UserName --output json 2>&1 | Out-String)
    if ($who -match [regex]::Escape($UserArn)) {
        Write-Host "Verified: signed in as $UserArn" -ForegroundColor Green
        Write-Host 'You can tell Claude this step is done.'
    } else {
        Write-Host "Sign-in did not produce the expected identity ($UserArn). Output:" -ForegroundColor Red
        Write-Host $who
        Write-Host "Retry with: aws login --profile $UserName"
    }
}
