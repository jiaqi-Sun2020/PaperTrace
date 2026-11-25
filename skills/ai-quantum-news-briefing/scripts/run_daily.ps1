[CmdletBinding(PositionalBinding=$false)]
param(
    [string]$RuntimeConfig,
    [switch]$Publisher,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$DailyArguments
)
$ErrorActionPreference = 'Stop'
if (-not $DailyArguments) {
    throw 'Supply a taskbox action and --date YYYY-MM-DD; this launcher never chooses or schedules a date.'
}
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
if (-not $RuntimeConfig) { $RuntimeConfig = Join-Path $projectRoot 'news_runtime.local.json' }
if (-not (Test-Path -LiteralPath $RuntimeConfig -PathType Leaf)) {
    throw 'Missing non-secret news_runtime.local.json; select and verify Python 3.12 and the existing OSS transport first.'
}
$runtime = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $RuntimeConfig).Path) | ConvertFrom-Json
$required = @('version','python_executable','ossutil_executable','ossutil_config','ossutil_endpoint')
if (@(Compare-Object $required @($runtime.PSObject.Properties.Name)).Count -ne 0 -or
    $runtime.version -isnot [long] -and $runtime.version -isnot [int] -or $runtime.version -ne 1) {
    throw 'Invalid non-secret daily runtime schema.'
}
$dailyPython = $runtime.python_executable
if (-not (Test-Path -LiteralPath $dailyPython -PathType Leaf)) { throw 'Configured Python is unavailable.' }
& $dailyPython -X utf8 -I -S -B -c 'import sys,sqlite3,ssl,json; sys.exit(0 if sys.version_info[:2] == (3,12) else 12)' 2>$null
if ($LASTEXITCODE -ne 0) { throw 'The daily entry requires the verified Python 3.12 runtime with sqlite3/ssl; no conda base fallback.' }
$overrides = @{
    PAPERTRACE_OSSUTIL_EXECUTABLE = $runtime.ossutil_executable
    PAPERTRACE_OSSUTIL_CONFIG = $runtime.ossutil_config
    PAPERTRACE_OSSUTIL_ENDPOINT = $runtime.ossutil_endpoint
}
$previous = @{}
foreach ($name in $overrides.Keys) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    foreach ($name in $overrides.Keys) { [Environment]::SetEnvironmentVariable($name, $overrides[$name], 'Process') }
    $scriptName = if ($Publisher) { 'publish_daily_to_oss.py' } else { 'taskbox_daily.py' }
    & $dailyPython -X utf8 -B (Join-Path $PSScriptRoot $scriptName) @DailyArguments
    $dailyExit = $LASTEXITCODE
} finally {
    foreach ($name in $previous.Keys) {
        if ($null -eq $previous[$name]) {
            Remove-Item -LiteralPath ('Env:' + $name) -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
        }
    }
}
exit $dailyExit
