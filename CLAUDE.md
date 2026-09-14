# Stack of Agents

Agentic AI learning experiments using Azure credentials.

## Project Structure

```
.
├── .env                 # Shared Azure credentials (never commit)
├── CLAUDE.md           # This file
└── experiments/
    ├── exp-1/
    ├── exp-2/
    └── ...
```

## .env Setup

All experiments use a single shared `.env` file in the root directory with Azure credentials:
- `AZURE_API_KEY`
- `AZURE_ENDPOINT`
- Any other shared config

**Important:** Never commit `.env`. Add to `.gitignore` immediately.

## Experiment Conventions

Each experiment subfolder should:
- Be self-contained and runnable
- Use relative path to load `../.env`
- Include a minimal README if needed
- Follow language conventions for that experiment

## Working With Me

- **Read credentials cautiously:** I will never log, print, or transmit credentials outside the project
- **Use shared .env:** Always reference the root `.env` for Azure config, never duplicate credentials
- **Minimal is fine:** Start with basic POCs; refactor only as needed
- **Keep experiments isolated:** One experiment per folder to avoid side effects
