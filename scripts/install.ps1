# FL Studio + Claude integration installer (Windows, Windows PowerShell 5.1+).
#
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -DryRun     # show what would happen
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1             # do it
#
# Steps: prerequisites (winget) -> pip install the MCP server -> copy the FL controller
# script -> install the Claude skill -> (optional) register the server with Claude Desktop.
# Safe to re-run. Backs up anything it overwrites.
param(
    [switch]$DryRun,                  # print actions only
    [switch]$SkipPrereqs,             # don't winget-install Python/loopMIDI/ffmpeg/Node
    [switch]$Stems,                   # also install Demucs (stem separation; pulls torch)
    [switch]$ConfigureClaudeDesktop,  # merge the fl-studio server into claude_desktop_config.json
    [switch]$NoSkill                  # don't copy the skill into ~/.claude/skills
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
function Step($m) { Write-Output "`n== $m" }
function Act($desc, [scriptblock]$do) {
    if ($DryRun) { Write-Output "   [dry-run] $desc" } else { Write-Output "   $desc"; & $do }
}

# -- 1. prerequisites --------------------------------------------------------------
Step "Prerequisites"
function Find-Python {
    $c = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
         Sort-Object FullName | Select-Object -Last 1
    if ($c) { return $c.FullName }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return (& py -3 -c "import sys; print(sys.executable)") }
    return $null
}
$python = Find-Python
$need = @()
if (-not $python) { $need += @{ id = 'Python.Python.3.12'; why = 'Python 3.10+'; args = '--scope user --override "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1"' } }
if (-not (Get-ChildItem "C:\Program Files*\Tobias Erichsen\loopMIDI\loopMIDI.exe" -ErrorAction SilentlyContinue)) { $need += @{ id = 'TobiasErichsen.loopMIDI'; why = 'virtual MIDI ports'; args = '' } }
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and -not (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -ErrorAction SilentlyContinue)) { $need += @{ id = 'Gyan.FFmpeg'; why = 'audio decoding for reference downloads'; args = '' } }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { $need += @{ id = 'OpenJS.NodeJS.LTS'; why = 'YouTube JS challenges in yt-dlp (optional)'; args = '' } }
if (-not $need) { Write-Output "   all present" }
foreach ($n in $need) {
    if ($SkipPrereqs) { Write-Output "   missing: $($n.id) ($($n.why)) -- skipped (-SkipPrereqs)"; continue }
    Act "winget install $($n.id)  ($($n.why))" { Invoke-Expression "winget install -e --id $($n.id) --silent --accept-package-agreements --accept-source-agreements $($n.args)" }
}
if (-not $python -and -not $DryRun) { $python = Find-Python }
if (-not $python) {
    if ($DryRun) { $python = 'python' } else { throw "Python not found after install; open a new terminal and re-run." }
}
Write-Output "   python: $python"

# -- 2. MCP server ------------------------------------------------------------------
Step "Install the fl-studio MCP server (editable, from this repo)"
$extras = 'audio,studio' + $(if ($Stems) { ',stems' } else { '' })
# pip must replace fl-studio-mcp(.exe) and fl-studio-mcp-daemon(.exe). If either is running (the
# daemon, or a server an MCP client such as Claude Desktop keeps open) Windows locks the file and
# pip fails half-way, leaving the package uninstalled. Stop them first; clients relaunch servers.
$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
           Where-Object { $_.CommandLine -match 'fl-studio-mcp(-daemon)?(\.exe)?' -and $_.ProcessId -ne $PID }
