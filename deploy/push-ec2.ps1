#Requires -Version 5.1
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$Ec2Host,
  [string]$KeyPath = "$env:USERPROFILE\.ssh\45dertyop.pem",
  [string]$RemoteUser = "ubuntu",
  [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
  $RepoRoot = Split-Path -Parent $PSScriptRoot
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
if (-not (Test-Path (Join-Path $RepoRoot "deploy\docker-compose.prod.yml"))) {
  throw "repo root invalid: $RepoRoot"
}
Write-Host "repo: $RepoRoot"

if (-not (Test-Path $KeyPath)) {
  throw "SSH key not found: $KeyPath"
}

$aclUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls $KeyPath /inheritance:r | Out-Null
icacls $KeyPath /grant:r "${aclUser}:(R)" | Out-Null

$sshBase = @(
  "-i", $KeyPath,
  "-o", "IdentitiesOnly=yes",
  "-o", "StrictHostKeyChecking=accept-new",
  "-o", "ConnectTimeout=15"
)

function Test-RemoteUser([string]$user) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & ssh @sshBase "${user}@${Ec2Host}" "echo ok" 2>$null | Out-Null
  $ok = ($LASTEXITCODE -eq 0)
  $ErrorActionPreference = $prev
  return $ok
}

if (-not (Test-RemoteUser $RemoteUser)) {
  foreach ($candidate in @("ubuntu", "ec2-user", "admin")) {
    if ($candidate -eq $RemoteUser) { continue }
    if (Test-RemoteUser $candidate) {
      $RemoteUser = $candidate
      break
    }
  }
}

Write-Host "ssh ${RemoteUser}@${Ec2Host}"

$stage = Join-Path $env:TEMP "aai-ec2-stage"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Path $stage | Out-Null

$xd = @(".git", "vendor", "research", ".venv", "node_modules", ".cursor", "resplan")
$xf = @("*.pt", "*.pkl", "*.log", ".env")
$robolog = Join-Path $env:TEMP "aai-robocopy.log"
& robocopy $RepoRoot $stage /E /NFL /NDL /NJH /NJS /nc /ns /np /R:1 /W:1 /XD @xd /XF @xf /LOG:$robolog | Out-Null
if ($LASTEXITCODE -ge 8) {
  throw "robocopy failed (code $LASTEXITCODE). log: $robolog"
}

$localEnv = Join-Path $stage "deploy\.env"
if (Test-Path $localEnv) { Remove-Item -Force $localEnv }

$archive = Join-Path $env:TEMP "aai-ec2.tar"
if (Test-Path $archive) { Remove-Item -Force $archive }
& tar -C $stage -cf $archive .
if ($LASTEXITCODE -ne 0) { throw "tar failed" }

$remote = "${RemoteUser}@${Ec2Host}"
Write-Host "uploading archive..."
& ssh @sshBase $remote "mkdir -p ~/A-AI"
if ($LASTEXITCODE -ne 0) { throw "ssh mkdir failed (check IP, SG port 22, AMI user)" }
& scp @sshBase $archive "${remote}:/tmp/aai-ec2.tar"
if ($LASTEXITCODE -ne 0) { throw "scp failed" }

Write-Host "remote bootstrap (docker + stack, no Blender)..."
& ssh @sshBase $remote 'tar -xf /tmp/aai-ec2.tar -C ~/A-AI; rm -f /tmp/aai-ec2.tar; sed -i "s/\r$//" ~/A-AI/deploy/*.sh; chmod +x ~/A-AI/deploy/*.sh; sudo bash ~/A-AI/deploy/bootstrap-ec2.sh'
if ($LASTEXITCODE -ne 0) { throw "remote bootstrap failed" }

$sslip = ($Ec2Host -replace '\.', '-') + ".sslip.io"
Write-Host "done. client URL: https://$sslip"
