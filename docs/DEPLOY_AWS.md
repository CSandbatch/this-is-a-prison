# AWS Deploy (CLI)

## Prereqs

- AWS CLI configured (`aws sts get-caller-identity` works)
- PowerShell 7+ recommended

## Variables

```powershell
$env:AWS_REGION="us-east-1"
$env:APP_NAME="telegram-openai-bot"
$env:DYNAMODB_CONTEXT_TABLE="telegram_bot_context"
$env:DYNAMODB_LOG_TABLE="telegram_bot_logs"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:CONTEXT_WINDOW_SIZE="30"
```

Set secrets:

```powershell
$env:TELEGRAM_BOT_TOKEN="..."
$env:OPENAI_API_KEY="..."
```

Or load from `secrets.json`:

```powershell
.\scripts\load-secrets.ps1 -PassThru
```

## 1) Create DynamoDB tables

```powershell
aws dynamodb create-table --region $env:AWS_REGION `
  --table-name $env:DYNAMODB_CONTEXT_TABLE `
  --attribute-definitions AttributeName=chat_id,AttributeType=S AttributeName=timestamp,AttributeType=S `
  --key-schema AttributeName=chat_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE `
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table --region $env:AWS_REGION `
  --table-name $env:DYNAMODB_LOG_TABLE `
  --attribute-definitions AttributeName=chat_id,AttributeType=S AttributeName=timestamp,AttributeType=S `
  --key-schema AttributeName=chat_id,KeyType=HASH AttributeName=timestamp,KeyType=RANGE `
  --billing-mode PAY_PER_REQUEST
```

## 2) Create IAM role (Lambda execution)

```powershell
$trust = @'
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Principal": { "Service": "lambda.amazonaws.com" }, "Action": "sts:AssumeRole" }
  ]
}
'@
$trust | Out-File -Encoding utf8 .\\trust-policy.json

aws iam create-role --role-name "$env:APP_NAME-exec" --assume-role-policy-document file://trust-policy.json | Out-Null
aws iam attach-role-policy --role-name "$env:APP_NAME-exec" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole | Out-Null

$policy = @"
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["dynamodb:PutItem","dynamodb:DeleteItem","dynamodb:Query","dynamodb:BatchWriteItem"],
      "Resource": [
        "arn:aws:dynamodb:$($env:AWS_REGION):*:table/$($env:DYNAMODB_CONTEXT_TABLE)",
        "arn:aws:dynamodb:$($env:AWS_REGION):*:table/$($env:DYNAMODB_LOG_TABLE)"
      ]
    }
  ]
}
"@
$policy | Out-File -Encoding utf8 .\\dynamodb-policy.json

aws iam put-role-policy --role-name "$env:APP_NAME-exec" --policy-name "$env:APP_NAME-dynamodb" --policy-document file://dynamodb-policy.json | Out-Null
```

## 3) Build deployment zip

```powershell
Remove-Item -Recurse -Force .\\.build -ErrorAction SilentlyContinue
New-Item -ItemType Directory .\\.build | Out-Null

.\\.venv\\Scripts\\python -m pip install --upgrade pip
.\\.venv\\Scripts\\python -m pip install -r .\\requirements.txt -t .\\.build
Copy-Item -Recurse -Force .\\app .\\.build\\app
Copy-Item -Recurse -Force .\\openai_inference .\\.build\\openai_inference

Remove-Item -Force .\\function.zip -ErrorAction SilentlyContinue
Compress-Archive -Path .\\.build\\* -DestinationPath .\\function.zip
```

## 4) Create Lambda + Function URL

```powershell
$roleArn = (aws iam get-role --role-name "$env:APP_NAME-exec" | ConvertFrom-Json).Role.Arn

aws lambda create-function --region $env:AWS_REGION `
  --function-name $env:APP_NAME `
  --runtime python3.12 `
  --handler app.handler.lambda_handler `
  --role $roleArn `
  --timeout 29 `
  --memory-size 256 `
  --zip-file fileb://function.zip `
  --environment Variables="{TELEGRAM_BOT_TOKEN=$env:TELEGRAM_BOT_TOKEN,OPENAI_API_KEY=$env:OPENAI_API_KEY,OPENAI_MODEL=$env:OPENAI_MODEL,CONTEXT_WINDOW_SIZE=$env:CONTEXT_WINDOW_SIZE,DYNAMODB_CONTEXT_TABLE=$env:DYNAMODB_CONTEXT_TABLE,DYNAMODB_LOG_TABLE=$env:DYNAMODB_LOG_TABLE}"

aws lambda create-function-url-config --region $env:AWS_REGION `
  --function-name $env:APP_NAME `
  --auth-type NONE

aws lambda add-permission --region $env:AWS_REGION `
  --function-name $env:APP_NAME `
  --statement-id FunctionUrlPublicAccess `
  --action lambda:InvokeFunctionUrl `
  --principal "*" `
  --function-url-auth-type NONE

$env:LAMBDA_FUNCTION_URL = (aws lambda get-function-url-config --region $env:AWS_REGION --function-name $env:APP_NAME | ConvertFrom-Json).FunctionUrl
```

## 5) Register Telegram webhook

```powershell
Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/setWebhook" -ContentType "application/json" -Body (@{ url = $env:LAMBDA_FUNCTION_URL } | ConvertTo-Json)
```

## 6) Verify webhook health

```powershell
Invoke-RestMethod -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/getWebhookInfo"
```
