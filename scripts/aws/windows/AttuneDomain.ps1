<#
.SYNOPSIS
  IONOS DNS and browser-trusted certificate steps used by AttuneControl.ps1.

.DESCRIPTION
  Dot-sourced by AttuneControl.ps1. Standard Windows components only.

  DNS: writes A records for the two names in $DnsNames and nothing else. The only other
  writes are short-lived TXT records at _acme-challenge.<those names>, which exist while a
  certificate is being validated. A name already used by another service is reported,
  never overwritten.

  Certificates: the Security Groups keep port 443 limited to the operator and port 80 is
  closed, so a public CA cannot reach the hosts. Validation therefore uses ACME DNS-01.
  The account key and the IONOS key stay on this PC, encrypted for this Windows user. The
  certificate private keys stay on their hosts. Only certificate requests and public
  certificates travel.

  The IONOS key is read when needed, sent only in the X-API-Key header, and never logged.
#>

$script:IonosApi = 'https://api.hosting.ionos.com/dns/v1'
$script:DnsZone = 'sasmaz.digital'
$script:DnsNames = @('attunemore.sasmaz.digital', 'aaos.attunemore.sasmaz.digital')
$script:DnsTtl = 60
$script:PublicResolvers = @('1.1.1.1', '8.8.8.8')
# See $DataRoot in AttuneControl.ps1 for why this is not under AppData.
$script:DomainDataRoot = Join-Path $env:USERPROFILE 'AttuneMore'
# The owner saves this file here. Reading it from AppData is safe: only writes are redirected.
$script:IonosKeyPath = Join-Path $env:LOCALAPPDATA 'AttuneMore\secrets\ionos-dns.xml'
$script:AcmeDirectories = @{
    production = 'https://acme-v02.api.letsencrypt.org/directory'
    staging    = 'https://acme-staging-v02.api.letsencrypt.org/directory'
}
$script:AcmePollSeconds = 3
$script:DnsPollSeconds = 5
$script:IonosRetrySeconds = 4

Add-Type -AssemblyName System.Net.Http
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

function Get-Field($object, [string]$name) {
    if ($null -eq $object) { return $null }
    $field = $object.PSObject.Properties[$name]
    if ($field) { return $field.Value }
    $null
}

function Invoke-Http {
    param([string]$Method, [string]$Url, [hashtable]$Headers = @{}, [string]$Body, [string]$ContentType = 'application/json', [int]$TimeoutSeconds = 30)
    $client = New-Object Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromSeconds($TimeoutSeconds)
    $request = New-Object Net.Http.HttpRequestMessage((New-Object Net.Http.HttpMethod($Method)), $Url)
    try {
        # IONOS answers 503 to a request with no User-Agent, and ACME asks clients to send one.
        [void]$request.Headers.TryAddWithoutValidation('User-Agent', 'AttuneMore-Control/1.0')
        foreach ($name in $Headers.Keys) { [void]$request.Headers.TryAddWithoutValidation($name, [string]$Headers[$name]) }
        if ($PSBoundParameters.ContainsKey('Body')) {
            $request.Content = New-Object Net.Http.StringContent($Body, [Text.Encoding]::UTF8)
            $request.Content.Headers.ContentType = [Net.Http.Headers.MediaTypeHeaderValue]::Parse($ContentType)
        }
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        $text = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $found = @{}
        foreach ($pair in $response.Headers) { $found[$pair.Key] = ($pair.Value -join ',') }
        [pscustomobject]@{ Code = [int]$response.StatusCode; Text = $text; Headers = $found }
    } catch {
        # Network failures only. A status of 0 means no answer arrived. The message never holds request headers.
        $inner = $_.Exception
        while ($inner.InnerException) { $inner = $inner.InnerException }
        [pscustomobject]@{ Code = 0; Text = $inner.Message; Headers = @{} }
    } finally {
        $request.Dispose()
        $client.Dispose()
    }
}

# --- IONOS ---------------------------------------------------------------------------------------

function Get-IonosSetupHelp {
    $path = $script:IonosKeyPath
    "Create or renew the key in the IONOS developer portal, then save it as this Windows user: Get-Credential -UserName '<public prefix>' -Message 'IONOS API secret' | Export-Clixml '$path'"
}

