# Development Pipeline Template

## Purpose
Use this template to track local development pipeline setup and routine workflow.

## Copy for local use
1. Copy this file to `dev_readme.md`.
2. Keep local machine-specific notes in `dev_readme.md`.
3. Do not add secrets, private keys, passphrases, or tokens.

## Environment
- Local workspace: <path>
- Target device SSH alias: <alias>
- Target device host: <host>

## Pipeline Components
- Deploy script: `scripts/deploy-uconsole.ps1`
- VS Code tasks: `.vscode/tasks.json`

## Available VS Code Tasks
- `uConsole: Deploy + Install + Diagnostics`
- `uConsole: Deploy + Install`
- `uConsole: Diagnostics Only`

## Manual Deploy Command
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/deploy-uconsole.ps1
```

## Optional Flags
- `-SkipSync`
- `-SkipInstall`
- `-SkipDiagnostics`
- `-HostAlias <name>`
- `-RemoteDir </path/on/target>`

## Typical Workflow
1. Edit code locally.
2. Run deploy task.
3. Review output and diagnostics.
4. Iterate and rerun.

## Change Log
- Date:
- Change:
- Why:
- Result:
