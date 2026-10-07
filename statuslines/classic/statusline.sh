#!/usr/bin/env bash

# Read JSON input from stdin
input=$(cat)

# Extract values
cwd=$(echo "$input" | jq -r '.workspace.current_dir')
model=$(echo "$input" | jq -r '.model.display_name')
transcript_path=$(echo "$input" | jq -r '.transcript_path')

# Use full path (replace home with ~)
dir="${cwd/#$HOME/~}"

# Calculate token usage and cost from transcript
tokens=""
cost=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    # Parse transcript JSON and sum up tokens by type
    token_data=$(jq -rs '
        [.[] | select(.type == "assistant") | .message.usage | select(. != null)] |
        {
            input: ([.[].input_tokens // 0] | add),
            cache_read: ([.[].cache_read_input_tokens // 0] | add),
            cache_write: ([.[].cache_creation_input_tokens // 0] | add),
            output: ([.[].output_tokens // 0] | add)
        } | [.input, .cache_read, .cache_write, .output] | @tsv
    ' "$transcript_path" 2>/dev/null)

    if [ -n "$token_data" ]; then
        input_tok=$(echo "$token_data" | cut -f1)
        cache_read_tok=$(echo "$token_data" | cut -f2)
        cache_write_tok=$(echo "$token_data" | cut -f3)
        output_tok=$(echo "$token_data" | cut -f4)

        # Calculate total tokens
        token_sum=$((input_tok + cache_read_tok + cache_write_tok + output_tok))
        tokens=$(printf "%'d" "$token_sum")

        # Determine pricing based on model
        case "$model" in
            *"Sonnet 4.5"*|*"4.5"*)
                input_price=3
                cache_read_price=0.30
                cache_write_price=3.75
                output_price=15
                ;;
            *"Opus"*)
                input_price=15
                cache_read_price=1.50
                cache_write_price=18.75
                output_price=75
                ;;
            *"Haiku"*)
                input_price=0.25
                cache_read_price=0.03
                cache_write_price=0.30
                output_price=1.25
                ;;
            *)
                # Default to Sonnet 4.5 pricing
                input_price=3
                cache_read_price=0.30
                cache_write_price=3.75
                output_price=15
                ;;
        esac

        # Calculate cost
        cost_calc=$(echo "scale=4; ($input_tok * $input_price + $cache_read_tok * $cache_read_price + $cache_write_tok * $cache_write_price + $output_tok * $output_price) / 1000000" | bc)
        if [ -n "$cost_calc" ] && [ "$(echo "$cost_calc > 0" | bc)" -eq 1 ]; then
            cost=$(printf "\$%.2f" "$cost_calc")
        fi
    fi
fi

# Get git branch if in a git repo
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
    branch=$(git -C "$cwd" -c core.useBuiltinFSMonitor=false branch --show-current 2>/dev/null)

    # Check for upstream tracking and commits ahead/behind
    upstream=""
    if git -C "$cwd" rev-parse --abbrev-ref @{u} > /dev/null 2>&1; then
        ahead=$(git -C "$cwd" rev-list --count @{u}..HEAD 2>/dev/null)
        behind=$(git -C "$cwd" rev-list --count HEAD..@{u} 2>/dev/null)

        if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then
            upstream="↑${ahead}↓${behind}"
        elif [ "$ahead" -gt 0 ]; then
            upstream="↑${ahead}"
        elif [ "$behind" -gt 0 ]; then
            upstream="↓${behind}"
        fi
    fi

    # Check git status
    if ! git -C "$cwd" -c core.useBuiltinFSMonitor=false diff --quiet 2>/dev/null || \
       ! git -C "$cwd" -c core.useBuiltinFSMonitor=false diff --cached --quiet 2>/dev/null; then
        git_status="!"
        git_color="31"  # red
    elif [ -n "$(git -C "$cwd" -c core.useBuiltinFSMonitor=false ls-files --others --exclude-standard 2>/dev/null)" ]; then
        git_status="?"
        git_color="32"  # green
    else
        git_status=""
        git_color=""
    fi

    if [ -n "$branch" ]; then
        # Build the output with branch, optional upstream, optional status
        output="\033[32m${dir}\033[0m on \033[35m${branch}\033[0m"

        if [ -n "$upstream" ]; then
            output="${output}\033[36m${upstream}\033[0m"
        fi

        if [ -n "$git_status" ]; then
            output="${output}\033[${git_color}m${git_status}\033[0m"
        fi

        output="${output} [\033[35m${model}\033[0m"

        if [ -n "$tokens" ]; then
            output="${output} | \033[33m${tokens}\033[0m"
            if [ -n "$cost" ]; then
                output="${output} (\033[32m${cost}\033[0m)"
            fi
        fi

        output="${output}]"
        printf "%b" "$output"
    else
        output="\033[32m${dir}\033[0m [\033[35m${model}\033[0m"

        if [ -n "$tokens" ]; then
            output="${output} | \033[33m${tokens}\033[0m"
            if [ -n "$cost" ]; then
                output="${output} (\033[32m${cost}\033[0m)"
            fi
        fi

        output="${output}]"
        printf "%b" "$output"
    fi
else
    output="\033[32m${dir}\033[0m [\033[35m${model}\033[0m"

    if [ -n "$tokens" ]; then
        output="${output} | \033[33m${tokens}\033[0m"
        if [ -n "$cost" ]; then
            output="${output} (\033[32m${cost}\033[0m)"
        fi
    fi

    output="${output}]"
    printf "%b" "$output"
fi