function Get-IonosKey {
    $path = $script:IonosKeyPath
    if (-not (Test-Path -LiteralPath $path)) { throw "The IONOS key file is missing: $path. $(Get-IonosSetupHelp)" }
    try {
        $credential = Import-Clixml -LiteralPath $path
        $prefix = $credential.UserName
        $secret = $credential.GetNetworkCredential().Password
    } catch {
        throw "The IONOS key file could not be opened: $path. It opens only for the Windows user who saved it, on this PC. $(Get-IonosSetupHelp)"
    }
    if ([string]::IsNullOrWhiteSpace($prefix) -or [string]::IsNullOrWhiteSpace($secret)) {
        throw "The IONOS key file is incomplete: $path. $(Get-IonosSetupHelp)"
    }
    "$prefix.$secret"
}

function Invoke-Ionos([string]$method, [string]$path, [string]$body) {
    $key = Get-IonosKey
    $headers = @{ 'X-API-Key' = $key; Accept = 'application/json' }
    $attempts = if ($method -eq 'GET') { 5 } else { 1 }
    $last = $null
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        $arguments = @{ Method = $method; Url = $script:IonosApi + $path; Headers = $headers }
        if ($body) { $arguments.Body = $body }
        $last = Invoke-Http @arguments
        if ($last.Code -ge 200 -and $last.Code -lt 300) {
            if ([string]::IsNullOrWhiteSpace($last.Text)) { return $null }
            return ($last.Text | ConvertFrom-Json)
        }
        if ($last.Code -in @(401, 403)) {
            throw "IONOS refused the API key (HTTP $($last.Code)). It may have expired or been revoked. $(Get-IonosSetupHelp)"
        }
        if ($last.Code -ne 0 -and $last.Code -ne 429 -and $last.Code -lt 500) { break }
        if ($attempt -lt $attempts) { Start-Sleep -Seconds ($script:IonosRetrySeconds * $attempt) }
    }
    $detail = ([string]$last.Text).Replace($key, '***')
    # Outages answer with an HTML page, which says nothing useful here.
    if ($detail -match '<html') { $detail = 'the service is temporarily unavailable' }
    if ($detail.Length -gt 240) { $detail = $detail.Substring(0, 240) }
    if ($last.Code -eq 0) { throw "IONOS could not be reached: $detail" }
    throw "IONOS API error on $method (HTTP $($last.Code)): $detail"
}

function Get-IonosZone {
    $zone = @(Invoke-Ionos 'GET' '/zones') | ForEach-Object { $_ } | Where-Object { $_.name -eq $script:DnsZone } | Select-Object -First 1
    if (-not $zone) { throw "The IONOS account has no zone named $($script:DnsZone)." }
    $zone
}

function Get-IonosRecords([string]$zoneId, [string]$name) {
    $reply = Invoke-Ionos 'GET' "/zones/$zoneId`?recordName=$name"
    @(Get-Field $reply 'records') | ForEach-Object { $_ } | Where-Object { $_ -and $_.name -eq $name }
}

function Get-AuthoritativeServers([string]$zoneId) {
    $reply = Invoke-Ionos 'GET' "/zones/$zoneId`?recordName=$($script:DnsZone)&recordType=NS"
    @(@(Get-Field $reply 'records') | ForEach-Object { $_ } | Where-Object { $_ -and $_.type -eq 'NS' } | ForEach-Object { $_.content })
}

function Read-DomainState {
    $path = Join-Path $script:DomainDataRoot 'dns-records.json'
    $state = @{}
    if (Test-Path -LiteralPath $path) {
        $saved = (Get-Content -LiteralPath $path -Raw -Encoding UTF8) | ConvertFrom-Json
        foreach ($property in $saved.PSObject.Properties) { $state[$property.Name] = $property.Value }
    }
    $state
}

function Save-DomainState($state) {
    New-Item -ItemType Directory -Force -Path $script:DomainDataRoot | Out-Null
    [IO.File]::WriteAllText((Join-Path $script:DomainDataRoot 'dns-records.json'), ($state | ConvertTo-Json -Depth 4), (New-Object Text.UTF8Encoding($false)))
}

