<#
.SYNOPSIS
  One-click START, STOP and STATUS for the two existing Attune.more EC2 instances.

.DESCRIPTION
  Never creates AWS resources. It starts and stops the two known instances, keeps the two
  authorized IONOS A records on their current EC2 addresses, renews browser-trusted
  certificates, restarts Attune services, runs checks through SSM, and asks before allowing
  a new home IP on the existing Security Groups. See AttuneDomain.ps1.

  Exit code: 0 READY or STOPPED, 1 PARTIAL, 2 ERROR.
#>
[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status', 'ShowLogin', 'SetupCertificates')][string]$Action = 'Status',
    [string]$AwsProfile = 'attune-desktop',
    [string]$LoginProfile = 'attune-operator',
    # Also hashes every model file and generates real Chatterbox speech. Adds several minutes.
    [switch]$Deep,
    [switch]$OpenBrowser,
    [switch]$NoPause,
    # For unattended runs: allow this PC's new public IP without asking.
    [switch]$AllowIpChange,
    # Start only: request new certificates even if the current ones have time left.
    [switch]$RenewCertificates,
    # Root-readable login record on the WEB host.
    [string]$LoginFile = '/var/lib/attune/qa/access.json'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
# Same number and date formatting whatever the Windows display language is.
[Threading.Thread]::CurrentThread.CurrentCulture = [Globalization.CultureInfo]::InvariantCulture
# Host output can hold characters outside the Windows code page, which would crash the AWS CLI.
$env:PYTHONUTF8 = '1'

$Region = 'eu-central-1'
$Account = '798886013428'
$WebDomain = 'attunemore.sasmaz.digital'
$AaosDomain = 'aaos.attunemore.sasmaz.digital'
$WebSg = 'sg-023659b3a447ab759'
$AaosSg = 'sg-0476f580c44063a5d'
$Targets = @(
    @{ Role = 'web'; Id = 'i-0b25450afc6633494'; Name = 'attune-web-ai'; Type = 'r7i.2xlarge'; UsdPerHour = 0.6384 },
    @{ Role = 'aaos'; Id = 'i-0f4cca4e92e94c351'; Name = 'attune-aaos-demo'; Type = 'm8i.2xlarge'; UsdPerHour = 0.50716 }
)
$TargetIds = @($Targets | ForEach-Object { $_.Id })
# AWS Pricing API, Frankfurt Linux On-Demand, recorded in docs/aws/evidence/final-cost-20261103.json.
$Ipv4UsdPerHourEach = 0.005
$EbsUsdPerMonth = 25.704

$HostScript = Join-Path $PSScriptRoot 'host_ready.py'
if (-not (Test-Path -LiteralPath $HostScript)) { $HostScript = Join-Path $PSScriptRoot '..\host_ready.py' }
$StableScript = Join-Path $PSScriptRoot 'stable_host.py'
if (-not (Test-Path -LiteralPath $StableScript)) { $StableScript = Join-Path $PSScriptRoot '..\stable_host.py' }
. (Join-Path $PSScriptRoot 'AttuneDomain.ps1')
# Not under AppData. A packaged app redirects its writes there to a private copy, so the same path
# would hold different files for the desktop shortcuts and for a tool started from that app.
$DataRoot = Join-Path $env:USERPROFILE 'AttuneMore'
$ReportRoot = Join-Path $DataRoot 'reports'
$StartedAt = Get-Date
$Result = [ordered]@{
    action = $Action; startedAt = $StartedAt.ToUniversalTime().ToString('o'); status = 'ERROR'; identity = $null
    instances = @(); checks = @(); recoveries = @(); urls = @{}; dns = @(); certificates = @(); cost = @{}; timings = [ordered]@{}; problems = @()
}

function Write-Line([string]$text, [string]$color = 'Gray') { Write-Host $text -ForegroundColor $color }
function Write-Step([string]$text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Add-Problem([string]$text) { $Result.problems += $text }
function Add-Timing([string]$name) { $Result.timings[$name] = [math]::Round(((Get-Date) - $StartedAt).TotalSeconds) }

function Invoke-Aws {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & aws @Arguments --profile $AwsProfile --region $Region --no-cli-pager 2>&1
        $exitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    [pscustomobject]@{ Ok = ($exitCode -eq 0); Text = (($output | ForEach-Object { "$_" }) -join "`n") }
}

function Invoke-AwsJson {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    $response = Invoke-Aws @Arguments --output json
    if (-not $response.Ok) { throw $response.Text }
    if ([string]::IsNullOrWhiteSpace($response.Text)) { return $null }
    $response.Text | ConvertFrom-Json
}

function Connect-Aws {
    $check = Invoke-Aws sts get-caller-identity --output json
    if (-not $check.Ok) {
        Write-Line 'Your AWS sign-in has expired or is missing. Opening the browser so you can sign in...' Yellow
        Write-Line "Sign in as IAM user $LoginProfile (account $Account)." Yellow
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & aws login --profile $LoginProfile --region $Region
        $ErrorActionPreference = $previous
        $check = Invoke-Aws sts get-caller-identity --output json
        if (-not $check.Ok) { throw "AWS sign-in failed: $($check.Text)" }
    }
    $identity = $check.Text | ConvertFrom-Json
    if ($identity.Account -ne $Account) { throw "Signed in to the wrong AWS account ($($identity.Account))." }
    if ($identity.Arn -match ':root$') { throw 'Refusing to operate as the AWS root user. Use the attune profiles.' }
    $Result.identity = $identity.Arn
    Write-Line "Signed in: $($identity.Arn)" DarkGray
}

function Get-Instances {
    $reply = Invoke-AwsJson ec2 describe-instances --instance-ids $TargetIds[0] $TargetIds[1]
    $found = @($reply.Reservations | ForEach-Object { $_.Instances })
    foreach ($target in $Targets) {
        $instance = $found | Where-Object { $_.InstanceId -eq $target.Id }
        if (-not $instance) { throw "Instance $($target.Id) not found." }
        $name = ($instance.Tags | Where-Object { $_.Key -eq 'Name' }).Value
        if ($instance.InstanceType -ne $target.Type -or $name -ne $target.Name) {
            throw "Instance $($target.Id) is '$name' $($instance.InstanceType), expected '$($target.Name)' $($target.Type). Refusing to continue."
        }
    }
    $found
}

# AWS omits this field while an instance is stopped; strict mode treats a missing field as an error.
function Get-PublicIp($instance) {
    $field = $instance.PSObject.Properties['PublicIpAddress']
    if ($field) { return $field.Value }
    $null
}

function Get-InstanceOf($instances, [string]$role) {
    $id = ($Targets | Where-Object { $_.Role -eq $role }).Id
    $instances | Where-Object { $_.InstanceId -eq $id }
}

function Get-RunningHours($instance, [datetime]$until) {
    $launch = ([datetime]$instance.LaunchTime).ToUniversalTime()
    # A plain 0 selects the integer overload, which rounds the result to whole hours.
    [math]::Max([double]0, ($until.ToUniversalTime() - $launch).TotalHours)
}

function Get-StopTime($instance) {
    $match = [regex]::Match([string]$instance.StateTransitionReason, '\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) GMT\)')
    if ($match.Success) {
        return [datetime]::SpecifyKind([datetime]::Parse($match.Groups[1].Value), 'Utc')
    }
    (Get-Date).ToUniversalTime()
}

function Set-CostEstimate($instances) {
    $total = 0.0
    $lines = @()
    foreach ($target in $Targets) {
        $instance = $instances | Where-Object { $_.InstanceId -eq $target.Id }
        $state = $instance.State.Name
        $until = if ($state -eq 'stopped' -or $state -eq 'stopping') { Get-StopTime $instance } else { (Get-Date).ToUniversalTime() }
        $hours = Get-RunningHours $instance $until
        $usd = $hours * ($target.UsdPerHour + $Ipv4UsdPerHourEach)
        $total += $usd
        $lines += [ordered]@{ role = $target.Role; state = $state; hours = [math]::Round($hours, 3); usd = [math]::Round($usd, 3) }
    }
    $running = @($instances | Where-Object { $_.State.Name -in @('running', 'pending') })
    $ratePerHour = 0.0
    foreach ($instance in $running) {
        $ratePerHour += ($Targets | Where-Object { $_.Id -eq $instance.InstanceId }).UsdPerHour + $Ipv4UsdPerHourEach
    }
    $Result.cost = [ordered]@{
        basis = 'Estimate from recorded AWS On-Demand rates and instance run time. Not a bill. Excludes data transfer, OpenAI and tax.'
        sessionComputeAndIpv4Usd = [math]::Round($total, 2); perInstance = $lines
        computeRunningNowUsdPerHour = [math]::Round($ratePerHour, 3)
        ebsContinuesUsdPerMonth = $EbsUsdPerMonth
    }
}

function Write-Cost {
    $cost = $Result.cost
    Write-Host ''
    Write-Line 'Cost (estimate, not a bill)' White
    foreach ($line in $cost.perInstance) {
        Write-Line ('  {0,-5} {1,-9} {2,6:N2} h   about ${3:N2}' -f $line.role.ToUpper(), $line.state, $line.hours, $line.usd)
    }
    Write-Line ('  Last session compute + public IPv4: about ${0:N2}' -f $cost.sessionComputeAndIpv4Usd)
    if ($cost.computeRunningNowUsdPerHour -gt 0) {
        Write-Line ('  Running now: about ${0:N2} per hour until you press STOP.' -f $cost.computeRunningNowUsdPerHour) Yellow
    } else {
        Write-Line '  Compute and public IPv4: $0.00 per hour while stopped.' Green
    }
    Write-Line ('  Disk storage (EBS) continues while stopped: about ${0:N2} per month.' -f $cost.ebsContinuesUsdPerMonth)
    Write-Line '  Excludes data transfer, OpenAI usage and tax.' DarkGray
}

function Get-MyPublicIp {
    try {
        $ip = (Invoke-RestMethod -Uri 'https://checkip.amazonaws.com' -TimeoutSec 10).Trim()
        if ($ip -match '^\d{1,3}(\.\d{1,3}){3}$') { return $ip }
    } catch { }
    $null
}

function Sync-HomeIp {
    $ip = Get-MyPublicIp
    if (-not $ip) {
        Write-Line "Could not determine this PC's public IP. Skipping the Security Group check." Yellow
        return
    }
    $wanted = "$ip/32"
    $groups = (Invoke-AwsJson ec2 describe-security-groups --group-ids $WebSg $AaosSg).SecurityGroups
    $changes = @()
    foreach ($group in $groups) {
        $rule = $group.IpPermissions | Where-Object { $_.IpProtocol -eq 'tcp' -and $_.FromPort -eq 443 -and $_.ToPort -eq 443 }
        $cidrs = @()
        if ($rule) { $cidrs = @($rule.IpRanges | ForEach-Object { $_.CidrIp }) }
        if ($cidrs -notcontains $wanted) { $changes += [pscustomobject]@{ Group = $group.GroupId; Old = $cidrs } }
    }
    if (-not $changes) {
        Write-Line "This PC ($ip) is already allowed on HTTPS." DarkGray
        return
    }
    Write-Line "This PC's public IP changed to $ip, so the Attune HTTPS pages are currently blocked for it." Yellow
    $approved = [bool]$AllowIpChange
    if (-not $approved) {
        $answer = Read-Host 'Allow this IP on port 443 and remove the old IP? [Y/n]'
        $approved = ($answer -eq '' -or $answer -match '^[Yy]')
    }
    if (-not $approved) {
        Add-Problem "HTTPS is not reachable from this PC: $ip is not allowed by the Security Groups."
        return
    }
    foreach ($change in $changes) {
        $allow = Invoke-Aws ec2 authorize-security-group-ingress --group-id $change.Group --protocol tcp --port 443 --cidr $wanted
        if (-not $allow.Ok -and $allow.Text -notmatch 'InvalidPermission.Duplicate') {
            Add-Problem "Could not allow $ip on $($change.Group): $($allow.Text)"
            continue
        }
        foreach ($old in $change.Old) {
            if ($old -ne $wanted) { [void](Invoke-Aws ec2 revoke-security-group-ingress --group-id $change.Group --protocol tcp --port 443 --cidr $old) }
        }
        $Result.recoveries += "Security Group $($change.Group): HTTPS source changed to $wanted"
    }
    Write-Line "Allowed $ip on HTTPS and removed the old address." Green
}

function Wait-State([string[]]$ids, [string]$wanted, [int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $instances = Get-Instances
        $pending = @($instances | Where-Object { $ids -contains $_.InstanceId -and $_.State.Name -ne $wanted })
        if (-not $pending) { return $true }
        Start-Sleep -Seconds 5
    }
    $false
}

function Start-Compute {
    $instances = Get-Instances
    $stopping = @($instances | Where-Object { $_.State.Name -eq 'stopping' } | ForEach-Object { $_.InstanceId })
    if ($stopping) {
        Write-Line 'An instance is still stopping. Waiting for it to finish first...'
        if (-not (Wait-State $stopping 'stopped' 360)) { throw 'An instance did not finish stopping within 6 minutes.' }
        $instances = Get-Instances
    }
    $stopped = @($instances | Where-Object { $_.State.Name -eq 'stopped' } | ForEach-Object { $_.InstanceId })
    foreach ($id in $stopped) {
        $name = ($Targets | Where-Object { $_.Id -eq $id }).Name
        Write-Line "Starting $name ($id)..."
        $deadline = (Get-Date).AddMinutes(5)
        while ($true) {
            $reply = Invoke-Aws ec2 start-instances --instance-ids $id --output json
            if ($reply.Ok) { break }
            if ($reply.Text -match 'InsufficientInstanceCapacity' -and (Get-Date) -lt $deadline) {
                Write-Line 'AWS has no capacity for this instance type right now. Retrying in 30 seconds...' Yellow
                $Result.recoveries += "Capacity retry on $name"
                Start-Sleep -Seconds 30
                continue
            }
            throw "AWS refused to start ${name}: $($reply.Text)"
        }
    }
    if (-not (Wait-State $TargetIds 'running' 420)) { throw 'Instances did not reach running within 7 minutes.' }
    Add-Timing 'computeRunningSeconds'
    Write-Line 'Both instances are running.' Green
}

function Wait-Ssm([int]$timeoutSeconds) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $reply = Invoke-AwsJson ssm describe-instance-information --filters "Key=InstanceIds,Values=$($TargetIds -join ',')"
        $online = @($reply.InstanceInformationList | Where-Object { $_.PingStatus -eq 'Online' })
        if ($online.Count -eq 2) { return $true }
        Start-Sleep -Seconds 5
    }
    $false
}

