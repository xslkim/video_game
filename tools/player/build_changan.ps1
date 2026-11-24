param(
    [string] $VcpkgRoot = $(if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { 'C:/vcpkg' }),
    [string] $Output,
    [ValidatePattern('^[a-z0-9_]+$')][string] $Level = 'm0',
    [switch] $Campaign
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
if (!(Test-Path -LiteralPath $toolchain)) { throw "vcpkg toolchain missing at $toolchain" }
Push-Location $repo
try {
    if (!$Output) { $Output = if ($Campaign) { 'dist/Changan-Full' } elseif ($Level -eq 'm0') { 'dist/Changan-Market' } else { "dist/Changan-$Level" } }
    python -X utf8 tools/player/check_changan.py --negative --level $Level
    if ($LASTEXITCODE) { throw 'Changan encounter validation failed' }
    cmake -S . -B build-changan -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_TOOLCHAIN_FILE=$toolchain" "-DVCPKG_INSTALLED_DIR=$repo/build/deps" -DBUILD_CHANGAN=ON -DBUILD_TESTING=ON "-DCHANGAN_LEVEL=$Level"
    if ($LASTEXITCODE) { throw 'Changan configuration failed' }
    cmake --build build-changan --config Release --parallel 6
    if ($LASTEXITCODE) { throw 'Changan build failed' }
    ctest --test-dir build-changan -C Release --output-on-failure
    if ($LASTEXITCODE) { throw 'Western rule regression failed' }
    if ($Campaign) {
        $runtime = Join-Path $repo 'build-changan/campaign-runtime'
        cmake --install build-changan --config Release --component GameRuntime --prefix $runtime
        if ($LASTEXITCODE) { throw 'Campaign runtime installation failed' }
        python -X utf8 tools/player/package_changan_campaign.py campaign $runtime $Output
    } else {
        cmake --install build-changan --config Release --prefix $Output
    }
    if ($LASTEXITCODE) { throw 'Changan installation failed' }
    Write-Host "Game: $(Join-Path (Resolve-Path $Output) 'Changan.exe')"
} finally {
    Pop-Location
}