# Decides only; touches nothing. An A record this tool did not create may belong to another service.
function Get-ARecordPlan([string]$name, [string]$ip, $records, [string]$ownedId) {
    $records = @($records | Where-Object { $_ })
    $others = @($records | Where-Object { $_.type -ne 'A' })
    if ($others) {
        return [pscustomobject]@{ Action = 'conflict'; Id = $null; Reason = "$name already has other records: $(@($others | ForEach-Object { $_.type + ' ' + $_.content }) -join ', ')" }
    }
    if ($records.Count -gt 1) {
        return [pscustomobject]@{ Action = 'conflict'; Id = $null; Reason = "$name already has $($records.Count) A records: $(@($records | ForEach-Object { $_.content }) -join ', ')" }
    }
    if ($records.Count -eq 0) { return [pscustomobject]@{ Action = 'create'; Id = $null; Reason = $null } }
    $record = $records[0]
    $disabled = [bool](Get-Field $record 'disabled')
    if ($record.content -eq $ip -and -not $disabled) { return [pscustomobject]@{ Action = 'none'; Id = $record.id; Reason = $null } }
    if ($ownedId -and $record.id -eq $ownedId) { return [pscustomobject]@{ Action = 'update'; Id = $record.id; Reason = $null } }
    [pscustomobject]@{ Action = 'conflict'; Id = $record.id; Reason = "$name already points to $($record.content), and this tool did not create that record" }
}

function Assert-PublishableIp([string]$ip, [string]$homeIp) {
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($ip, [ref]$parsed) -or $parsed.AddressFamily -ne 'InterNetwork') {
        throw "Refusing to publish '$ip': it is not an IPv4 address."
    }
    $b = $parsed.GetAddressBytes()
    $private = $b[0] -in @(0, 10, 127) -or ($b[0] -eq 100 -and $b[1] -ge 64 -and $b[1] -le 127) -or ($b[0] -eq 169 -and $b[1] -eq 254) -or
        ($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31) -or ($b[0] -eq 192 -and $b[1] -eq 168) -or $b[0] -ge 224
    if ($private) { throw "Refusing to publish $ip`: it is not a public address." }
    if ($homeIp -and $ip -eq $homeIp) { throw "Refusing to publish $ip`: that is this PC's own address, not an EC2 address." }
}

# The IP must come from AWS for the exact instance, and $homeIp is this PC's address when known.
function Sync-DnsRecord([string]$zoneId, [string]$name, [string]$ip, [string]$homeIp) {
    if ($name -notin $script:DnsNames) { throw "Refusing to write DNS for $name`: not an authorized name." }
    Assert-PublishableIp $ip $homeIp
    $lastError = $null
    for ($attempt = 1; $attempt -le 3; $attempt++) {
        try {
            $state = Read-DomainState
            $owned = [string](Get-Field $state[$name] 'id')
            $plan = Get-ARecordPlan $name $ip (Get-IonosRecords $zoneId $name) $owned
            if ($plan.Action -eq 'conflict') { throw [InvalidOperationException]::new($plan.Reason) }
            if ($plan.Action -eq 'none') { return 'unchanged' }
            if ($plan.Action -eq 'create') {
                $body = ConvertTo-Json -InputObject @(@{ name = $name; type = 'A'; content = $ip; ttl = $script:DnsTtl; disabled = $false }) -Depth 3
                $created = @(Invoke-Ionos 'POST' "/zones/$zoneId/records" $body) | ForEach-Object { $_ } | Select-Object -First 1
                $state[$name] = @{ id = $created.id }
                Save-DomainState $state
            } else {
                $body = @{ content = $ip; ttl = $script:DnsTtl; disabled = $false } | ConvertTo-Json
                [void](Invoke-Ionos 'PUT' "/zones/$zoneId/records/$($plan.Id)" $body)
            }
            $after = Get-ARecordPlan $name $ip (Get-IonosRecords $zoneId $name) ([string](Get-Field (Read-DomainState)[$name] 'id'))
            if ($after.Action -ne 'none') { throw "IONOS did not keep the record for $name." }
            return $(if ($plan.Action -eq 'create') { 'created' } else { 'updated' })
        } catch [InvalidOperationException] {
            throw
        } catch {
            $lastError = $_
            if ("$lastError" -match 'refused the API key|key file') { throw }
            if ($attempt -lt 3) { Start-Sleep -Seconds (3 * $attempt) }
        }
    }
    throw $lastError
}

# --- Resolving -----------------------------------------------------------------------------------

function Get-DnsAnswer([string]$name, [string]$type, [string]$server) {
    $arguments = @{ Name = $name; Type = $type; DnsOnly = $true; NoHostsFile = $true; QuickTimeout = $true; ErrorAction = 'Stop' }
    if ($server) { $arguments.Server = $server }
    try { $rows = @(Resolve-DnsName @arguments) } catch { return @() }
    if ($type -eq 'TXT') { return @($rows | Where-Object { "$($_.Type)" -eq 'TXT' } | ForEach-Object { $_.Strings -join '' }) }
    @($rows | Where-Object { "$($_.Type)" -eq $type -and $_.Name -eq $name } | ForEach-Object { $_.IPAddress })
}