function Invoke-HostCommand([string]$instanceId, [string[]]$commands, [int]$timeoutSeconds = 300) {
    $file = Join-Path $env:TEMP ('attune-ssm-' + [guid]::NewGuid().ToString('N') + '.json')
    [IO.File]::WriteAllText($file, (@{ commands = $commands } | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
    try {
        $sent = Invoke-AwsJson ssm send-command --instance-ids $instanceId --document-name AWS-RunShellScript --comment 'Attune desktop control' --timeout-seconds ([string]$timeoutSeconds) --parameters ('file://' + ($file -replace '\\', '/'))
    } finally { Remove-Item -LiteralPath $file -Force -ErrorAction SilentlyContinue }
    $commandId = $sent.Command.CommandId
    $deadline = (Get-Date).AddSeconds($timeoutSeconds + 30)
    Start-Sleep -Seconds 2
    while ((Get-Date) -lt $deadline) {
        $reply = Invoke-Aws ssm get-command-invocation --command-id $commandId --instance-id $instanceId --output json
        if ($reply.Ok) {
            $invocation = $reply.Text | ConvertFrom-Json
            if ($invocation.Status -notin @('Pending', 'InProgress', 'Delayed')) {
                return [pscustomobject]@{ Status = $invocation.Status; Code = $invocation.ResponseCode; Out = $invocation.StandardOutputContent; Err = $invocation.StandardErrorContent }
            }
        }
        Start-Sleep -Seconds 3
    }
    [pscustomobject]@{ Status = 'TimedOut'; Code = -1; Out = ''; Err = 'No result in time' }
}

function Get-InlineScriptCommands([string]$path, [string]$arguments) {
    $bytes = [IO.File]::ReadAllBytes($path)
    $memory = New-Object IO.MemoryStream
    $gzip = New-Object IO.Compression.GZipStream($memory, [IO.Compression.CompressionMode]::Compress)
    $gzip.Write($bytes, 0, $bytes.Length)
    $gzip.Close()
    $encoded = [Convert]::ToBase64String($memory.ToArray())
    $commands = @('set -e', 'target=$(mktemp /tmp/attune-host-script.XXXXXX)')
    for ($at = 0; $at -lt $encoded.Length; $at += 3000) {
        $commands += "printf %s '" + $encoded.Substring($at, [math]::Min(3000, $encoded.Length - $at)) + "' >> `"`$target`""
    }
    $commands += 'base64 -d "$target" | gunzip > "$target.py"'
    $commands += "python3 `"`$target.py`" $arguments"
    $commands += 'rm -f "$target" "$target.py"'
    $commands
}

function Get-HostScriptCommands([string]$role) {
    $deepFlag = if ($Deep) { ' --deep' } else { '' }
    Get-InlineScriptCommands $HostScript "--role $role$deepFlag"
}

# Certificates and origins only. Public data travels; nothing here prints a key.
function Invoke-StableHost([string]$role, [string]$step, [string]$payload) {
    $id = ($Targets | Where-Object { $_.Role -eq $role }).Id
    $arguments = "$step --role $role"
    if ($payload) { $arguments += " --payload '$payload'" }
    $reply = Invoke-HostCommand $id (Get-InlineScriptCommands $StableScript $arguments) 180
    if ($reply.Status -ne 'Success') {
        $detail = "$($reply.Err)".Trim()
        if ($detail.Length -gt 300) { $detail = $detail.Substring($detail.Length - 300) }
        throw "$($role.ToUpper()) step '$step' failed: $detail"
    }
    ($reply.Out.Trim() -split "`n" | Select-Object -Last 1) | ConvertFrom-Json
}

function Get-HostReport([string]$role, [int]$timeoutSeconds = 240) {
    $id = ($Targets | Where-Object { $_.Role -eq $role }).Id
    $reply = Invoke-HostCommand $id (Get-HostScriptCommands $role) $timeoutSeconds
    if ($reply.Status -ne 'Success') { return $null }
    try { return ($reply.Out.Trim() -split "`n" | Select-Object -Last 1) | ConvertFrom-Json } catch { return $null }
}

function Wait-HostReady([string]$role, [int]$timeoutSeconds, [int]$pollSeconds = 20) {
    $deadline = (Get-Date).AddSeconds($timeoutSeconds)
    $last = $null
    $lastFailed = ''
    while ((Get-Date) -lt $deadline) {
        $last = Get-HostReport $role ([math]::Max(120, [int]($deadline - (Get-Date)).TotalSeconds))
        if ($last -and $last.ready) { return $last }
        $failed = if ($last) { (@($last.failedRequired) -join ', ') } else { 'no report yet' }
        if ($failed -ne $lastFailed) {
            Write-Line "  ${role}: still waiting for: $failed" DarkGray
            $lastFailed = $failed
        }
        Start-Sleep -Seconds $pollSeconds
    }
    $last
}

function Write-HostReport($report, [string]$role) {
    if (-not $report) {
        Write-Line "  [FAIL] $($role.ToUpper()): no report from the host" Red
        return
    }
    foreach ($check in $report.checks) {
        $color = switch ($check.status) { 'PASS' { 'Green' } 'WARN' { 'Yellow' } default { if ($check.required) { 'Red' } else { 'Yellow' } } }
        $tag = switch ($check.status) { 'PASS' { ' OK ' } 'WARN' { 'WARN' } default { 'FAIL' } }
        $detail = if ($check.detail) { "  ($($check.detail))" } else { '' }
        Write-Line "  [$tag] $($check.label)$detail" $color
    }
}

function Sync-Origins {
    foreach ($role in @('web', 'aaos')) {
        try {
            $reply = Invoke-StableHost $role 'origins'
            $changed = @($reply.changed)
            if ($changed) {
                $Result.recoveries += "Origins updated on ${role}: $($changed -join ', ')"
                Write-Line "  $($role.ToUpper()): origins updated, restarting its services." Yellow
                [void](Invoke-StableHost $role 'restart')
            }
        } catch { Add-Problem "Could not confirm the origins on $($role.ToUpper()): $($_.Exception.Message)" }
    }
}

function Start-Services {
    $web = ($Targets | Where-Object { $_.Role -eq 'web' }).Id
    $aaos = ($Targets | Where-Object { $_.Role -eq 'aaos' }).Id
    $webReply = Invoke-HostCommand $web @('systemctl start attune-caddy attune-api@web attune-api@aaos attune-web@web attune-web@aaos attune-capture') 180
    if ($webReply.Status -ne 'Success') { Add-Problem "WEB services did not start cleanly: $($webReply.Err)" }
    # attune-aaos is Type=simple, so this returns immediately while Android boots.
    $aaosReply = Invoke-HostCommand $aaos @('systemctl start attune-caddy attune-aaos attune-audio') 120
    if ($aaosReply.Status -ne 'Success') { Add-Problem "AAOS services did not start cleanly: $($aaosReply.Err)" }
}

function Restart-FailedUnits($report, [string]$role) {
    if (-not $report) { return $false }
    $units = @($report.failedRequired | Where-Object { $_ -like 'unit:*' } | ForEach-Object { $_.Substring(5) })
    if (-not $units) { return $false }
    Write-Line "  Restarting: $($units -join ', ')" Yellow
    $Result.recoveries += "Restarted on ${role}: $($units -join ', ')"
    $id = ($Targets | Where-Object { $_.Role -eq $role }).Id
    [void](Invoke-HostCommand $id @("systemctl restart $($units -join ' ')") 180)
    $true
}

# No certificate bypass and no address pinning: this is the path a browser takes.
function Test-PublicHttps($instances) {
    $rows = @()
    foreach ($pair in @(@{ Role = 'web'; Domain = $WebDomain }, @{ Role = 'aaos'; Domain = $AaosDomain })) {
        $ip = Get-PublicIp (Get-InstanceOf $instances $pair.Role)
        & ipconfig.exe /flushdns | Out-Null
        $resolved = @(Get-SystemAnswer $pair.Domain)
        $code = & curl.exe -s --max-time 15 --ssl-revoke-best-effort -o NUL -w '%{http_code}' "https://$($pair.Domain)/"
        $curlExit = $LASTEXITCODE
        $rows += [ordered]@{
            role = $pair.Role; publicIp = $ip; domain = $pair.Domain; resolvesTo = ($resolved -join ',')
            dnsPointsHere = [bool]($ip -and $resolved.Count -eq 1 -and $resolved[0] -eq $ip)
            trustedCertificate = [bool]("$code" -ne '000' -and $curlExit -eq 0); unauthenticatedHttps = "$code"
        }
    }
    $rows
}

function Add-AddressProblems($rows) {
    foreach ($row in $rows) {
        if (-not $row.dnsPointsHere) { Add-Problem "$($row.domain) resolves to '$($row.resolvesTo)' on this PC, but its instance has $($row.publicIp)." }
        elseif (-not $row.trustedCertificate) { Add-Problem "$($row.domain): the HTTPS connection failed or the certificate is not trusted, so a browser would warn (curl result $($row.unauthenticatedHttps))." }
        elseif ($row.unauthenticatedHttps -ne '401') { Add-Problem "$($row.domain) did not refuse an unauthenticated request (HTTP $($row.unauthenticatedHttps))." }
    }
}

function Sync-Dns($instances, $zone) {
    $homeIp = Get-MyPublicIp
    foreach ($pair in @(@{ Role = 'web'; Domain = $WebDomain }, @{ Role = 'aaos'; Domain = $AaosDomain })) {
        $instance = Get-InstanceOf $instances $pair.Role
        # From AWS, for this exact instance ID. Nothing else can reach the record.
        $ip = Get-PublicIp $instance
        if (-not $ip) {
            Add-Problem "$($pair.Domain): instance $($instance.InstanceId) has no public IP yet, so DNS was not changed."
            continue
        }
        try {
            $action = Sync-DnsRecord $zone.id $pair.Domain $ip $homeIp
            $Result.dns += [ordered]@{ name = $pair.Domain; instance = $instance.InstanceId; ip = $ip; action = $action }
            Write-Line "  $($pair.Domain) -> $ip ($action)" $(if ($action -eq 'unchanged') { 'DarkGray' } else { 'Green' })
        } catch {
            Add-Problem "DNS for $($pair.Domain) was not changed: $($_.Exception.Message)"
            Write-Line "  $($pair.Domain): NOT changed" Red
        }
    }
}

function Confirm-Dns($instances, $zone) {
    $servers = @(Get-AuthoritativeServers $zone.id)
    foreach ($pair in @(@{ Role = 'web'; Domain = $WebDomain }, @{ Role = 'aaos'; Domain = $AaosDomain })) {
        $ip = Get-PublicIp (Get-InstanceOf $instances $pair.Role)
        if (-not $ip) { continue }
        $seen = Confirm-Hostname $pair.Domain $ip $servers
        $entry = @($Result.dns | Where-Object { $_.name -eq $pair.Domain }) | Select-Object -First 1
        if ($entry) { $entry.resolution = $seen }
        if (-not $seen.authoritative) { Add-Problem "$($pair.Domain): the IONOS name servers do not yet answer $ip." }
        elseif (-not $seen.thisPcOk) { Add-Problem "$($pair.Domain): IONOS is correct, but this PC still resolves it to '$($seen.thisPcAnswer)'. Its resolver may be caching; try STATUS in a few minutes." }
        else { Write-Line "  $($pair.Domain) resolves to $ip (name servers and this PC; $($seen.publicResolversAgreeing) of $($script:PublicResolvers.Count) public resolvers)" Green }
    }
}

function Sync-Certificates($zone) {
    $servers = $null
    foreach ($role in @('web', 'aaos')) {
        try {
            $state = Invoke-StableHost $role 'public-state'
            if (-not $state.needsCertificate -and -not $RenewCertificates) {
                Write-Line "  $($state.name): trusted certificate, $($state.daysLeft) days left" DarkGray
                $Result.certificates += [ordered]@{ name = $state.name; action = 'kept'; daysLeft = $state.daysLeft; notAfter = $state.notAfter }
                continue
            }
            Write-Line "  $($state.name): requesting a browser-trusted certificate" White
            if (-not $servers) { $servers = @(Get-AuthoritativeServers $zone.id) }
            $request = Invoke-StableHost $role 'public-request'
            $chain = New-PublicCertificate $request.name $request.request 'production' $zone.id $servers
            $payload = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes((@{ chain = $chain } | ConvertTo-Json -Compress)))
            $after = Invoke-StableHost $role 'install-public' $payload
            $Result.certificates += [ordered]@{ name = $after.name; action = 'issued'; daysLeft = $after.daysLeft; notAfter = $after.notAfter }
            Write-Line "  $($after.name): installed, $($after.daysLeft) days left" Green
        } catch {
            $Result.certificates += [ordered]@{ name = "$role"; action = 'failed' }
            Add-Problem "Certificate for $($role.ToUpper()): $($_.Exception.Message)"
        }
    }
}

function Open-Browser($urls) {
    # The ordinary browser and real DNS, so what opens here is what any allowed device sees.
    foreach ($url in $urls) { Start-Process "https://$($url.domain)/" | Out-Null }
}

function Save-Result {
    New-Item -ItemType Directory -Force -Path $ReportRoot | Out-Null
    $Result.finishedAt = (Get-Date).ToUniversalTime().ToString('o')
    $Result.seconds = [math]::Round(((Get-Date) - $StartedAt).TotalSeconds)
    $path = Join-Path $ReportRoot ('{0:yyyyMMdd-HHmmss}-{1}.json' -f $StartedAt, $Action.ToLower())
    [IO.File]::WriteAllText($path, ($Result | ConvertTo-Json -Depth 8), (New-Object Text.UTF8Encoding($false)))
    $path
}

function Write-Banner([string]$status, [string]$message) {
    $color = switch ($status) { 'READY' { 'Green' } 'STOPPED' { 'Green' } 'PARTIAL' { 'Yellow' } default { 'Red' } }
    Write-Host ''
    Write-Host ('=' * 66) -ForegroundColor $color
    Write-Host ("  ATTUNE.MORE: $status") -ForegroundColor $color
    if ($message) { Write-Host "  $message" -ForegroundColor $color }
    Write-Host ('=' * 66) -ForegroundColor $color
}

function Write-Urls($rows) {
    Write-Host ''
    Write-Line 'Addresses' White
    foreach ($row in $rows) {
        $label = if ($row.role -eq 'web') { 'WEB ' } else { 'AAOS' }
        $routing = if (-not $row.dnsPointsHere) { "NOT resolving to this instance ($($row.publicIp))" } elseif ($row.trustedCertificate) { 'DNS correct, certificate trusted' } else { 'DNS correct, certificate NOT trusted' }
        Write-Line "  $label https://$($row.domain)/   ($routing)"
    }
}

function New-Der([int]$tag, [byte[]]$content) {
    $length = $content.Length
    $prefix = if ($length -lt 128) { @($length) } elseif ($length -lt 256) { @(0x81, $length) } else { @(0x82, ($length -shr 8), ($length -band 255)) }
    [byte[]](@($tag) + $prefix + $content)
}

function Get-PublicKeyPem($rsa) {
    $key = $rsa.ExportParameters($false)
    $integer = { param([byte[]]$value) if ($value[0] -ge 0x80) { $value = [byte[]](@(0) + $value) }; New-Der 2 $value }
    $sequence = New-Der 0x30 ([byte[]]((& $integer $key.Modulus) + (& $integer $key.Exponent)))
    $algorithm = [byte[]](0x30, 0x0d, 0x06, 0x09, 0x2a, 0x86, 0x48, 0x86, 0xf7, 0x0d, 0x01, 0x01, 0x01, 0x05, 0x00)
    $der = New-Der 0x30 ([byte[]]($algorithm + (New-Der 3 ([byte[]](@(0) + $sequence)))))
    "-----BEGIN PUBLIC KEY-----`n" + [Convert]::ToBase64String($der, 'InsertLineBreaks').Replace("`r", '') + "`n-----END PUBLIC KEY-----`n"
}

function Invoke-ShowLogin {
    Connect-Aws
    $web = Get-InstanceOf (Get-Instances) 'web'
    if ($web.State.Name -ne 'running') { throw 'The WEB instance must be running. Press START first.' }
    # Encrypted to a key that exists only in this window, so SSM history holds ciphertext only.
    $rsa = New-Object Security.Cryptography.RSACryptoServiceProvider 2048
    try {
        $pem = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes((Get-PublicKeyPem $rsa)))
        $reply = Invoke-HostCommand $web.InstanceId @(
            'set -e', 'key=$(mktemp)', "trap 'rm -f `"`$key`"' EXIT", "printf %s '$pem' | base64 -d > `"`$key`"",
            "openssl pkeyutl -encrypt -pubin -inkey `"`$key`" -pkeyopt rsa_padding_mode:oaep -pkeyopt rsa_oaep_md:sha1 -in '$LoginFile' | base64 -w0"
        ) 60
        # /bin/sh has no pipefail, so a failed read reaches here as empty output.
        if ($reply.Status -ne 'Success' -or -not $reply.Out.Trim()) { throw "Could not read the login record: $($reply.Err)" }
        $plain = [Text.Encoding]::UTF8.GetString($rsa.Decrypt([Convert]::FromBase64String($reply.Out.Trim()), $true)).Trim()
    } finally { $rsa.Dispose() }
    Write-Host ''
    Write-Line 'Web page login. Shown only in this window and not saved anywhere by this tool.' White
    $record = $null
    try { $record = $plain | ConvertFrom-Json } catch { }
    if ($record -and $record.PSObject.Properties['password']) {
        $name = @('username', 'user') | Where-Object { $record.PSObject.Properties[$_] } | Select-Object -First 1
        if ($name) { Write-Line "  User:     $($record.$name)" Green }
        Write-Line "  Password: $($record.password)" Green
    } else {
        Write-Line "  $plain" Green
    }
    $Result.status = 'READY'
    'SHOWN'
}