if ($running) {
    Act "stop $(@($running).Count) running fl-studio-mcp process(es) so pip can replace their executables" {
        $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep 1
    }
    Write-Output "   (restart Claude Desktop afterwards so it relaunches the server; preflight restarts the daemon)"
}
# A failed pip run leaves '~'-prefixed stash folders that make pip print warnings forever.
$site = & $python -c "import sysconfig; print(sysconfig.get_paths()['purelib'])" 2>$null
if ($site -and (Test-Path $site)) {
    Get-ChildItem $site -Directory -Filter '~l*studio*mcp*' -ErrorAction SilentlyContinue | ForEach-Object {
        $stale = $_.FullName
        Act "remove stale pip leftover $stale" { Remove-Item $stale -Recurse -Force }
    }
}
if ($Stems) { Write-Output "   tip: for GPU stem separation install CUDA torch first: pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124" }
Act "pip install -e `"$repo\flstudio-mcp[$extras]`"" { & $python -m pip install --no-warn-script-location -e "$repo\flstudio-mcp[$extras]"; if ($LASTEXITCODE) { throw "pip install failed" } }
$scripts = Join-Path (Split-Path $python) 'Scripts'
$serverExe = Join-Path $scripts 'fl-studio-mcp.exe'

# -- 3. FL controller script ---------------------------------------------------------
Step "Copy the FL Studio controller script"
$paths = Get-ItemProperty 'HKCU:\Software\Image-Line\Shared\Paths' -ErrorAction SilentlyContinue
$userData = $null
if ($paths -and $paths.'Shared data') {
    $cand = Join-Path ([Environment]::ExpandEnvironmentVariables($paths.'Shared data')) 'FL Studio'
    if (Test-Path (Join-Path $cand 'Settings')) { $userData = $cand }
}
if (-not $userData) { $userData = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Image-Line\FL Studio' }
if (-not (Test-Path (Join-Path $userData 'Settings'))) {
    Write-Output "   FL user data folder not found ($userData). Open FL Studio once (Options > File settings shows the folder) and re-run."
} else {
    $hw = Join-Path $userData 'Settings\Hardware\FLStudioMCP'
    Act "copy device_FLStudioMCP.py -> $hw" {
        New-Item -ItemType Directory -Force $hw | Out-Null
        Copy-Item "$repo\flstudio-mcp\fl_controller\FLStudioMCP\device_FLStudioMCP.py" $hw -Force
    }
}

# -- 4. Claude skill ----------------------------------------------------------------
if (-not $NoSkill) {
    Step "Install the fl-studio skill for Claude Code"
    $skillDst = Join-Path $HOME '.claude\skills\fl-studio'
    if (Test-Path $skillDst) {
        $bak = "$skillDst.bak-$(Get-Date -Format yyyyMMdd-HHmmss)"
        Act "back up existing skill -> $bak" { Move-Item $skillDst $bak }
    }
    Act "copy skills\fl-studio -> $skillDst" { Copy-Item "$repo\skills\fl-studio" $skillDst -Recurse }
    Write-Output "   Claude Desktop: zip skills\fl-studio and upload it under Settings > Capabilities > Skills."
}

# -- 5. Claude Desktop config ---------------------------------------------------------
Step "Register the server with Claude Desktop"
$snippet = @{ command = $serverExe; env = @{ FLSTUDIO_MCP_TRANSPORT = 'tcp' } } | ConvertTo-Json -Compress
$configs = @("$env:APPDATA\Claude\claude_desktop_config.json") +
           (Get-ChildItem "$env:LOCALAPPDATA\Packages" -Filter 'Claude*' -Directory -ErrorAction SilentlyContinue |
            ForEach-Object { Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json' })
$config = $configs | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $ConfigureClaudeDesktop) {
    Write-Output "   Add this under `"mcpServers`" in $(if ($config) { $config } else { 'claude_desktop_config.json' }):"
    Write-Output "   `"fl-studio`": $snippet"
    Write-Output "   (or re-run with -ConfigureClaudeDesktop to merge it automatically, with a backup)"
} elseif (-not $config) {
    Write-Output "   no claude_desktop_config.json found; is Claude Desktop installed? Snippet: `"fl-studio`": $snippet"
} else {
    Act "back up + merge fl-studio into $config" {
        Copy-Item $config ($config -replace '\.json$', ".backup-$(Get-Date -Format yyyyMMdd-HHmmss).json")
        $merge = @'
import json, sys
path, exe = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8-sig") as f:
    cfg = json.load(f)
cfg.setdefault("mcpServers", {})["fl-studio"] = {"command": exe, "env": {"FLSTUDIO_MCP_TRANSPORT": "tcp"}}
with open(path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
'@
        $tmp = Join-Path $env:TEMP 'fl_merge_config.py'
        [IO.File]::WriteAllText($tmp, $merge)
        & $python $tmp $config $serverExe
        Remove-Item $tmp
    }
    Write-Output "   Restart Claude Desktop fully (tray icon > Quit) to load the server."
}

# -- next steps -----------------------------------------------------------------------
Step "Next (manual, once)"
Write-Output @"
   1. loopMIDI: create two ports named exactly  FLStudioMCP RX  and  FLStudioMCP TX
   2. FL Studio > Options > MIDI Settings (restart FL first so it sees the script):
        Input  'FLStudioMCP RX' : Enable, Controller type = FLStudioMCP, Port = 10
        Output 'FLStudioMCP TX' : Port = 10
        Output 'FLStudioMCP RX' : leave at '---' or any port other than 10
   3. Each session:  powershell -ExecutionPolicy Bypass -File "$HOME\.claude\skills\fl-studio\scripts\preflight.ps1" -StartFL
"@
if ($DryRun) { Write-Output "`n(dry run: nothing was changed)" }
