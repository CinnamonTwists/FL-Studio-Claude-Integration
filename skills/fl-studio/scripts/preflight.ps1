# Session preflight for Claude <-> FL Studio. Checks each link in the chain and
# fixes what it safely can (starts loopMIDI / the bridge daemon). Prints a
# summary line per check; exit code 0 = ready, 1 = something needs attention.
#   powershell -ExecutionPolicy Bypass -File preflight.ps1 [-StartFL]
param([switch]$StartFL)

$ErrorActionPreference = 'Continue'
$problems = @()
function Ok($m)   { Write-Output "[ OK ] $m" }
function Bad($m)  { Write-Output "[FAIL] $m"; $script:problems += $m }
function Note($m) { Write-Output "[ .. ] $m" }

# Python that has fl-studio-mcp installed
$py = (Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue | Sort-Object FullName | Select-Object -Last 1).FullName
if (-not $py) { Bad "Python not found under $env:LOCALAPPDATA\Programs\Python (see references/setup.md)"; exit 1 }
$scripts = Join-Path (Split-Path $py) 'Scripts'
$daemonExe = Join-Path $scripts 'fl-studio-mcp-daemon.exe'
if (-not (Test-Path $daemonExe)) { Bad "fl-studio-mcp not installed (pip install -e <repo>[audio,studio])"; exit 1 }
Ok "Python: $py"

# 1. loopMIDI running (it recreates its saved ports on start)
$loop = Get-Process loopMIDI -ErrorAction SilentlyContinue
if (-not $loop) {
    $exe = Get-ChildItem "C:\Program Files*\Tobias Erichsen\loopMIDI\loopMIDI.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) { Start-Process $exe.FullName -WindowStyle Minimized; Start-Sleep 3; Note "started loopMIDI" }
    else { Bad "loopMIDI not installed (winget install -e --id TobiasErichsen.loopMIDI)" }
}
$ports = & $py -c "import mido; n=set(mido.get_input_names())|set(mido.get_output_names()); print(','.join(p for p in ('FLStudioMCP RX','FLStudioMCP TX') if not any(x.startswith(p) for x in n)))" 2>$null
if ($LASTEXITCODE -ne 0) { Bad "could not query MIDI ports (mido missing?)" }
elseif ($ports) { Bad "missing loopMIDI ports: $ports  (create them in loopMIDI; names must match exactly)" }
else { Ok "loopMIDI ports FLStudioMCP RX / TX present" }

# 2. FL Studio running
$fl = Get-Process FL64 -ErrorAction SilentlyContinue
if (-not $fl -and $StartFL) {
    $flExe = (Get-ItemProperty 'HKCU:\Software\Image-Line\Shared\Paths' -ErrorAction SilentlyContinue).'FL Studio'
    if ($flExe -and (Test-Path $flExe)) { Start-Process $flExe; Note "starting FL Studio (dismiss the Welcome dialog / pick a template)"; Start-Sleep 15; $fl = Get-Process FL64 -ErrorAction SilentlyContinue }
}
if ($fl) { Ok "FL Studio running (pid $($fl.Id))" } else { Bad "FL Studio is not running (rerun with -StartFL to launch it)" }

# 3. Bridge daemon listening on 127.0.0.1:9787 (start minimized if not)
function DaemonUp { try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('127.0.0.1', 9787); $c.Close(); $true } catch { $false } }
if (-not (DaemonUp)) {
    Start-Process powershell -WindowStyle Minimized -ArgumentList '-NoExit', '-Command', "`$host.UI.RawUI.WindowTitle='FL Studio MCP daemon'; & '$daemonExe'"
    Start-Sleep 4
    if (DaemonUp) { Note "started the bridge daemon (minimized window 'FL Studio MCP daemon')" }
}
if (DaemonUp) { Ok "bridge daemon listening on 127.0.0.1:9787" } else { Bad "bridge daemon not reachable on 127.0.0.1:9787" }

# 4. End-to-end heartbeat (FL -> TX -> daemon)
if ($fl -and (DaemonUp)) {
    $here = Split-Path -Parent $MyInvocation.MyCommand.Path
    $ping = & $py (Join-Path $here 'mcp_call.py') call fl_ping 2>$null | Out-String
    if ($ping -match '"alive": true') { Ok "fl_ping: FL controller alive" }
    else {
        Bad "fl_ping failed. In FL: Options > MIDI Settings -> Input 'FLStudioMCP RX' enabled, Controller type FLStudioMCP, Port 10; Output 'FLStudioMCP TX' Port 10; Output 'FLStudioMCP RX' must NOT be on port 10 (FL sometimes auto-pairs it after a restart). View > Script output should say '[FLStudioMCP] Ready'."
        Write-Output $ping.Trim()
    }
}

if ($problems.Count -eq 0) { Write-Output "READY. Next: fl_arm_note_bridge once this FL session, then make music."; exit 0 }
exit 1