function Invoke-SetupCertificates {
    Write-Host ''
    Write-Line 'Browser-trusted certificates for the two Attune.more addresses come from Let''s Encrypt.' White
    Write-Line 'This creates one Let''s Encrypt account and a matching test account. No email or personal data is sent.'
    Write-Line 'The account key stays on this PC, encrypted for your Windows user. Certificates then renew on their own at START.'
    Write-Host ''
    Write-Line "Terms you accept by continuing: $(Get-AcmeTerms 'production')" Yellow
    $answer = Read-Host 'Do you accept these terms? Type yes to continue'
    if ($answer -ne 'yes') {
        Write-Line 'Nothing was created.' Yellow
        return 'SHOWN'
    }
    foreach ($authority in @('production', 'staging')) {
        [void](Register-AcmeAccount $authority)
        Write-Line "  $authority account ready." Green
    }
    Write-Line 'Done. Press START to issue the certificates.' Green
    'SHOWN'
}

function Invoke-Start {
    Connect-Aws
    Write-Step 'Checking the two instances'
    $before = Get-Instances
    Sync-HomeIp
    Write-Step 'Checking IONOS DNS access'
    $zone = $null
    try {
        $zone = Get-IonosZone
        Write-Line "  IONOS zone $($zone.name) reachable." Green
    } catch {
        # Stopped hosts get new addresses at START, so without DNS the pages could not be reached.
        if (@($before | Where-Object { $_.State.Name -ne 'running' })) {
            Add-Problem $_.Exception.Message
            Add-Problem 'Nothing was started, so nothing is charging.'
            return 'ERROR'
        }
        Add-Problem $_.Exception.Message
    }
    Write-Step 'Starting compute'
    Start-Compute
    $instances = Get-Instances
    Write-Step 'Updating the DNS records from the addresses AWS reports'
    if ($zone) { Sync-Dns $instances $zone }
    Add-Timing 'dnsWrittenSeconds'
    Write-Step 'Waiting for the operating systems and SSM'
    if (-not (Wait-Ssm 480)) {
        Add-Problem 'SSM did not come online within 8 minutes.'
        return 'ERROR'
    }
    Add-Timing 'ssmOnlineSeconds'
    Write-Line 'SSM is online on both instances.' Green
    Write-Step 'Checking origins and browser-trusted certificates'
    Sync-Origins
    if ($zone) { Sync-Certificates $zone }
    Add-Timing 'certificatesCheckedSeconds'
    Write-Step 'Starting Attune services'
    Start-Services
    Write-Step 'Verifying WEB + AI (backends, models, OpenAI, Chatterbox, Caddy)'
    $webTimeout = if ($Deep) { 1200 } else { 480 }
    $web = Wait-HostReady 'web' $webTimeout
    if ((-not $web -or -not $web.ready) -and (Restart-FailedUnits $web 'web')) { $web = Wait-HostReady 'web' 240 }
    Add-Timing 'webVerifiedSeconds'
    Write-HostReport $web 'web'
    Write-Step 'Verifying AAOS 15 (Android boot, APK, WebView, audio, camera bridge, mTLS)'
    $aaos = Wait-HostReady 'aaos' 720 25
    if ((-not $aaos -or -not $aaos.ready) -and (Restart-FailedUnits $aaos 'aaos')) { $aaos = Wait-HostReady 'aaos' 480 25 }
    Add-Timing 'aaosVerifiedSeconds'
    Write-HostReport $aaos 'aaos'
    $Result.checks = @($web, $aaos)
    Write-Step 'Checking the addresses from this PC'
    $instances = Get-Instances
    $Result.instances = @($instances | ForEach-Object { [ordered]@{ id = $_.InstanceId; state = $_.State.Name; publicIp = (Get-PublicIp $_) } })
    if ($zone) {
        try { Confirm-Dns $instances $zone } catch { Add-Problem "Could not confirm DNS: $($_.Exception.Message)" }
    }
    $rows = @(Test-PublicHttps $instances)
    $Result.urls = $rows
    Write-Urls $rows
    Add-AddressProblems $rows
    Set-CostEstimate $instances
    Write-Cost
    if ($OpenBrowser) { Open-Browser $rows }
    foreach ($report in @(@{ Role = 'WEB'; Data = $web }, @{ Role = 'AAOS'; Data = $aaos })) {
        if (-not $report.Data) { Add-Problem "$($report.Role): no readiness report." }
        elseif (-not $report.Data.ready) { Add-Problem "$($report.Role) failed: $(@($report.Data.failedRequired) -join ', ')" }
    }
    if ($Result.problems.Count -eq 0) { return 'READY' }
    'PARTIAL'
}

