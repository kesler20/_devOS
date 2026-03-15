# To update devOS installation from anywhere.
function Update-devOS {
    param(
        [string]$TargetDir = "",      # optional argument for target directory
        [string]$DevOSPath = "../devOS"  # optional argument for devOS path
    )
    Set-Location $DevOSPath
    git pull
    pip install -e .
    if ($TargetDir -ne "") {
        Set-Location "..\$TargetDir"
    }
}
Set-Alias dev-update Update-devOS

# A function that will run devOS to update specific files locally.
function Sync-devOS {
    param(
        [string]$Target = ""
    )

    switch ($Target.ToLower()) {
        "read_agents" {
            dev get snippet from prompts,AGENTS.md to AGENTS.md
        }
        "read_ralph" {
            dev get snippet from prompts,ralph.sh to ralph.sh
        }
        "write_agents" {
            dev set snippet from AGENTS.md to prompts,AGENTS.md
        }
        "write_ralph" {
            dev set snippet from ralph.sh to prompts,ralph.sh
        }
        default {
            Write-Host "Unknown target: $Target. Supported targets: agents, ralph."
        }
    }
}
Set-Alias dev-sync Sync-devOS
