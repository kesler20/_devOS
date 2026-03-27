#!/usr/bin/env bash
set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <iterations>"
  exit 1
fi

for ((i=1; i<=$1; i++)); do
  echo "Iteration $i"
  echo "------------------------"

  result=$(
    cat <<'PROMPT' | codex exec --skip-git-repo-check --full-auto --cd . -
@prd.json
@docs/Design Document.md
@AGENTS.md
@progress.txt 

1. Find the highest-priority feature to work on and work only on that feature.
This should be the one you decide has the highest priority, not necessarily the first item.

2. Before implementing:
   - Read and follow AGENTS.md.
   - Read and follow Design Document.md.
   - Extract the constraints relevant to the single feature you are implementing, and all relevant UI, software, or system-design images referenced in the design document.
   - Do not implement until those constraints are clear.

3. After implementation:
   - Verify that the changes follow AGENTS.md and Design Document.md style and constraints.
   - If they do not, refactor until they do.

4. Check that the types check via pnpm typecheck or mypy src and that the tests pass via pnpm test or pytest tests or the appropriate commands for the project.

5. Update the PRD with the work that was done.

6. Append your progress to the progress.txt file.
Use this to leave a note for the next person working in the codebase.

7. Make a git commit of that feature.

ONLY WORK ON A SINGLE FEATURE.

If, while implementing the feature, you notice the PRD is complete, output <promise>COMPLETE</promise>
PROMPT
  )

  echo "$result"

  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "PRD complete, exiting."
    exit 0
  fi
done