function Invoke-Stop {
    Connect-Aws
    $instances = Get-Instances
    $active = @($instances | Where-Object { $_.State.Name -notin @('stopped', 'stopping') } | ForEach-Object { $_.InstanceId })
    if ($active) {
        Write-Step 'Stopping both instances (normal shutdown, data on disk is kept)'
        foreach ($id in $active) {
            $reply = Invoke-Aws ec2 stop-instances --instance-ids $id --output json
            if (-not $reply.Ok) { Add-Problem "Stop request failed for ${id}: $($reply.Text)" }
        }
    } else {
        Write-Line 'Both instances were already stopped or stopping.'
    }
    Write-Step 'Waiting for AWS to confirm'
    $confirmed = Wait-State $TargetIds 'stopped' 480
    Add-Timing 'stoppedSeconds'
    $instances = Get-Instances
    $Result.instances = @($instances | ForEach-Object { [ordered]@{ id = $_.InstanceId; state = $_.State.Name } })
    foreach ($instance in $instances) {
        $name = ($Targets | Where-Object { $_.Id -eq $instance.InstanceId }).Name
        $color = if ($instance.State.Name -eq 'stopped') { 'Green' } else { 'Red' }
        Write-Line "  $name ($($instance.InstanceId)): $($instance.State.Name)" $color
    }
    Set-CostEstimate $instances
    Write-Cost
    if ($confirmed -and $Result.problems.Count -eq 0) { return 'STOPPED' }
    Add-Problem 'AWS did not confirm that both instances stopped. They may still be charging. Press STOP again or check the AWS console.'
    'ERROR'
}

