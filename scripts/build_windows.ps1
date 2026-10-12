# Builds the Windows app:
#   dist\MarkItDownGUI\MarkItDownGUI.exe                  (the app folder)
#   dist\MarkItDownGUI-<version>-windows-x64.zip           (portable, unzip and run)
#   dist\MarkItDownGUI-<version>-windows-x64-setup.exe     (installer, needs Inno Setup 6)
# Usage (PowerShell):  .\scripts\build_windows.ps1   [-Python py] [-SkipInstaller]
param(
    [string]$Python = $(if ($env:PYTHON) { $env:PYTHON } else { "python" }),
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

function Invoke-Checked {
    & $args[0] $args[1..($args.Count - 1)]
    if ($LASTEXITCODE -ne 0) { throw "Failed ($LASTEXITCODE): $args" }
}

if (-not (Test-Path .venv)) { Invoke-Checked $Python -m venv .venv }
$py = (Resolve-Path ".venv\Scripts\python.exe").Path
Invoke-Checked $py -m pip install --upgrade pip
Invoke-Checked $py -m pip install -e ".[dev]"

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
Invoke-Checked $py -m PyInstaller --noconfirm packaging\MarkItDownGUI.spec

$exe = Join-Path $PWD "dist\MarkItDownGUI\MarkItDownGUI.exe"
# Quick check that the bundle can convert without opening a window.
Set-Content -Path build\check.html -Value "<h1>ok</h1>" -Encoding utf8
$proc = Start-Process -FilePath $exe -ArgumentList "--cli", "--output", "build\check.md", "build\check.html" -WorkingDirectory $PWD -Wait -PassThru -NoNewWindow
if ($proc.ExitCode -ne 0 -or -not (Select-String -Path build\check.md -Pattern "# ok" -Quiet)) {
    throw "The bundled .exe could not convert build\check.html"
}

$version = (& $py -c "import markitdowngui; print(markitdowngui.__version__)").Trim()
$zip = "dist\MarkItDownGUI-$version-windows-x64.zip"
Compress-Archive -Path dist\MarkItDownGUI -DestinationPath $zip -Force
Write-Host "Listo: $exe"
Write-Host "Listo: $zip"

if (-not $SkipInstaller) {
    $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
    if (-not $iscc) {
        $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $iscc) {
        Write-Warning "Inno Setup 6 no encontrado (winget install JRSoftware.InnoSetup); se omite el instalador."
    } else {
        Invoke-Checked $iscc /Qp "/DAppVersion=$version" /DArch=x64 packaging\installer.iss
        Write-Host "Listo: dist\MarkItDownGUI-$version-windows-x64-setup.exe"
    }
}