function Get-SystemAnswer([string]$name) {
    try { @([Net.Dns]::GetHostAddresses($name) | ForEach-Object { $_.IPAddressToString }) } catch { @() }
}

function Wait-DnsAnswer([string]$name, [string]$type, [string]$expected, [string[]]$servers, [int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    do {
        $missing = @($servers | Where-Object { (Get-DnsAnswer $name $type $_) -notcontains $expected })
        if (-not $missing) { return $true }
        Start-Sleep -Seconds $script:DnsPollSeconds
    } while ((Get-Date) -lt $deadline)
    $false
}

function Confirm-Hostname([string]$name, [string]$ip, [string[]]$authoritative, [int]$seconds = 180) {
    $authorityOk = Wait-DnsAnswer $name 'A' $ip $authoritative $seconds
    $publicOk = @($script:PublicResolvers | Where-Object { (Get-DnsAnswer $name 'A' $_) -contains $ip }).Count
    $deadline = (Get-Date).AddSeconds($(if ($authorityOk) { $seconds } else { 0 }))
    $system = @()
    do {
        & ipconfig.exe /flushdns | Out-Null
        $system = @(Get-SystemAnswer $name)
        if ($system.Count -eq 1 -and $system[0] -eq $ip) { break }
        Start-Sleep -Seconds $script:DnsPollSeconds
    } while ((Get-Date) -lt $deadline)
    [ordered]@{
        name = $name; intended = $ip; authoritative = [bool]$authorityOk; publicResolversAgreeing = $publicOk
        thisPcAnswer = ($system -join ','); thisPcOk = ($system.Count -eq 1 -and $system[0] -eq $ip)
    }
}

# --- ACME DNS-01 ---------------------------------------------------------------------------------

function ConvertTo-Base64Url([byte[]]$bytes) { [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_') }
function ConvertFrom-Base64Url([string]$text) {
    $padded = $text.Replace('-', '+').Replace('_', '/')
    [Convert]::FromBase64String($padded + ('=' * ((4 - $padded.Length % 4) % 4)))
}
function ConvertTo-Utf8Base64Url([string]$text) { ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($text)) }
function Get-Sha256Base64Url([string]$text) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { ConvertTo-Base64Url $sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($text)) } finally { $sha.Dispose() }
}

function Get-AcmeAccountPath([string]$authority) { Join-Path $script:DomainDataRoot "secrets\acme-$authority-account.xml" }

