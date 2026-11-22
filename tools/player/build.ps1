param(
    [string] $VcpkgRoot = $(if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { 'C:/vcpkg' }),
    [string] $Output = 'dist/DustCreek'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Push-Location $repo
try {
    $toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
    if (!(Test-Path -LiteralPath $toolchain)) { throw "vcpkg toolchain missing at $toolchain" }
    python -X utf8 tools/player/check_opening.py
    if ($LASTEXITCODE) { throw 'Asset validation failed' }
    cmake -S . -B build -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_TOOLCHAIN_FILE=$toolchain" "-DVCPKG_INSTALLED_DIR=$repo/build/deps" -DBUILD_TESTING=ON
    if ($LASTEXITCODE) { throw 'CMake configure failed' }
    cmake --build build --config Release --parallel 6
    if ($LASTEXITCODE) { throw 'Release build failed' }
    ctest --test-dir build -C Release --output-on-failure
    if ($LASTEXITCODE) { throw 'Regression failed' }
    cmake --install build --config Release --prefix $Output
    if ($LASTEXITCODE) { throw 'Install failed' }
    Write-Host "Game: $(Join-Path (Resolve-Path $Output) 'DustCreek.exe')"
} finally { Pop-Location }
