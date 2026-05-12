#!/usr/bin/env sh
# Parse $ARGUMENTS for meta-ralph SKILL.
#
# Usage (wrap $ARGUMENTS in DOUBLE QUOTES so it arrives as a single
# positional argument; without quoting, the host shell will split it on
# whitespace and the script will only see the first word):
#   sh scripts/parse-args.sh "$ARGUMENTS"
#
# Output (single line, JSON, LF-terminated):
#   {"mode":"bootstrap","userPrompt":""}
#   {"mode":"amend","userPrompt":"add login flow"}
#
# Rules:
#   - mode = "amend" iff the whole-token "--amend" appears in $ARGUMENTS
#     (case-sensitive). Otherwise "bootstrap".
#   - userPrompt = $ARGUMENTS minus the "--amend" token (and one adjacent
#     space), trimmed. Used as a prefill hint, not authoritative content.
#   - JSON escape covers backslash and double-quote. Tab/newline in input
#     are not officially supported (Claude Code invocations are single-line).

set -eu

raw="${1-}"

mode="bootstrap"
case " $raw " in
  *" --amend "*) mode="amend" ;;
esac

userPrompt=$(printf '%s' "$raw" | sed -E 's/(^| )--amend( |$)/ /g; s/^ +//; s/ +$//; s/  +/ /g')

# JSON-escape: \ -> \\, " -> \"
escaped=$(printf '%s' "$userPrompt" | sed 's/\\/\\\\/g; s/"/\\"/g')

printf '{"mode":"%s","userPrompt":"%s"}\n' "$mode" "$escaped"
