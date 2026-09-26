$ErrorActionPreference = 'Stop'
Push-Location (Join-Path $PSScriptRoot '../..')
try {
    $version = python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])"
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid package version' }
    python -m PyInstaller --clean --noconfirm packaging/desktop.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
    $compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (!(Test-Path $compiler)) { throw 'Install Inno Setup 6 before building' }
    & $compiler "/DAppVersion=$version" packaging/windows/installer.iss
    if ($LASTEXITCODE -ne 0) { throw 'Inno Setup failed' }
    $setup = Get-Item "dist/installer/VoiceToClipboard-$version-windows-x64-cpu-setup.exe"
    $hash = (Get-FileHash $setup.FullName -Algorithm SHA256).Hash.ToLower()
    "$hash  $($setup.Name)" | Set-Content "$($setup.FullName).sha256" -Encoding ascii
    $commit = git rev-parse HEAD
    @{version=$version; commit=$commit; architecture='x64'; backend='CPU'; signing='unsigned'; sha256=$hash} |
        ConvertTo-Json | Set-Content dist/installer/build-info.json -Encoding utf8
    python -m pip freeze | Set-Content dist/installer/dependencies.txt
} finally { Pop-Location }
