# Security Policy

## Secrets

Never commit `.env`, API keys, passwords, tokens, private keys, cookies, or credentials.

## Local tool design

JARVIS OMEGA deliberately does not expose arbitrary host shell execution, credential extraction, file deletion, software installation, persistence, security bypasses, or stealth automation.

Read-only local file tools are restricted to approved roots and text-like extensions. Secret-looking paths are blocked. Local actions can require user approval.

## Reporting a vulnerability

Please report security issues privately to the repository owner rather than opening a public exploit issue.
