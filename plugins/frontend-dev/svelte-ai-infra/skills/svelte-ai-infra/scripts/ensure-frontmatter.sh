#!/usr/bin/env bash
# Usage: ensure-frontmatter.sh <file> <description> <applyTo>
# 確保 <file> 開頭有 canonical frontmatter，含 description / applyTo 兩個欄位。
# 行為：
#   - 去除 UTF-8 BOM（若有）
#   - 移除既有 frontmatter（若有），避免重複堆疊
#   - 寫入由參數提供的 canonical 版本
#   - Idempotent：可重複執行不會破壞
set -euo pipefail

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <file> <description> <applyTo>" >&2
  exit 1
fi

file="$1"
desc="$2"
apply_to="$3"

[ -f "$file" ] || { echo "File not found: $file" >&2; exit 1; }

# 1) 去 BOM
if head -c 3 -- "$file" | od -An -tx1 | tr -d ' \n' | grep -q '^efbbbf'; then
  tmp="$(mktemp)"
  tail -c +4 -- "$file" > "$tmp"
  mv "$tmp" "$file"
fi

# 2) 抽出主體（去除既有 frontmatter 與後面相鄰空行）
body_tmp="$(mktemp)"
awk '
  NR==1 && /^---$/ { in_fm=1; next }
  in_fm && /^---$/ { in_fm=0; skip_blank=1; next }
  in_fm           { next }
  skip_blank && NF==0 { next }
                  { skip_blank=0; print }
' "$file" > "$body_tmp"

# 3) 寫入 canonical frontmatter + 主體
out_tmp="$(mktemp)"
{
  printf -- '---\n'
  printf -- 'description: %s\n' "$desc"
  printf -- 'applyTo: "%s"\n' "$apply_to"
  printf -- '---\n\n'
  cat "$body_tmp"
} > "$out_tmp"
mv "$out_tmp" "$file"
rm -f "$body_tmp"

echo "frontmatter ensured: $file"
