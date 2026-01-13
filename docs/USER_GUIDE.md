# User Guide

## What This Is

This repo deploys a Telegram bot that:

- Runs on AWS Lambda (Python 3.12) behind a **Lambda Function URL** (webhook only).
- Uses OpenAI for inference with a **bounded per-chat context window**.
- Writes **two DynamoDB tables**: short-term context and long-term training logs.

## How To Talk To The Bot

### Private chats

- Send a normal message; the bot replies.

### Group chats

The bot responds only when:

- You start the message with `/ask ...`
- You **reply to a bot message**
- You mention the bot: `@YourBotName ...`

Examples:

- `/ask summarize the last 5 messages`
- `@YourBotName what’s the plan for today?`

## What Gets Stored (DynamoDB)

### Context table (`$DYNAMODB_CONTEXT_TABLE`)

- Stores recent `user` and `assistant` messages for inference.
- Automatically trimmed to the last `CONTEXT_WINDOW_SIZE` messages per `chat_id`.

### Training log table (`$DYNAMODB_LOG_TABLE`)

- Append-only archival log of user messages and bot replies.
- Never used for inference.

Treat all stored text as sensitive.

## Configuration

### Required environment variables (Lambda)

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `CONTEXT_WINDOW_SIZE`
- `DYNAMODB_CONTEXT_TABLE`
- `DYNAMODB_LOG_TABLE`

Recommended model:

- `OPENAI_MODEL=gpt-5.2`

### Local secrets file (optional helper)

`secrets.json` is ignored by git (`.gitignore`) and can be used to set env vars locally.

Load it into your shell:

```powershell
.\scripts\load-secrets.ps1 -PassThru
```

## Deploy (AWS)

The full CLI sequence is in `docs/DEPLOY_AWS.md`.

### One-command deploy script

```powershell
.\scripts\load-secrets.ps1

.\scripts\deploy.ps1 `
  -AwsRegion $env:AWS_REGION `
  -AppName "telegram-openai-bot" `
  -DynamoContextTable $env:DYNAMODB_CONTEXT_TABLE `
  -DynamoLogTable $env:DYNAMODB_LOG_TABLE `
  -TelegramBotToken $env:TELEGRAM_BOT_TOKEN `
  -OpenAIApiKey $env:OPENAI_API_KEY `
  -OpenAIModel $env:OPENAI_MODEL `
  -ContextWindowSize ([int]$env:CONTEXT_WINDOW_SIZE)
```

The script outputs the Function URL and webhook status.

## Troubleshooting

- Bot silent in groups: use `/ask`, mention `@botname`, or reply to the bot.
- “Inference error. Try again.”: OpenAI call failed or timed out; confirm `OPENAI_API_KEY` + `OPENAI_MODEL`.
- No DynamoDB items: confirm table names in `DYNAMODB_CONTEXT_TABLE` / `DYNAMODB_LOG_TABLE` and Lambda IAM permissions.
- Webhook not set: run `getWebhookInfo` (`docs/DEPLOY_AWS.md`) and re-run `setWebhook`.

