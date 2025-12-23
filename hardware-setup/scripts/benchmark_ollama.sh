#!/bin/bash
set -euo pipefail

MODEL="${MODEL:-qwq}"
PROMPT="${PROMPT:-Tell me a story about a robot dog.}"
LOGFILE="${LOGFILE:-ollama_benchmark.log}"
API_URL="${API_URL:-http://localhost:11434/api/generate}"
CONCURRENCY="${CONCURRENCY:-2}"

echo "Benchmarking model: $MODEL"
echo "Prompt: \"$PROMPT\""
echo "Running $CONCURRENCY concurrent request(s) to hit both GPUs."

echo "Pulling model inside Docker container..."
ollama pull "$MODEL"

run_benchmark() {
  local worker_id="$1"
  local response eval_count eval_duration_ns eval_duration_sec tokens_per_sec

  response=$(curl -sS "$API_URL" -d "{
    \"model\": \"$MODEL\",
    \"prompt\": \"$PROMPT\",
    \"stream\": false
  }")

  eval_count=$(echo "$response" | jq .eval_count)
  eval_duration_ns=$(echo "$response" | jq .eval_duration)

  if [[ -z "$eval_count" || "$eval_count" == "null" || -z "$eval_duration_ns" || "$eval_duration_ns" == "null" ]]; then
    echo "[$worker_id] Failed to parse eval_count or eval_duration from response:"
    echo "$response"
    exit 1
  fi

  eval_duration_sec=$(awk "BEGIN {printf \"%.2f\", $eval_duration_ns / 1000000000}")
  tokens_per_sec=$(awk "BEGIN {printf \"%.2f\", $eval_count / $eval_duration_sec}")

  echo "[$worker_id] Result: $eval_count tokens in $eval_duration_sec sec = $tokens_per_sec tokens/sec"
  echo "log|$(date -Iseconds) | worker=$worker_id | $MODEL | $eval_count tokens | $eval_duration_sec sec | $tokens_per_sec tokens/sec"
}

if ! [[ "$CONCURRENCY" =~ ^[1-9][0-9]*$ ]]; then
  echo "CONCURRENCY must be a positive integer."
  exit 1
fi

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

pids=()

for worker in $(seq 1 "$CONCURRENCY"); do
  run_benchmark "$worker" >"$tmp_dir/run_$worker.out" 2>&1 &
  pids+=("$!")
done

status=0

for idx in "${!pids[@]}"; do
  worker=$((idx + 1))
  if ! wait "${pids[$idx]}"; then
    status=1
  fi

  while IFS= read -r line; do
    if [[ "$line" == log\|* ]]; then
      echo "${line#log|}" >>"$LOGFILE"
    else
      echo "$line"
    fi
  done <"$tmp_dir/run_$worker.out"
done

exit "$status"