function Invoke-Status {
    Connect-Aws
    $instances = Get-Instances
    $Result.instances = @($instances | ForEach-Object { [ordered]@{ id = $_.InstanceId; state = $_.State.Name; publicIp = (Get-PublicIp $_) } })
    Write-Step 'Instances'
    foreach ($instance in $instances) {
        $target = $Targets | Where-Object { $_.Id -eq $instance.InstanceId }
        $publicIp = Get-PublicIp $instance
        $ip = if ($publicIp) { "  public IP $publicIp" } else { '' }
        Write-Line "  $($target.Role.ToUpper()): $($target.Name) ($($target.Type)): $($instance.State.Name)$ip"
    }
    Set-CostEstimate $instances
    Write-Cost
    $states = @($instances | ForEach-Object { $_.State.Name } | Select-Object -Unique)
    if ($states.Count -eq 1 -and $states[0] -eq 'stopped') { return 'STOPPED' }
    if ($states.Count -ne 1 -or $states[0] -ne 'running') {
        Add-Problem "Instances are in a mixed or changing state: $($states -join ', ')."
        return 'PARTIAL'
    }
    Write-Step 'Both are running. Checking services (read-only)'
    $web = Get-HostReport 'web'
    Write-HostReport $web 'web'
    $aaos = Get-HostReport 'aaos'
    Write-HostReport $aaos 'aaos'
    $Result.checks = @($web, $aaos)
    $rows = @(Test-PublicHttps $instances)
    $Result.urls = $rows
    Write-Urls $rows
    Add-AddressProblems $rows
    foreach ($report in @(@{ Role = 'WEB'; Data = $web }, @{ Role = 'AAOS'; Data = $aaos })) {
        if (-not $report.Data) { Add-Problem "$($report.Role): no readiness report." }
        elseif (-not $report.Data.ready) { Add-Problem "$($report.Role) failed: $(@($report.Data.failedRequired) -join ', ')" }
    }
    if ($Result.problems.Count -eq 0) { return 'READY' }
    'PARTIAL'
}

