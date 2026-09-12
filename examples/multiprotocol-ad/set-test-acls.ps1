<#
.SYNOPSIS
  Set the three kinds of NTFS ACE the multiprotocol measurement needs, and record them.

.DESCRIPTION
  This writes the first of the three parts of the record. read-effective-permissions.sh writes the
  other two on the Linux side.

  Three ACE kinds are set, because they translate differently and the difference is the point:

    allow        A plain Allow ACE. It has a representation in POSIX mode bits, so this is the case
                 that is expected to survive translation and acts as the baseline.
    deny         An explicit Deny ACE. POSIX mode bits have no way to express a deny. An NFSv4 ACL
                 does, so whether it survives depends on which of the two the NFS client ends up
                 reading - which is why read-effective-permissions.sh records both.
    inherited    An inheritable ACE on a parent directory, with a child created afterwards so the
                 child's ACE arrives by inheritance rather than by being set. Inheritance is a
                 Windows-side mechanism; whether the resulting ACE looks the same from NFS as a
                 directly set one is not something the mode bits can show.

  Run this as an account that can change ACLs - normally a Domain Admins member. That is fine here:
  setting the permissions is administrative work. Reading them back is NOT: do that as an ordinary
  Active Directory user, because members of the file system administrators group bypass the
  evaluation being measured and every access succeeds.

.PARAMETER SharePath
  UNC path to the SMB share on the NTFS-security-style volume, for example
  \\CORPSRC.corp.example.com\ntfsshare
  The SVM's SMB endpoint is its NetBIOS name in the domain. Resolve it with:
    aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids svm-... `
      --query 'StorageVirtualMachines[0].Endpoints.Smb.DNSName'

.PARAMETER AdUser
  The Active Directory test user the ACEs apply to, as DOMAIN\user. It must not be a member of the
  group given as FileSystemAdministratorsGroup.

.PARAMETER OutFile
  Where to write the JSON record. Defaults to .\set-test-acls-record.json

.EXAMPLE
  .\set-test-acls.ps1 -SharePath \\CORPSRC.corp.example.com\ntfsshare -AdUser CORP\mpadtest
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SharePath,
    [Parameter(Mandatory = $true)][string]$AdUser,
    [string]$OutFile = '.\set-test-acls-record.json'
)

$ErrorActionPreference = 'Stop'

function Assert-Path {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "cannot reach $Path. Check that the SVM is joined to the domain (a join that failed " +
              "leaves the SVM in MISCONFIGURED and the stack still at CREATE_COMPLETE), that this " +
              "host is domain-joined, and that TCP 445 is open to the file system security group."
    }
}

Assert-Path -Path $SharePath

# Confirm the account exists before writing any ACE. An identity that does not resolve produces an
# ACE against a raw SID, which then reads back as an unresolvable entry on both sides and looks like
# a translation failure rather than a typo.
try {
    $resolved = (New-Object System.Security.Principal.NTAccount($AdUser)).Translate(
        [System.Security.Principal.SecurityIdentifier])
}
catch {
    throw "$AdUser does not resolve to a security identifier on this host. Check the account exists " +
          "and that this host is joined to the same domain."
}

Write-Host "== target =="
Write-Host ("share      : {0}" -f $SharePath)
Write-Host ("test user  : {0} ({1})" -f $AdUser, $resolved.Value)

# Setting the ACEs is administrative work, but reading them back must not be. Say so once here so the
# operator does not carry the same session into the measurement.
$isAdmin = ([Security.Principal.WindowsPrincipal] `
    [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host ("running as : {0}{1}" -f $env:USERNAME, $(if ($isAdmin) { ' (elevated)' } else { '' }))
Write-Host ''

$paths = @{
    allow     = Join-Path $SharePath 'allow'
    deny      = Join-Path $SharePath 'deny'
    inherited = Join-Path $SharePath 'inherited'
}

foreach ($p in $paths.Values) {
    if (-not (Test-Path -LiteralPath $p)) {
        New-Item -ItemType Directory -Path $p | Out-Null
        Write-Host ("created    : {0}" -f $p)
    }
    else {
        Write-Host ("exists     : {0}" -f $p)
    }
}

# A file inside each directory, so the record covers a file as well as a directory. ONTAP presents
# the two differently over NFS and a finding about one does not carry to the other.
foreach ($p in $paths.Values) {
    $f = Join-Path $p 'probe.txt'
    if (-not (Test-Path -LiteralPath $f)) {
        Set-Content -LiteralPath $f -Value 'multiprotocol permission probe' -Encoding UTF8
    }
}

Write-Host ''
Write-Host "== setting ACEs =="

# ------------------------------------------------------------------ allow

$acl = Get-Acl -LiteralPath $paths.allow
$allowAce = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $AdUser,
    [System.Security.AccessControl.FileSystemRights]::Modify,
    [System.Security.AccessControl.InheritanceFlags]::None,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow)
