# 使用当前终端的 Python 调用可选 runner；显式传入工作根并原样转交参数，进程归属与安全停机由 runner 核验。
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
$runner = Join-Path $repoRoot "ops\modular_runtime.py"
$python = (Get-Command python -ErrorAction Stop).Source

& $python -B $runner --repo-root $repoRoot $Command @Arguments
exit $LASTEXITCODE
