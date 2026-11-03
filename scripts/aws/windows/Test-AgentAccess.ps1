<#
.SYNOPSIS
  Proves what one agent's AWS profile can and cannot do. Changes nothing.

.DESCRIPTION
  Every write check uses --dry-run, or targets an instance outside the allowed
  pair so that IAM refuses it before anything happens. Prints JSON and exits 1
  if any result differs from what the role is meant to allow.

  Not provable here: Start and Stop on an instance outside the pair. The account has
  no other instance and EC2 rejects a made-up ID as malformed before authorizing it.
  Those limits are checked against the policy files in tests/aws/test_control.py.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$AwsProfile,
    # Expected to differ between roles: only the control role may edit Security Groups.
    [switch]$ExpectIngressDenied
)

$ErrorActionPreference = 'Stop'
$Region = 'eu-central-1'
$Web = 'i-0b25450afc6633494'
$Aaos = 'i-0f4cca4e92e94c351'
$WebSg = 'sg-023659b3a447ab759'
$Outside = 'i-00000000000000000'

function Invoke-Aws {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & aws @Arguments --profile $AwsProfile --region $Region --no-cli-pager --output json 2>&1
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    [pscustomobject]@{ ExitCode = $code; Text = (($output | ForEach-Object { "$_" }) -join "`n") }
}

$rows = New-Object Collections.ArrayList

function Add-Check([string]$name, [string]$expected, $reply) {
    $actual = if ($reply.ExitCode -eq 0) { 'allowed' }
    elseif ($reply.Text -match 'DryRunOperation') { 'allowed' }
    elseif ($reply.Text -match 'UnauthorizedOperation|AccessDenied|not authorized') { 'denied' }
    else { 'error' }
    [void]$rows.Add([ordered]@{ check = $name; expected = $expected; actual = $actual; pass = ($actual -eq $expected) })
}

$identity = (Invoke-Aws sts get-caller-identity).Text | ConvertFrom-Json

Add-Check 'Read instance inventory' 'allowed' (Invoke-Aws ec2 describe-instances --instance-ids $Web $Aaos)
Add-Check 'Read instance state' 'allowed' (Invoke-Aws ec2 describe-instance-status --include-all-instances --instance-ids $Web $Aaos)
Add-Check 'Read Security Groups' 'allowed' (Invoke-Aws ec2 describe-security-groups --group-ids $WebSg)
Add-Check 'Read SSM node status' 'allowed' (Invoke-Aws ssm describe-instance-information)
Add-Check 'Read SSM command history' 'allowed' (Invoke-Aws ssm list-commands --max-items 1)
Add-Check 'Start WEB instance (dry run)' 'allowed' (Invoke-Aws ec2 start-instances --instance-ids $Web --dry-run)
Add-Check 'Start AAOS instance (dry run)' 'allowed' (Invoke-Aws ec2 start-instances --instance-ids $Aaos --dry-run)
Add-Check 'Stop WEB instance (dry run)' 'allowed' (Invoke-Aws ec2 stop-instances --instance-ids $Web --dry-run)
Add-Check 'Stop AAOS instance (dry run)' 'allowed' (Invoke-Aws ec2 stop-instances --instance-ids $Aaos --dry-run)
$ingress = if ($ExpectIngressDenied) { 'denied' } else { 'allowed' }
Add-Check 'Edit HTTPS rule on Security Group (dry run)' $ingress (Invoke-Aws ec2 authorize-security-group-ingress --group-id $WebSg --protocol tcp --port 443 --cidr 192.0.2.1/32 --dry-run)

Add-Check 'Run a command on an instance outside the pair' 'denied' (Invoke-Aws ssm send-command --instance-ids $Outside --document-name AWS-RunShellScript --parameters 'commands=true')
# A real image ID, because EC2 rejects a malformed one before authorizing the call.
$image = ((Invoke-Aws ec2 describe-instances --instance-ids $Web).Text | ConvertFrom-Json).Reservations[0].Instances[0].ImageId
Add-Check 'Create an instance (dry run)' 'denied' (Invoke-Aws ec2 run-instances --image-id $image --instance-type t3.micro --dry-run)
Add-Check 'Terminate an Attune instance (dry run)' 'denied' (Invoke-Aws ec2 terminate-instances --instance-ids $Web --dry-run)
Add-Check 'Allocate an Elastic IP (dry run)' 'denied' (Invoke-Aws ec2 allocate-address --domain vpc --dry-run)
Add-Check 'List IAM users' 'denied' (Invoke-Aws iam list-users)
Add-Check 'Create an IAM access key' 'denied' (Invoke-Aws iam create-access-key --user-name attune-operator)
Add-Check 'List S3 buckets' 'denied' (Invoke-Aws s3api list-buckets)
Add-Check 'Read Secrets Manager' 'denied' (Invoke-Aws secretsmanager list-secrets)

$failed = @($rows | Where-Object { -not $_.pass })
[ordered]@{
    profile = $AwsProfile; arn = $identity.Arn; account = $identity.Account
    observedAt = (Get-Date).ToUniversalTime().ToString('o')
    passed = $rows.Count - $failed.Count; failed = $failed.Count; checks = $rows
} | ConvertTo-Json -Depth 5
if ($failed) { exit 1 }