function Get-AcmeSetupHelp {
    $tool = Join-Path $script:DomainDataRoot 'bin\AttuneControl.ps1'
    "Run this once yourself, because it accepts the certificate authority's terms: powershell -NoProfile -ExecutionPolicy Bypass -File `"$tool`" -Action SetupCertificates"
}

function New-AcmeSession([string]$authority) {
    $directory = Invoke-Http -Method 'GET' -Url $script:AcmeDirectories[$authority]
    if ($directory.Code -ne 200) { throw "The certificate authority could not be reached (HTTP $($directory.Code))." }
    [pscustomobject]@{ Authority = $authority; Directory = ($directory.Text | ConvertFrom-Json); Nonce = $null; Key = $null; Kid = $null; Jwk = $null; Thumbprint = $null }
}

function Set-AcmeKey($session, $parameters) {
    $session.Key = [Security.Cryptography.ECDsa]::Create($parameters)
    $x = ConvertTo-Base64Url $parameters.Q.X
    $y = ConvertTo-Base64Url $parameters.Q.Y
    $session.Jwk = [ordered]@{ crv = 'P-256'; kty = 'EC'; x = $x; y = $y }
    # RFC 7638: members in this order, no whitespace.
    $session.Thumbprint = Get-Sha256Base64Url ('{"crv":"P-256","kty":"EC","x":"' + $x + '","y":"' + $y + '"}')
}

function Read-AcmeAccount($session) {
    $path = Get-AcmeAccountPath $session.Authority
    if (-not (Test-Path -LiteralPath $path)) { throw "No certificate account exists on this PC. $(Get-AcmeSetupHelp)" }
    try {
        $saved = (Import-Clixml -LiteralPath $path).GetNetworkCredential().Password | ConvertFrom-Json
    } catch {
        throw "The certificate account file could not be opened: $path. It opens only for the Windows user who saved it. $(Get-AcmeSetupHelp)"
    }
    $parameters = New-Object Security.Cryptography.ECParameters
    $parameters.Curve = [Security.Cryptography.ECCurve+NamedCurves]::nistP256
    $point = New-Object Security.Cryptography.ECPoint
    $point.X = ConvertFrom-Base64Url $saved.x
    $point.Y = ConvertFrom-Base64Url $saved.y
    $parameters.Q = $point
    $parameters.D = ConvertFrom-Base64Url $saved.d
    Set-AcmeKey $session $parameters
    $session.Kid = $saved.kid
}

function Get-AcmeNonce($session) {
    $reply = Invoke-Http -Method 'HEAD' -Url $session.Directory.newNonce
    $nonce = $reply.Headers['Replay-Nonce']
    if (-not $nonce) { throw "The certificate authority gave no nonce (HTTP $($reply.Code))." }
    $session.Nonce = $nonce
}

# $payload is JSON text. $null sends a POST-as-GET, whose payload is empty by definition.
function Invoke-Acme($session, [string]$url, $payload) {
    for ($attempt = 1; $attempt -le 4; $attempt++) {
        if (-not $session.Nonce) { Get-AcmeNonce $session }
        $protected = [ordered]@{ alg = 'ES256'; nonce = $session.Nonce; url = $url }
        if ($session.Kid) { $protected.kid = $session.Kid } else { $protected.jwk = $session.Jwk }
        $session.Nonce = $null
        $head = ConvertTo-Utf8Base64Url ($protected | ConvertTo-Json -Compress -Depth 3)
        $body = if ($null -eq $payload) { '' } else { ConvertTo-Utf8Base64Url $payload }
        $signature = ConvertTo-Base64Url $session.Key.SignData([Text.Encoding]::ASCII.GetBytes("$head.$body"), [Security.Cryptography.HashAlgorithmName]::SHA256)
        $envelope = [ordered]@{ protected = $head; payload = $body; signature = $signature } | ConvertTo-Json -Compress
        $reply = Invoke-Http -Method 'POST' -Url $url -Body $envelope -ContentType 'application/jose+json' -TimeoutSeconds 60
        if ($reply.Headers['Replay-Nonce']) { $session.Nonce = $reply.Headers['Replay-Nonce'] }
        $json = $null
        if ($reply.Text -and $reply.Text.TrimStart().StartsWith('{')) { try { $json = $reply.Text | ConvertFrom-Json } catch { } }
        $problem = [string](Get-Field $json 'type')
        if ($reply.Code -in @(0, 429, 500, 502, 503) -or $problem -like '*:badNonce') {
            if ($attempt -lt 4) { Start-Sleep -Seconds ($attempt * 2); continue }
        }
        return [pscustomobject]@{ Code = $reply.Code; Json = $json; Text = $reply.Text; Location = $reply.Headers['Location'] }
    }
}

function Assert-AcmeOk($reply, [string]$step) {
    if ($reply.Code -ge 200 -and $reply.Code -lt 300) { return }
    $detail = Get-Field $reply.Json 'detail'
    if (-not $detail) { $detail = "HTTP $($reply.Code)" }
    throw "The certificate authority refused $step`: $detail"
}

function Get-AcmeTerms([string]$authority) {
    $session = New-AcmeSession $authority
    Get-Field (Get-Field $session.Directory 'meta') 'termsOfService'
}

# Registers an account with no email or other personal data. Only -Action SetupCertificates may call this.
function Register-AcmeAccount([string]$authority) {
    $session = New-AcmeSession $authority
    $ecdsa = [Security.Cryptography.ECDsa]::Create([Security.Cryptography.ECCurve+NamedCurves]::nistP256)
    try { $parameters = $ecdsa.ExportParameters($true) } finally { $ecdsa.Dispose() }
    Set-AcmeKey $session $parameters
    $reply = Invoke-Acme $session $session.Directory.newAccount '{"termsOfServiceAgreed":true}'
    Assert-AcmeOk $reply 'the new account'
    $document = @{ x = ConvertTo-Base64Url $parameters.Q.X; y = ConvertTo-Base64Url $parameters.Q.Y; d = ConvertTo-Base64Url $parameters.D; kid = $reply.Location } | ConvertTo-Json -Compress
    New-Item -ItemType Directory -Force -Path (Join-Path $script:DomainDataRoot 'secrets') | Out-Null
    New-Object Management.Automation.PSCredential('acme', (ConvertTo-SecureString $document -AsPlainText -Force)) |
        Export-Clixml -LiteralPath (Get-AcmeAccountPath $authority)
    $reply.Location
}

