#Requires -Version 5.1
<#
.SYNOPSIS
    Record what a Windows endpoint can reach on an Amazon FSx for NetApp ONTAP file system.

.DESCRIPTION
    The Windows counterpart of probe-endpoint.sh, emitting the same JSON shape so two records line up
    field by field. It creates nothing on the file system, and unmounts anything it mounts.

    EVERY VALUE IS MASKED AS IT IS WRITTEN. Computer names, IPv4 host octets, file system and SVM
    identifiers, 12-digit account numbers, the iSCSI qualified name's host part and the user profile
    path are replaced before they reach the file. Masking a record afterwards leaves the unmasked
    version in whatever it was copied into first, so this script never produces one.

    Two findings here have no equivalent on the other endpoints, and both come from the AWS iSCSI
    procedure being written for an EC2 instance running Windows Server:

      - whether Install-WindowsFeature exists at all, which is how that procedure enables MPIO
      - the local address the procedure passes as InitiatorPortalAddress, which over a VPN is
        assigned per connection rather than fixed

.PARAMETER SvmDnsName
    SVM DNS name. Resolution is checked with the system resolver, which is what a mount uses.

.PARAMETER SmbIpAddress
    SVM SMB address. TCP 445 is checked.

.PARAMETER NfsIpAddress
    SVM NFS address. TCP 2049, 111 and 635 are checked.

.PARAMETER IscsiIpAddress
    SVM iSCSI address. TCP 3260 is checked.

.PARAMETER ShareName
    SMB share name, used only with -TryMount.

.PARAMETER SmbUser
    Local SMB user as SERVER\user. Used only with -TryMount, and only to prefill the credential
    prompt: the password is never a parameter, because a parameter is visible in the command line of
    a running process and in PowerShell history.

.PARAMETER S3AccessPoint
    FSx for ONTAP S3 Access Point alias or ARN. A ListObjectsV2 is attempted with the AWS CLI.

.PARAMETER TryMount
    Attempt the SMB mount, then remove it. Prompts for the password.

.PARAMETER OutFile
    Write the JSON here instead of to the pipeline.

.EXAMPLE
    .\probe-endpoint.ps1 -SvmDnsName svm-x.fs-y.fsx.ap-northeast-1.amazonaws.com `
        -SmbIpAddress 10.0.1.10 -NfsIpAddress 10.0.1.10 -IscsiIpAddress 10.0.1.11 `
        -OutFile windows-probe.json
#>
[CmdletBinding()]
param(
    [string] $SvmDnsName,
    [string] $SmbIpAddress,
    [string] $NfsIpAddress,
    [string] $IscsiIpAddress,
    [string] $ShareName,
    [string] $SmbUser,
    [string] $S3AccessPoint,
    [switch] $TryMount,
    [string] $OutFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$computerName = $env:COMPUTERNAME
$profilePath = $env:USERPROFILE

function Convert-ToMaskedText {
    <#
        .SYNOPSIS
            Replace identifying values in a string before it is written.
        .DESCRIPTION
            The computer name is replaced before addresses, because on many machines it contains one.
            Addresses keep their first two octets so records from different networks stay
            distinguishable, and lose the rest so neither identifies a host.
    #>
    [OutputType([string])]
    param([AllowEmptyString()] [string] $Text)

    if ([string]::IsNullOrEmpty($Text)) { return '' }
    $masked = $Text

    if (-not [string]::IsNullOrEmpty($computerName)) {
        $masked = $masked -replace [regex]::Escape($computerName), '<client-hostname>'
    }
    if (-not [string]::IsNullOrEmpty($profilePath)) {
        $masked = $masked -replace [regex]::Escape($profilePath), '<home>'
    }

    $masked = [regex]::Replace($masked, '\b(?:\d{1,3}\.){3}\d{1,3}\b', {
            param($match)
            $addr = $match.Value
            if ($addr -in @('0.0.0.0', '127.0.0.1', '255.255.255.255')) { return $addr }
            $parts = $addr.Split('.')
            '{0}.{1}.x.x' -f $parts[0], $parts[1]
        })

    $masked = $masked -replace '\bfs-[0-9a-f]{8,}\b', 'fs-0123456789abcdef0'
    $masked = $masked -replace '\bsvm-[0-9a-f]{8,}\b', 'svm-0123456789abcdef0'
    $masked = $masked -replace '\bFSxId[0-9a-f]{8,}\b', 'FSxId0123456789abc'
    $masked = $masked -replace '\b\d{12}\b', '123456789012'
    $masked = $masked -replace '(iqn\.\d{4}-\d{2}\.[^:\s]+):\S+', '$1:<client-hostname>'
    return $masked
}

function Get-TcpProbeResult {
    <#
        .SYNOPSIS
            Report whether a TCP port accepts a connection.
        .DESCRIPTION
            A raw TcpClient is used rather than Test-NetConnection so the result set matches the
            other endpoints exactly: open, refused, timeout, unresolved.
    #>
    [OutputType([string])]
    param([AllowEmptyString()] [string] $HostName, [int] $Port)

    if ([string]::IsNullOrEmpty($HostName)) { return 'not_tested' }
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(4000, $false)) { return 'timeout' }
        $client.EndConnect($async)
        return 'open'
    } catch [System.Net.Sockets.SocketException] {
        switch ($_.Exception.SocketErrorCode) {
            'ConnectionRefused' { return 'refused' }
            'HostNotFound' { return 'unresolved' }
            default { return "error:$($_.Exception.SocketErrorCode)" }
        }
    } catch {
        return "error:$($_.Exception.GetType().Name)"
    } finally {
        $client.Close()
    }
}

