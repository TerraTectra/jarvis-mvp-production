# This script helps you set up GitHub secrets for the CI/CD pipeline
# Run this script in PowerShell with admin privileges

# Check if gh CLI is installed
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed. Please install it from https://cli.github.com/"
    exit 1
}

# Check if user is logged in to GitHub
$ghAuthStatus = gh auth status 2>&1
if ($ghAuthStatus -match "not logged into any GitHub hosts") {
    Write-Host "You need to log in to GitHub first. Running 'gh auth login'..."
    gh auth login
}

# Get repository info
$repoInfo = git remote -v | Select-String -Pattern "origin\s+(https://github\.com/|git@github\.com:)([^/]+/[^/s.]+)"
if (-not $repoInfo) {
    Write-Error "Could not determine repository information. Make sure you're in a git repository with a GitHub remote named 'origin'."
    exit 1
}

$repoOwner = $repoInfo.Matches.Groups[2].Value

# Function to set a secret
function Set-GitHubSecret {
    param (
        [string]$SecretName,
        [string]$Description,
        [switch]$MaskInput = $true
    )
    
    Write-Host "`n=== $SecretName ===" -ForegroundColor Cyan
    Write-Host "$Description" -ForegroundColor Gray
    
    $secretValue = if ($MaskInput) {
        $secureValue = Read-Host -AsSecureString -Prompt "Enter value for $SecretName"
        [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
        )
    } else {
        Read-Host -Prompt "Enter value for $SecretName"
    }
    
    if (-not [string]::IsNullOrEmpty($secretValue)) {
        Write-Host "Setting secret $SecretName..." -NoNewline
        $secretValue | gh secret set $SecretName --repo $repoOwner
        if ($LASTEXITCODE -eq 0) {
            Write-Host " [OK]" -ForegroundColor Green
        } else {
            Write-Host " [FAILED]" -ForegroundColor Red
        }
    } else {
        Write-Host "Skipping $SecretName" -ForegroundColor Yellow
    }
}

# Required secrets
$secrets = @(
    @{
        Name = "TELEGRAM_BOT_TOKEN"
        Description = "Telegram Bot Token for notifications"
    },
    @{
        Name = "TELEGRAM_CHAT_ID"
        Description = "Telegram Chat ID for notifications"
    },
    @{
        Name = "SSH_PRIVATE_KEY"
        Description = "SSH private key for deployment (contents of the private key file)"
        MaskInput = $false
    },
    @{
        Name = "STAGING_HOST"
        Description = "Staging server hostname or IP"
    },
    @{
        Name = "STAGING_SSH_USER"
        Description = "SSH username for staging server"
    },
    @{
        Name = "PRODUCTION_HOST"
        Description = "Production server hostname or IP"
    },
    @{
        Name = "PRODUCTION_SSH_USER"
        Description = "SSH username for production server"
    },
    @{
        Name = "GRAFANA_ADMIN_PASSWORD"
        Description = "Admin password for Grafana"
    },
    @{
        Name = "CODECOV_TOKEN"
        Description = "Codecov token for test coverage reporting"
    }
)

# Set each secret
foreach ($secret in $secrets) {
    Set-GitHubSecret @secret
}

Write-Host "`n=== Repository Secrets Setup Complete ===" -ForegroundColor Green
Write-Host "You can view and manage these secrets at: https://github.com/$repoOwner/settings/secrets/actions" -ForegroundColor Cyan
