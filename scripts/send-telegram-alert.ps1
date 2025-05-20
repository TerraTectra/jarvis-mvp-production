param(
    [Parameter(Mandatory=$true)]
    [string]$Message,
    
    [Parameter(Mandatory=$true)]
    [string]$Token,
    
    [Parameter(Mandatory=$true)]
    [string]$ChatId,
    
    [ValidateSet('info', 'warning', 'error', 'success')]
    [string]$Level = 'info'
)

# Define emojis based on level
$emojis = @{
    'info' = 'ℹ️'
    'warning' = '⚠️'
    'error' = '❌'
    'success' = '✅'
}

$emoji = $emojis[$Level]
$formattedMessage = "$emoji *$($Level.ToUpper())* $emoji`n`n$Message"

$uri = "https://api.telegram.org/bot$Token/sendMessage"

$body = @{
    chat_id = $ChatId
    text = $formattedMessage
    parse_mode = 'Markdown'
    disable_web_page_preview = $true
}

try {
    $response = Invoke-RestMethod -Uri $uri -Method Post -Body $body -ContentType 'application/json'
    Write-Host "Message sent successfully!" -ForegroundColor Green
    return $response
} catch {
    Write-Error "Failed to send message: $_"
    exit 1
}