function Get-NameResolutionResult {
    <#
        .SYNOPSIS
            Resolve a name through the system resolver, which is what a mount uses.
    #>
    [OutputType([string])]
    param([AllowEmptyString()] [string] $Name)

    if ([string]::IsNullOrEmpty($Name)) { return 'not_tested' }
    try {
        $addresses = [System.Net.Dns]::GetHostAddresses($Name)
        $first = $addresses | Where-Object { $_.AddressFamily -eq 'InterNetwork' } | Select-Object -First 1
        if ($null -eq $first) { return 'unresolved:no_ipv4_answer' }
        return "resolved:$($first.IPAddressToString)"
    } catch {
        return "unresolved:$($_.Exception.Message)"
    }
}

# ---------------------------------------------------------------- environment

$osInfo = Get-CimInstance -ClassName Win32_OperatingSystem
# ProductType 1 is a client SKU (Windows 10, Windows 11); 2 and 3 are domain controller and server.
# This single field decides whether the AWS iSCSI procedure applies unmodified, because
# Install-WindowsFeature belongs to the ServerManager module and ships only on a server.
$productType = $osInfo.ProductType
$skuKind = if ($productType -eq 1) { 'client' } else { 'server' }

$installWindowsFeatureAvailable =
    $null -ne (Get-Command -Name Install-WindowsFeature -ErrorAction SilentlyContinue)

$mpioState = 'not_tested'
try {
    $feature = Get-WindowsOptionalFeature -Online -FeatureName MultiPathIO -ErrorAction Stop
    $mpioState = [string] $feature.State
} catch {
    $mpioState = "query_failed:$($_.Exception.GetType().Name)"
}

$iscsiService = 'absent'
try {
    $svc = Get-Service -Name MSiSCSI -ErrorAction Stop
    $iscsiService = "$($svc.Status)/$($svc.StartType)"
} catch {
    $iscsiService = 'absent'
}

$initiatorName = 'none'
try {
    $port = Get-InitiatorPort -ErrorAction Stop | Select-Object -First 1
    if ($null -ne $port) { $initiatorName = [string] $port.NodeAddress }
} catch {
    $initiatorName = 'get_initiatorport_unavailable'
}

# The address the AWS procedure passes as InitiatorPortalAddress. Recorded because over a VPN it is
# assigned when the tunnel comes up, so a script that hard-codes it works once.
$localAddresses = @()
try {
    $localAddresses = @(
        Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -ne '127.0.0.1' } |
            ForEach-Object { "$($_.InterfaceAlias)=$($_.IPAddress)" }
    )
} catch {
    $localAddresses = @("enumeration_failed:$($_.Exception.GetType().Name)")
}

# ---------------------------------------------------------------- probes

$dnsResult = Get-NameResolutionResult -Name $SvmDnsName
$smb445 = Get-TcpProbeResult -HostName $SmbIpAddress -Port 445
$nfs2049 = Get-TcpProbeResult -HostName $NfsIpAddress -Port 2049
$nfs111 = Get-TcpProbeResult -HostName $NfsIpAddress -Port 111
$nfs635 = Get-TcpProbeResult -HostName $NfsIpAddress -Port 635
$iscsi3260 = Get-TcpProbeResult -HostName $IscsiIpAddress -Port 3260

