[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet("config-check", "preflight", "start", "status", "ready", "stop")]
    [string]$Command,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Arguments
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\..")).Path
$runner = Join-Path $repoRoot "scripts\modular_runtime.py"
$python = (Get-Command python -ErrorAction Stop).Source

& $python -B $runner --repo-root $repoRoot $Command @Arguments
exit $LASTEXITCODE
