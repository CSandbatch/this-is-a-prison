param(
  [Parameter(Mandatory = $false)][string]$SecretsPath = ".\\secrets.json",
  [switch]$PassThru
)

$ErrorActionPreference = "Stop"

if (!(Test-Path $SecretsPath)) {
  throw "Secrets file not found: $SecretsPath"
}

$secrets = Get-Content -Raw -Path $SecretsPath | ConvertFrom-Json

if ($null -ne $secrets.telegram.bot_token) {
  $env:TELEGRAM_BOT_TOKEN = [string]$secrets.telegram.bot_token
}
if ($null -ne $secrets.openai.api_key) {
  $env:OPENAI_API_KEY = [string]$secrets.openai.api_key
}
if ($null -ne $secrets.openai.model) {
  $env:OPENAI_MODEL = [string]$secrets.openai.model
}
if ($null -ne $secrets.aws.context_window_size) {
  $env:CONTEXT_WINDOW_SIZE = [string]$secrets.aws.context_window_size
}
if ($null -ne $secrets.aws.dynamodb_context_table) {
  $env:DYNAMODB_CONTEXT_TABLE = [string]$secrets.aws.dynamodb_context_table
}
if ($null -ne $secrets.aws.dynamodb_log_table) {
  $env:DYNAMODB_LOG_TABLE = [string]$secrets.aws.dynamodb_log_table
}
if ($null -ne $secrets.aws.region) {
  $env:AWS_REGION = [string]$secrets.aws.region
}

if ($PassThru) {
  [pscustomobject]@{
    AWS_REGION             = $env:AWS_REGION
    TELEGRAM_BOT_TOKEN     = if ($env:TELEGRAM_BOT_TOKEN) { "***set***" } else { "" }
    OPENAI_API_KEY         = if ($env:OPENAI_API_KEY) { "***set***" } else { "" }
    OPENAI_MODEL           = $env:OPENAI_MODEL
    CONTEXT_WINDOW_SIZE    = $env:CONTEXT_WINDOW_SIZE
    DYNAMODB_CONTEXT_TABLE = $env:DYNAMODB_CONTEXT_TABLE
    DYNAMODB_LOG_TABLE     = $env:DYNAMODB_LOG_TABLE
  }
}