$exitCode = 2
$host.UI.RawUI.WindowTitle = "Attune.more $($Action.ToUpper())"
Write-Host "ATTUNE.MORE $($Action.ToUpper())   $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor White
try {
    $status = switch ($Action) {
        'Start' { Invoke-Start }
        'Stop' { Invoke-Stop }
        'Status' { Invoke-Status }
        'ShowLogin' { Invoke-ShowLogin }
        'SetupCertificates' { Invoke-SetupCertificates }
    }
    $Result.status = $status
    if ($status -eq 'SHOWN') {
        # Nothing to summarize, and the report must not hold the login.
        if (-not $NoPause) { Write-Host ''; [void](Read-Host 'Press Enter to close this window') }
        exit 0
    }
    $message = switch ($status) {
        'READY' { 'All checks passed. Remember to press STOP when you finish.' }
        'STOPPED' { 'Both instances are confirmed stopped by AWS. Your data and settings are kept.' }
        'PARTIAL' { 'Some checks failed. Compute may be running and charging. See below.' }
        default { 'See below.' }
    }
    Write-Banner $status $message
    $exitCode = switch ($status) { 'READY' { 0 } 'STOPPED' { 0 } 'PARTIAL' { 1 } default { 2 } }
} catch {
    Add-Problem $_.Exception.Message
    $Result.status = 'ERROR'
    Write-Banner 'ERROR' 'The action did not complete. See below.'
}
foreach ($problem in $Result.problems) { Write-Line "  - $problem" Yellow }
$reportPath = Save-Result
Write-Line "Report: $reportPath" DarkGray
Write-Line ('Took {0:N0} minutes {1:N0} seconds.' -f [math]::Floor($Result.seconds / 60), ($Result.seconds % 60)) DarkGray
if (-not $NoPause) {
    Write-Host ''
    [void](Read-Host 'Press Enter to close this window')
}
exit $exitCode
