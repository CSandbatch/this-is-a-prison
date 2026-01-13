param(
  [Parameter(Mandatory = $true)][string]$AwsRegion,
  [Parameter(Mandatory = $true)][string]$AppName,
  [Parameter(Mandatory = $true)][string]$DynamoContextTable,
  [Parameter(Mandatory = $true)][string]$DynamoLogTable,
  [Parameter(Mandatory = $true)][string]$TelegramBotToken,
  [Parameter(Mandatory = $true)][string]$OpenAIApiKey,
  [Parameter(Mandatory = $true)][string]$OpenAIModel,
  [Parameter(Mandatory = $true)][int]$ContextWindowSize
)

$ErrorActionPreference = "Stop"

function Ensure-Table {
  param([string]$TableName)
  $existing = aws dynamodb list-tables --region $AwsRegion | ConvertFrom-Json
  if ($existing.TableNames -contains $TableName) { return }

  aws dynamodb create-table --region $AwsRegion `
    --table-name $TableName `
    --attribute-definitions AttributeName=chat_id,AttributeType=S AttributeName=timestamp,AttributeType=S `
    --key-schema AttributeName=chat_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE `
    --billing-mode PAY_PER_REQUEST | Out-Null
}

Ensure-Table -TableName $DynamoContextTable
Ensure-Table -TableName $DynamoLogTable

$trust = @'
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Principal": { "Service": "lambda.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ]
}
'@
$trustPath = Join-Path $PSScriptRoot "trust-policy.json"
$trust | Out-File -Encoding utf8 $trustPath

$roleName = "$AppName-exec"
try { aws iam create-role --role-name $roleName --assume-role-policy-document "file://$trustPath" | Out-Null } catch {}
try {
  aws iam attach-role-policy --role-name $roleName --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole | Out-Null
} catch {}

$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem","dynamodb:DeleteItem","dynamodb:Query","dynamodb:BatchWriteItem"],
      "Resource": [
        "arn:aws:dynamodb:$AwsRegion:*:table/$DynamoContextTable",
        "arn:aws:dynamodb:$AwsRegion:*:table/$DynamoLogTable"
      ]
    }
  ]
}
"@
$policyPath = Join-Path $PSScriptRoot "dynamodb-policy.json"
$policy | Out-File -Encoding utf8 $policyPath
aws iam put-role-policy --role-name $roleName --policy-name "$AppName-dynamodb" --policy-document "file://$policyPath" | Out-Null

$roleArn = (aws iam get-role --role-name $roleName | ConvertFrom-Json).Role.Arn

Remove-Item -Recurse -Force (Join-Path $PSScriptRoot "..\\.build") -ErrorAction SilentlyContinue
New-Item -ItemType Directory (Join-Path $PSScriptRoot "..\\.build") | Out-Null

$venvPy = Join-Path $PSScriptRoot "..\\.venv\\Scripts\\python.exe"
& $venvPy -m pip install --upgrade pip | Out-Null
& $venvPy -m pip install -r (Join-Path $PSScriptRoot "..\\requirements.txt") -t (Join-Path $PSScriptRoot "..\\.build") | Out-Null
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "..\\app") (Join-Path $PSScriptRoot "..\\.build\\app")
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "..\\openai_inference") (Join-Path $PSScriptRoot "..\\.build\\openai_inference")

$zipPath = Join-Path $PSScriptRoot "..\\function.zip"
Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $PSScriptRoot "..\\.build\\*") -DestinationPath $zipPath

try {
  aws lambda create-function --region $AwsRegion `
    --function-name $AppName `
    --runtime python3.12 `
    --handler app.handler.lambda_handler `
    --role $roleArn `
    --timeout 29 `
    --memory-size 256 `
    --zip-file "fileb://$zipPath" `
    --environment "Variables={TELEGRAM_BOT_TOKEN=$TelegramBotToken,OPENAI_API_KEY=$OpenAIApiKey,OPENAI_MODEL=$OpenAIModel,CONTEXT_WINDOW_SIZE=$ContextWindowSize,DYNAMODB_CONTEXT_TABLE=$DynamoContextTable,DYNAMODB_LOG_TABLE=$DynamoLogTable}" | Out-Null
} catch {
  aws lambda update-function-code --region $AwsRegion --function-name $AppName --zip-file "fileb://$zipPath" | Out-Null
  aws lambda update-function-configuration --region $AwsRegion --function-name $AppName `
    --environment "Variables={TELEGRAM_BOT_TOKEN=$TelegramBotToken,OPENAI_API_KEY=$OpenAIApiKey,OPENAI_MODEL=$OpenAIModel,CONTEXT_WINDOW_SIZE=$ContextWindowSize,DYNAMODB_CONTEXT_TABLE=$DynamoContextTable,DYNAMODB_LOG_TABLE=$DynamoLogTable}" | Out-Null
}

try { aws lambda create-function-url-config --region $AwsRegion --function-name $AppName --auth-type NONE | Out-Null } catch {}
try {
  aws lambda add-permission --region $AwsRegion `
    --function-name $AppName `
    --statement-id FunctionUrlPublicAccess `
    --action lambda:InvokeFunctionUrl `
    --principal "*" `
    --function-url-auth-type NONE | Out-Null
} catch {}

$fnUrl = (aws lambda get-function-url-config --region $AwsRegion --function-name $AppName | ConvertFrom-Json).FunctionUrl

$webhook = Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$TelegramBotToken/setWebhook" -ContentType "application/json" -Body (@{ url = $fnUrl } | ConvertTo-Json)

[pscustomobject]@{
  FunctionUrl = $fnUrl
  WebhookOk   = $webhook.ok
} | ConvertTo-Json