function Add-ChallengeRecord([string]$zoneId, [string]$name, [string]$value) {
    if ($name -notin $script:DnsNames) { throw "Refusing to write DNS for $name`: not an authorized name." }
    $recordName = "_acme-challenge.$name"
    $body = ConvertTo-Json -InputObject @(@{ name = $recordName; type = 'TXT'; content = $value; ttl = $script:DnsTtl; disabled = $false }) -Depth 3
    $created = @(Invoke-Ionos 'POST' "/zones/$zoneId/records" $body) | ForEach-Object { $_ } | Select-Object -First 1
    $created.id
}

function Remove-ChallengeRecord([string]$zoneId, [string]$name, [string]$id) {
    # Deletes only the record this run created, and only if it is still a challenge record.
    $record = @(Get-IonosRecords $zoneId "_acme-challenge.$name") | Where-Object { $_.id -eq $id -and $_.type -eq 'TXT' }
    if ($record) { [void](Invoke-Ionos 'DELETE' "/zones/$zoneId/records/$id" $null) }
}

function Wait-AcmeStatus($session, [string]$url, [string[]]$done, [int]$seconds = 180) {
    $deadline = (Get-Date).AddSeconds($seconds)
    do {
        $reply = Invoke-Acme $session $url $null
        Assert-AcmeOk $reply 'the status request'
        if ($reply.Json.status -in $done) { return $reply.Json }
        Start-Sleep -Seconds $script:AcmePollSeconds
    } while ((Get-Date) -lt $deadline)
    throw "The certificate authority did not finish in time (status: $($reply.Json.status))."
}

function Get-CsrDer([string]$pem) {
    $inner = ($pem -replace '-----[A-Z ]+-----', '') -replace '\s', ''
    ConvertTo-Base64Url ([Convert]::FromBase64String($inner))
}

# Returns the certificate chain as PEM. The challenge record is removed whatever happens.
function New-PublicCertificate([string]$name, [string]$csrPem, [string]$authority, [string]$zoneId, [string[]]$authoritative) {
    if ($name -notin $script:DnsNames) { throw "Refusing to request a certificate for $name`: not an authorized name." }
    $session = New-AcmeSession $authority
    Read-AcmeAccount $session
    $order = Invoke-Acme $session $session.Directory.newOrder ('{"identifiers":[{"type":"dns","value":"' + $name + '"}]}')
    Assert-AcmeOk $order 'the certificate order'
    $orderUrl = $order.Location
    foreach ($authorization in @($order.Json.authorizations)) {
        $reply = Invoke-Acme $session $authorization $null
        Assert-AcmeOk $reply 'the authorization'
        if ($reply.Json.status -eq 'valid') { continue }
        $challenge = @($reply.Json.challenges) | Where-Object { $_.type -eq 'dns-01' } | Select-Object -First 1
        if (-not $challenge) { throw 'The certificate authority did not offer DNS validation.' }
        $value = Get-Sha256Base64Url ($challenge.token + '.' + $session.Thumbprint)
        $recordId = Add-ChallengeRecord $zoneId $name $value
        try {
            if (-not (Wait-DnsAnswer "_acme-challenge.$name" 'TXT' $value $authoritative 240)) {
                throw "The validation record for $name did not reach the name servers in time."
            }
            $started = Invoke-Acme $session $challenge.url '{}'
            Assert-AcmeOk $started 'the validation request'
            $result = Wait-AcmeStatus $session $authorization @('valid', 'invalid')
            if ($result.status -ne 'valid') {
                $failed = @($result.challenges) | Where-Object { $_.type -eq 'dns-01' } | Select-Object -First 1
                throw "Validation of $name failed: $(Get-Field (Get-Field $failed 'error') 'detail')"
            }
        } finally {
            Remove-ChallengeRecord $zoneId $name $recordId
        }
    }
    $final = Invoke-Acme $session $order.Json.finalize ('{"csr":"' + (Get-CsrDer $csrPem) + '"}')
    Assert-AcmeOk $final 'the certificate request'
    $issued = Wait-AcmeStatus $session $orderUrl @('valid', 'invalid')
    if ($issued.status -ne 'valid') { throw "The certificate order for $name failed: $(Get-Field (Get-Field $issued 'error') 'detail')" }
    $download = Invoke-Acme $session $issued.certificate $null
    Assert-AcmeOk $download 'the certificate download'
    if ($download.Text -notmatch 'BEGIN CERTIFICATE') { throw 'The certificate download held no certificate.' }
    $download.Text
}
