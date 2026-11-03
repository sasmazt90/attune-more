<#
.SYNOPSIS
  One-click START, STOP and STATUS for the two existing Attune.more EC2 instances.

.DESCRIPTION
  Never creates AWS resources or changes DNS. It only starts and stops the two
  known instances, runs read-only checks through SSM, restarts Attune services,
  and asks before allowing a new home IP on the existing Security Groups.

  Exit code: 0 READY or STOPPED, 1 PARTIAL, 2 ERROR.
#>
[CmdletBinding()]
param(
    [ValidateSet('Start', 'Stop', 'Status')][string]$Action = 'Status',
    [string]$AwsProfile = 'attune-desktop',
    [string]$LoginProfile = 'attune-operator',
    # Also hashes every model file and generates real Chatterbox speech. Adds several minutes.
    [switch]$Deep,
    [switch]$OpenBrowser,
    [switch]$NoPause,
    # For unattended runs: allow this PC's new public IP without asking.
    [switch]$AllowIpChange
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$Region = 'eu-central-1'
$Account = '798886013428'
$WebDomain = 'attune.sasmaz.digital'
$AaosDomain = 'aaos.sasmaz.digital'
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
$DataRoot = Join-Path $env:LOCALAPPDATA 'AttuneMore'
$ReportRoot = Join-Path $DataRoot 'reports'
$StartedAt = Get-Date
$Result = [ordered]@{
    action = $Action; startedAt = $StartedAt.ToUniversalTime().ToString('o'); status = 'ERROR'; identity = $null
    instances = @(); checks = @(); recoveries = @(); urls = @{}; cost = @{}; timings = [ordered]@{}; problems = @()
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

function Get-InstanceOf($instances, [string]$role) {
    $id = ($Targets | Where-Object { $_.Role -eq $role }).Id
    $instances | Where-Object { $_.InstanceId -eq $id }
}

function Get-RunningHours($instance, [datetime]$until) {
    $launch = ([datetime]$instance.LaunchTime).ToUniversalTime()
    [math]::Max(0, ($until.ToUniversalTime() - $launch).TotalHours)
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

function Get-HostScriptCommands([string]$role) {
    $bytes = [IO.File]::ReadAllBytes($HostScript)
    $memory = New-Object IO.MemoryStream
    $gzip = New-Object IO.Compression.GZipStream($memory, [IO.Compression.CompressionMode]::Compress)
    $gzip.Write($bytes, 0, $bytes.Length)
    $gzip.Close()
    $encoded = [Convert]::ToBase64String($memory.ToArray())
    $commands = @('set -e', 'target=$(mktemp /tmp/attune-host-ready.XXXXXX)')
    for ($at = 0; $at -lt $encoded.Length; $at += 3000) {
        $commands += "printf %s '" + $encoded.Substring($at, [math]::Min(3000, $encoded.Length - $at)) + "' >> `"`$target`""
    }
    $deepFlag = if ($Deep) { ' --deep' } else { '' }
    $commands += 'base64 -d "$target" | gunzip > "$target.py"'
    $commands += "python3 `"`$target.py`" --role $role$deepFlag"
    $commands += 'rm -f "$target" "$target.py"'
    $commands
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

function Test-PublicHttps($instances) {
    $rows = @()
    foreach ($pair in @(@{ Role = 'web'; Domain = $WebDomain }, @{ Role = 'aaos'; Domain = $AaosDomain })) {
        $ip = (Get-InstanceOf $instances $pair.Role).PublicIpAddress
        $resolved = $null
        try { $resolved = @([Net.Dns]::GetHostAddresses($pair.Domain) | ForEach-Object { $_.IPAddressToString }) } catch { }
        $dnsOk = $resolved -and ($resolved -contains $ip)
        # The certificate comes from the project's private CA, so this checks routing and
        # that unauthenticated callers are refused, not public certificate trust.
        $code = & curl.exe -sk --max-time 12 --resolve "$($pair.Domain):443:$ip" -o NUL -w '%{http_code}' "https://$($pair.Domain)/" 2>$null
        $rows += [ordered]@{ role = $pair.Role; publicIp = $ip; domain = $pair.Domain; dnsPointsHere = [bool]$dnsOk; unauthenticatedHttps = "$code" }
    }
    $rows
}

function Open-Browser($urls) {
    $browser = @("$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe", "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $browser) {
        Write-Line 'No Chrome or Edge found. Open the URLs above manually.' Yellow
        return
    }
    $rules = @($urls | ForEach-Object { "MAP $($_.domain) $($_.publicIp)" }) -join ','
    $profileDir = Join-Path $DataRoot 'browser-profile'
    $arguments = @("--user-data-dir=`"$profileDir`"", "--host-resolver-rules=`"$rules`"", '--no-first-run') + @($urls | ForEach-Object { "https://$($_.domain)/" })
    Start-Process -FilePath $browser -ArgumentList $arguments | Out-Null
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
        $routing = if ($row.dnsPointsHere) { 'DNS points here' } else { "DNS not set up yet, public IP $($row.publicIp)" }
        Write-Line "  $label https://$($row.domain)/   ($routing)"
    }
    if (@($rows | Where-Object { -not $_.dnsPointsHere })) {
        Write-Line '  Use the browser this tool opens. It maps these names to the current public IPs.' DarkGray
    }
}

function Invoke-Start {
    Connect-Aws
    Write-Step 'Checking the two instances'
    Sync-HomeIp
    Write-Step 'Starting compute'
    Start-Compute
    Write-Step 'Waiting for the operating systems and SSM'
    if (-not (Wait-Ssm 480)) {
        Add-Problem 'SSM did not come online within 8 minutes.'
        return 'ERROR'
    }
    Add-Timing 'ssmOnlineSeconds'
    Write-Line 'SSM is online on both instances.' Green
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
    $Result.instances = @($instances | ForEach-Object { [ordered]@{ id = $_.InstanceId; state = $_.State.Name; publicIp = $_.PublicIpAddress } })
    $rows = @(Test-PublicHttps $instances)
    $Result.urls = $rows
    Write-Urls $rows
    foreach ($row in $rows) {
        if ($row.unauthenticatedHttps -ne '401') { Add-Problem "$($row.domain) did not answer as expected from this PC (HTTP $($row.unauthenticatedHttps))." }
    }
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
    $Result.instances = @($instances | ForEach-Object { [ordered]@{ id = $_.InstanceId; state = $_.State.Name; publicIp = $_.PublicIpAddress } })
    Write-Step 'Instances'
    foreach ($instance in $instances) {
        $target = $Targets | Where-Object { $_.Id -eq $instance.InstanceId }
        $ip = if ($instance.PublicIpAddress) { "  public IP $($instance.PublicIpAddress)" } else { '' }
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
    }
    $Result.status = $status
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
