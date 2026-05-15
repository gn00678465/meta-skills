# Parse $ARGUMENTS for meta-ralph SKILL (PowerShell 7+).
#
# Usage (canonical — wrap $ARGUMENTS in DOUBLE QUOTES so it arrives as a
# single positional argument; otherwise PowerShell will re-tokenize on space
# and the script's first arg sees only the first word):
#   pwsh -NoProfile -File scripts/parse-args.ps1 "$ARGUMENTS"
#
# Output (single line, JSON, LF-terminated):
#   {"mode":"bootstrap","userPrompt":""}
#   {"mode":"amend","userPrompt":"add login flow"}
#
# Rules: same as parse-args.sh. See that file's header for full contract.

[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $InputArgs
)

$raw = if ($InputArgs) { ($InputArgs -join ' ') } else { '' }

# PowerShell -match / -replace are case-insensitive by default. Use the
# case-sensitive variants (-cmatch / -creplace) to match parse-args.sh.
if ($raw -cmatch '(^|\s)--amend(\s|$)') {
    $mode = 'amend'
} else {
    $mode = 'bootstrap'
}

$userPrompt = ($raw -creplace '(^|\s)--amend(\s|$)', ' ').Trim()
$userPrompt = $userPrompt -replace '\s+', ' '

# ConvertTo-Json -Compress emits CRLF on Windows by default; force LF for
# parity with parse-args.sh and the SKILL's "all writes use LF" rule.
$json = [ordered]@{
    mode       = $mode
    userPrompt = $userPrompt
} | ConvertTo-Json -Compress

[Console]::Out.Write($json + "`n")
