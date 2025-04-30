#!/bin/bash

MODEL="qwq"
PROMPT="Tell me a story about a robot dog."
LOGFILE="ollama_benchmark.log"

echo "Benchmarking model: $MODEL"
echo "Prompt: \"$PROMPT\""

# Run the prompt and capture JSON response
RESPONSE=$(curl -s http://localhost:11434/api/generate -d "{
  \"model\": \"$MODEL\",
  \"prompt\": \"$PROMPT\",
  \"stream\": false
}")

# Extract values
eval_count=$(echo "$RESPONSE" | jq .eval_count)
eval_duration_ns=$(echo "$RESPONSE" | jq .eval_duration)

# Check for missing data
if [[ -z "$eval_count" || "$eval_count" == "null" || -z "$eval_duration_ns" ]]; then
    echo "Failed to parse eval_count or eval_duration from response:"
    echo "$RESPONSE"
    exit 1
fi

# Convert ns to seconds
eval_duration_sec=$(awk "BEGIN {printf \"%.2f\", $eval_duration_ns / 1000000000}")

# Calculate tokens/sec
tokens_per_sec=$(awk "BEGIN {printf \"%.2f\", $eval_count / $eval_duration_sec}")

echo "Result: $eval_count tokens in $eval_duration_sec sec = $tokens_per_sec tokens/sec"

# Log it
echo "$(date -Iseconds) | $MODEL | $eval_count tokens | $eval_duration_sec sec | $tokens_per_sec tokens/sec" >> "$LOGFILE"
