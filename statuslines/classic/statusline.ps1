# Claude Code StatusLine for PowerShell
# Displays directory, git status, model, token usage, and cost

# Read JSON input from stdin
$input = [Console]::In.ReadToEnd()
$json = $input | ConvertFrom-Json

# Extract values
$cwd = $json.workspace.current_dir
$model = $json.model.display_name
$transcriptPath = $json.transcript_path

# Replace home directory with ~
$dir = $cwd -replace [regex]::Escape($env:USERPROFILE), '~'

# Initialize variables
$tokens = ""
$cost = ""

# Calculate token usage and cost from transcript
if ($transcriptPath -and (Test-Path $transcriptPath)) {
    try {
        # Read and parse transcript file
        $transcriptContent = Get-Content $transcriptPath -Raw | ConvertFrom-Json

        # Sum up tokens by type from assistant messages
        $inputTok = 0
        $cacheReadTok = 0
        $cacheWriteTok = 0
        $outputTok = 0

        foreach ($entry in $transcriptContent) {
            if ($entry.type -eq "assistant" -and $entry.message.usage) {
                $usage = $entry.message.usage
                $inputTok += [int]($usage.input_tokens ?? 0)
                $cacheReadTok += [int]($usage.cache_read_input_tokens ?? 0)
                $cacheWriteTok += [int]($usage.cache_creation_input_tokens ?? 0)
                $outputTok += [int]($usage.output_tokens ?? 0)
            }
        }

        # Calculate total tokens
        $tokenSum = $inputTok + $cacheReadTok + $cacheWriteTok + $outputTok
        $tokens = "{0:N0}" -f $tokenSum

        # Determine pricing based on model
        $inputPrice = 3
        $cacheReadPrice = 0.30
        $cacheWritePrice = 3.75
        $outputPrice = 15

        if ($model -match "Opus") {
            $inputPrice = 15
            $cacheReadPrice = 1.50
            $cacheWritePrice = 18.75
            $outputPrice = 75
        }
        elseif ($model -match "Haiku") {
            $inputPrice = 0.25
            $cacheReadPrice = 0.03
            $cacheWritePrice = 0.30
            $outputPrice = 1.25
        }
        # Default is Sonnet 4.5 pricing (already set)

        # Calculate cost
        $costCalc = (($inputTok * $inputPrice) + ($cacheReadTok * $cacheReadPrice) +
                     ($cacheWriteTok * $cacheWritePrice) + ($outputTok * $outputPrice)) / 1000000

        if ($costCalc -gt 0) {
            $cost = "`${0:F2}" -f $costCalc
        }
    }
    catch {
        # Silently fail if transcript parsing fails
    }
}

# ANSI color codes
$green = "`e[32m"
$magenta = "`e[35m"
$cyan = "`e[36m"
$yellow = "`e[33m"
$red = "`e[31m"
$reset = "`e[0m"

# Get git information if in a git repo
$branch = ""
$upstream = ""
$gitStatus = ""
$gitColor = ""

try {
    Push-Location $cwd

    # Check if in git repo
    $null = git rev-parse --git-dir 2>$null
    if ($LASTEXITCODE -eq 0) {
        # Get current branch
        $branch = git branch --show-current 2>$null

        # Check for upstream tracking and commits ahead/behind
        $upstreamBranch = git rev-parse --abbrev-ref '@{u}' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $ahead = [int](git rev-list --count '@{u}..HEAD' 2>$null)
            $behind = [int](git rev-list --count 'HEAD..@{u}' 2>$null)

            if ($ahead -gt 0 -and $behind -gt 0) {
                $upstream = "↑$ahead↓$behind"
            }
            elseif ($ahead -gt 0) {
                $upstream = "↑$ahead"
            }
            elseif ($behind -gt 0) {
                $upstream = "↓$behind"
            }
        }

        # Check git status
        git diff --quiet 2>$null
        $diffClean = $LASTEXITCODE -eq 0
        git diff --cached --quiet 2>$null
        $stagedClean = $LASTEXITCODE -eq 0

        if (-not $diffClean -or -not $stagedClean) {
            $gitStatus = "!"
            $gitColor = $red
        }
        else {
            $untracked = git ls-files --others --exclude-standard 2>$null
            if ($untracked) {
                $gitStatus = "?"
                $gitColor = $green
            }
        }
    }

    Pop-Location
}
catch {
    # Not in a git repo or git not available
    if ((Get-Location).Path -ne $cwd) {
        Pop-Location
    }
}

# Build output string
$output = "$green$dir$reset"

if ($branch) {
    $output += " on $magenta$branch$reset"

    if ($upstream) {
        $output += "$cyan$upstream$reset"
    }

    if ($gitStatus) {
        $output += "$gitColor$gitStatus$reset"
    }
}

$output += " [$magenta$model$reset"

if ($tokens) {
    $output += " | $yellow$tokens$reset"

    if ($cost) {
        $output += " ($green$cost$reset)"
    }
}

$output += "]"

# Write output
Write-Host $output -NoNewline