$acl.AddAccessRule($allowAce)
Set-Acl -LiteralPath $paths.allow -AclObject $acl
Write-Host ("allow      : Modify for {0}, not inheritable" -f $AdUser)

# ------------------------------------------------------------------ deny

# Read is allowed and Write is explicitly denied on the same directory. A bare Deny would be
# indistinguishable from having no ACE at all when read as mode bits, so the pairing is what makes
# the loss visible: if the NFS side shows read but not the denial, the denial did not survive.
$acl = Get-Acl -LiteralPath $paths.deny
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    $AdUser,
    [System.Security.AccessControl.FileSystemRights]::ReadAndExecute,
    [System.Security.AccessControl.InheritanceFlags]::None,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow)))
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    $AdUser,
    [System.Security.AccessControl.FileSystemRights]::Write,
    [System.Security.AccessControl.InheritanceFlags]::None,
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Deny)))
Set-Acl -LiteralPath $paths.deny -AclObject $acl
Write-Host ("deny       : Allow ReadAndExecute plus explicit Deny Write for {0}" -f $AdUser)

# ------------------------------------------------------------------ inherited

# The inheritable ACE goes on the parent first, and the child is created afterwards, so the child's
# ACE is genuinely inherited. Creating the child first and then setting the parent would leave the
# child with no ACE and the run would silently measure nothing.
$acl = Get-Acl -LiteralPath $paths.inherited
$acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule(
    $AdUser,
    [System.Security.AccessControl.FileSystemRights]::Modify,
    ([System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor
     [System.Security.AccessControl.InheritanceFlags]::ObjectInherit),
    [System.Security.AccessControl.PropagationFlags]::None,
    [System.Security.AccessControl.AccessControlType]::Allow)))
Set-Acl -LiteralPath $paths.inherited -AclObject $acl
Write-Host ("inherited  : Modify for {0}, ContainerInherit + ObjectInherit on the parent" -f $AdUser)

$child = Join-Path $paths.inherited 'child'
if (-not (Test-Path -LiteralPath $child)) {
    New-Item -ItemType Directory -Path $child | Out-Null
    Write-Host ("           : created {0} after the parent ACE, so its ACE is inherited" -f $child)
}
else {
    Write-Host ("           : {0} already existed. If it predates the parent ACE its ACE may not " -f $child)
    Write-Host  "             be inherited. Delete it and re-run to be sure."
}
Set-Content -LiteralPath (Join-Path $child 'probe.txt') `
    -Value 'multiprotocol permission probe' -Encoding UTF8

# ------------------------------------------------------------------ record

function Get-AceRecord {
    param([string]$Path)
    $a = Get-Acl -LiteralPath $Path
    [pscustomobject]@{
        path  = $Path
        owner = $a.Owner
        sddl  = $a.Sddl
        aces  = @($a.Access | ForEach-Object {
            [pscustomobject]@{
                identity          = $_.IdentityReference.Value
                type              = $_.AccessControlType.ToString()
                rights            = $_.FileSystemRights.ToString()
                inheritance_flags = $_.InheritanceFlags.ToString()
                propagation_flags = $_.PropagationFlags.ToString()
                # Whether this entry arrived by inheritance rather than being set here. The
                # inherited case is only meaningful if this is true on the child.
                is_inherited      = $_.IsInherited
            }
        })
    }
}

$record = [pscustomobject]@{
    part            = 'ace-as-set'
    share_path      = $SharePath
    ad_user         = $AdUser
    ad_user_sid     = $resolved.Value
    set_by          = $env:USERNAME
    set_by_elevated = $isAdmin
    host            = $env:COMPUTERNAME
    recorded_at_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
    subjects        = @(
        Get-AceRecord -Path $paths.allow
        Get-AceRecord -Path $paths.deny
        Get-AceRecord -Path $paths.inherited
        Get-AceRecord -Path $child
    )
    reminder        = 'This is one of the three parts. Pair it with the NFS-side record from read-effective-permissions.sh, and do not read it back from an account in the file system administrators group.'
}

$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutFile -Encoding UTF8

Write-Host ''
Write-Host "== record =="
Write-Host ("written to : {0}" -f (Resolve-Path -LiteralPath $OutFile))
Write-Host ''
Write-Host "Next, on the Linux client, as an ordinary Active Directory user:"
Write-Host "  ./read-effective-permissions.sh --nfs-endpoint <ip> --junction /<ntfs volume> \"
Write-Host "      --style ntfs --ontap-version <version> --out ntfs.json"
Write-Host "  ./read-effective-permissions.sh --nfs-endpoint <ip> --junction /<unix volume> \"
Write-Host "      --style unix --ontap-version <version> --out unix.json"
Write-Host ''
Write-Host "The second run is the control. Without it, a result on the NTFS volume cannot be"
Write-Host "attributed to the security style rather than to the export policy or to sssd."
