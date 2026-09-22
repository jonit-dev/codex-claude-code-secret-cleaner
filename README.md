# Codex Claude Code Secret Cleaner

`codex-claude-code-secret-cleaner` redacts leaked API keys, tokens, passwords, private keys, and connection strings from local AI coding assistant conversation history.

It is built for people searching for:

- clean secrets from Codex session history
- clean secrets from Claude Code history
- remove API keys from AI conversation logs
- redact credentials from local coding agent transcripts
- cron job to scrub Codex and Claude Code history

The cleaner scans local text history files, replaces likely credentials with `*******************`, and can run safely as a recurring cron job.

## What It Cleans

By default it scans:

- `~/.codex/sessions`
- `~/.codex/shell_snapshots`
- `~/.codex/history.jsonl`
- `~/.codex/log/codex-tui.log`
- `~/.claude/sessions`
- `~/.claude/projects`
- `~/.claude/history.jsonl`

You can also pass one or more custom files or directories with `--path`.

## What It Detects

The cleaner uses local regex detection for common secret formats:

- OpenAI API keys
- GitHub personal access tokens
- AWS access key IDs
- Slack tokens
- Google API keys
- JWTs
- private key blocks
- `Authorization: Bearer ...` and `Authorization: Basic ...`
- database URLs with embedded passwords
- key/value fields such as `api_key`, `access_token`, `client_secret`, `password`, `database_url`, and `connection_string`

It intentionally ignores common placeholder values such as `example`, `dummy`, `changeme`, `redacted`, and `masked`.

## Install

Clone the repo:

```bash
git clone https://github.com/jonit-dev/codex-claude-code-secret-cleaner.git
cd codex-claude-code-secret-cleaner
```

Install the CLI into `~/.local/bin`:

```bash
mkdir -p ~/.local/bin
cp codex-claude-code-secret-cleaner ~/.local/bin/
chmod 700 ~/.local/bin/codex-claude-code-secret-cleaner
```

Make sure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## Run a Dry Run First

Always start with a dry run:

```bash
codex-claude-code-secret-cleaner --dry-run
```

Example output:

```text
mode=dry_run scanned_files=42 changed_files=3 redactions=9 incremental=0 elapsed_seconds=1.234
```

The command reports counts only. It does not print the secret values it found.

## Redact Secrets

After reviewing the dry-run count, run:

```bash
codex-claude-code-secret-cleaner
```

Matched secrets are replaced in-place with:

```text
*******************
```

## Scan Custom Paths

To scan specific files or directories:

```bash
codex-claude-code-secret-cleaner --path ~/.codex --path ~/my-agent-logs
```

## Incremental Scans

Use `--incremental` for recurring scans of the default history paths:

```bash
codex-claude-code-secret-cleaner --incremental --dry-run
codex-claude-code-secret-cleaner --incremental
```

The first incremental run scans all default paths. Later runs check file timestamps before reading content and select files changed after the previous successful run started. Each selected file is scanned in full. Metadata change times also catch imported files that retain an older modification time.

The checkpoint is stored in `~/.local/state/codex-claude-code-secret-cleaner/last-successful-start-ns`. Dry runs and failed runs do not advance it. Edits made during a scan remain eligible for the next run.

Without `--incremental`, the command performs a full scan. Use a full scan after changing detection patterns. Custom `--path` scans cannot use `--incremental` or advance its checkpoint.

## Install as a Cron Job

The suggested schedule is Sunday at 1:17 AM in the machine's local timezone, with reduced CPU priority. Cron requires the machine to be awake at that time.

Create the log directory, then open your crontab:

```bash
mkdir -p "$HOME/.local/state/codex-claude-code-secret-cleaner"
crontab -e
```

Replace any existing cleaner entry with this weekly job. Keep other jobs unchanged:

```cron
17 1 * * 0 PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin /usr/bin/nice -n 15 "$HOME/.local/bin/codex-claude-code-secret-cleaner" --incremental --quiet >> "$HOME/.local/state/codex-claude-code-secret-cleaner/cron.log" 2>&1
```

The explicit `PATH` lets cron find Python and optional ripgrep installations in common locations. Without ripgrep, the cleaner uses its Python fallback on the selected files.

Verify it was installed:

```bash
crontab -l | grep codex-claude-code-secret-cleaner
```

## Logs

The cleaner writes a small audit log here:

```text
~/.local/state/codex-claude-code-secret-cleaner/scrubber.log
```

The log contains timestamps and summary counts only, not secret values.

## Tests

Run the regression tests with Python's standard library:

```bash
python3 -m unittest -v test_incremental.py
```

The tests use temporary directories and do not scan your history.

## Safety Notes

- This tool redacts local files in place unless `--dry-run` is used.
- It does not rotate leaked credentials. Rotate any real credential that may have been pasted into an AI assistant.
- It is regex-based, so it can have false positives and false negatives.
- It is designed for local conversation history, not as a full source-code secret scanner.

For Git repositories, pair this with a dedicated scanner such as Gitleaks, TruffleHog, or GitHub secret scanning.
