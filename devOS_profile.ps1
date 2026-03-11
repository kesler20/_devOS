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