$s3Result = 'not_tested'
if (-not [string]::IsNullOrEmpty($S3AccessPoint)) {
    if ($null -ne (Get-Command -Name aws -ErrorAction SilentlyContinue)) {
        $awsOutput = & aws s3api list-objects-v2 --bucket $S3AccessPoint --max-items 1 2>&1
        if ($LASTEXITCODE -eq 0) {
            $s3Result = 'ok'
        } else {
            $joined = ($awsOutput | Out-String) -replace '\r?\n', ' '
            $s3Result = 'failed: ' + $joined.Substring(0, [Math]::Min(400, $joined.Length))
        }
    } else {
        $s3Result = 'aws_cli_absent'
    }
}

$smbMount = 'not_tested'
if ($TryMount -and -not [string]::IsNullOrEmpty($SmbIpAddress) -and
    -not [string]::IsNullOrEmpty($ShareName)) {
    $remotePath = "\\$SmbIpAddress\$ShareName"
    # Get-Credential prompts. The password is never a parameter and never reaches the command line,
    # where Get-Process and PowerShell history would both expose it.
    $credential = Get-Credential -Message "Password for $SmbUser on $remotePath" -UserName $SmbUser
    try {
        New-SmbMapping -RemotePath $remotePath -Credential $credential -ErrorAction Stop | Out-Null
        $smbMount = 'mounted'
        Remove-SmbMapping -RemotePath $remotePath -Force -ErrorAction SilentlyContinue
    } catch {
        $message = $_.Exception.Message -replace '\r?\n', ' '
        $smbMount = 'failed: ' + $message.Substring(0, [Math]::Min(400, $message.Length))
    }
}

# ---------------------------------------------------------------- record

$record = [ordered] @{
    schema      = 'fsxn-client-access-probe/1'
    recorded_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    environment = [ordered] @{
        os                  = 'Windows'
        os_version          = Convert-ToMaskedText -Text ("$($osInfo.Caption) build $($osInfo.BuildNumber)")
        kernel              = Convert-ToMaskedText -Text ([string] $osInfo.Version)
        arch                = [string] $env:PROCESSOR_ARCHITECTURE
        is_wsl              = $false
        wsl_networking_mode = 'not_applicable'
        wsl_version         = 'not_applicable'
        sku_kind            = $skuKind
    }
    windows_specific = [ordered] @{
        install_windowsfeature_available = $installWindowsFeatureAvailable
        multipathio_feature_state        = Convert-ToMaskedText -Text $mpioState
        msiscsi_service                  = Convert-ToMaskedText -Text $iscsiService
        local_ipv4_addresses             = @($localAddresses | ForEach-Object { Convert-ToMaskedText -Text $_ })
    }
    name_resolution = [ordered] @{
        svm_dns_queried = Convert-ToMaskedText -Text ($(if ($SvmDnsName) { $SvmDnsName } else { 'not_tested' }))
        result          = Convert-ToMaskedText -Text $dnsResult
    }
    reachability = [ordered] @{
        smb_445    = Convert-ToMaskedText -Text $smb445
        nfs_2049   = Convert-ToMaskedText -Text $nfs2049
        nfs_111    = Convert-ToMaskedText -Text $nfs111
        nfs_635    = Convert-ToMaskedText -Text $nfs635
        iscsi_3260 = Convert-ToMaskedText -Text $iscsi3260
    }
    block = [ordered] @{
        # Derived, not asserted. Writing 'iscsicli_builtin' unconditionally would make this field
        # agree with the expectation rather than with the machine, which is the one thing a record
        # meant for comparison must not do -- the macOS record earns its 'absent' by being looked up.
        initiator_tool   = if ($iscsiService -eq 'absent') { 'absent' } else { 'msiscsi_builtin' }
        initiator_name   = Convert-ToMaskedText -Text $initiatorName
        iscsi_tcp_module = 'not_applicable'
    }
    object = [ordered] @{
        access_point_list_objects = Convert-ToMaskedText -Text $s3Result
    }
    mounts = [ordered] @{
        nfs = 'not_tested'
        smb = Convert-ToMaskedText -Text $smbMount
    }
    notes = [ordered] @{
        masking            = 'Computer name, IPv4 host octets, file system and SVM identifiers, 12-digit account numbers, IQN host parts and the profile path are replaced at write time.'
        not_tested_meaning = 'A field reading not_tested was not attempted. It is not a failure.'
        throughput         = 'Deliberately absent. Measured over a VPN it would describe the tunnel and this endpoint own network rather than the file system.'
    }
}

$json = $record | ConvertTo-Json -Depth 6

if ([string]::IsNullOrEmpty($OutFile)) {
    Write-Output $json
} else {
    Set-Content -Path $OutFile -Value $json -Encoding UTF8
    Write-Verbose "wrote $OutFile"
}
