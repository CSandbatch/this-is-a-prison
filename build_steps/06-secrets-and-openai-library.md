1. Reorganized `secrets.json` into nested sections (github/telegram/openai/aws).
2. Added `scripts/load-secrets.ps1` to map `secrets.json` into required env vars.
3. Created `openai_inference/` package and updated Lambda code to use it.

