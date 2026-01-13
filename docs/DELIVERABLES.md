# Deliverables

## 1) Final Lambda handler code

- Handler: `app/handler.py` (`lambda_handler`)
- Handler string: `app.handler.lambda_handler`

## 2) DynamoDB table schemas

### Context table

- Table name: `$DYNAMODB_CONTEXT_TABLE`
- Partition key: `chat_id` (String)
- Sort key: `timestamp` (String)
- Attributes stored:
  - `user_id` (String)
  - `role` (`user` | `assistant`)
  - `content` (String)

### Training log table

- Table name: `$DYNAMODB_LOG_TABLE`
- Partition key: `chat_id` (String)
- Sort key: `timestamp` (String)
- Attributes stored:
  - `user_id` (String)
  - `username` (String | null)
  - `is_group` (Boolean)
  - `message_text` (String | null)
  - `bot_reply` (String | null)
  - `language` (String | null, optional)
  - `role` (`user` | `assistant`)

## 3) Webhook registration command

- PowerShell:
  - `Invoke-RestMethod -Method Post -Uri "https://api.telegram.org/bot$env:TELEGRAM_BOT_TOKEN/setWebhook" -ContentType "application/json" -Body (@{ url = $env:LAMBDA_FUNCTION_URL } | ConvertTo-Json)`

## 4) Environment variables list

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `CONTEXT_WINDOW_SIZE`
- `DYNAMODB_CONTEXT_TABLE`
- `DYNAMODB_LOG_TABLE`

## 5) Minimal validation checklist

- `POST` webhook calls return HTTP 200.
- Private chat: bot replies to normal text.
- Group chat: bot replies only to `/ask ...`, direct reply-to-bot, or `@botname` mention.
- DynamoDB Context table contains only last `CONTEXT_WINDOW_SIZE` messages per `chat_id`.
- DynamoDB Log table appends user messages and bot replies; no context reads from this table.

