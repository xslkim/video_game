param(
    [string] $VcpkgRoot = $(if ($env:VCPKG_ROOT) { $env:VCPKG_ROOT } else { 'C:/vcpkg' }),
    [string] $Output = 'dist/Linyuan-MVP',
    [switch] $BuildOnly
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$toolchain = Join-Path $VcpkgRoot 'scripts/buildsystems/vcpkg.cmake'
if (!(Test-Path -LiteralPath $toolchain)) { throw "vcpkg toolchain missing at $toolchain" }
Push-Location $repo
try {
    cmake -S . -B build-linyuan -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_TOOLCHAIN_FILE=$toolchain" "-DVCPKG_INSTALLED_DIR=$repo/build/deps" -DBUILD_LINYUAN=ON -DBUILD_TESTING=ON
    if ($LASTEXITCODE) { throw 'Linyuan configuration failed' }
    cmake --build build-linyuan --config Release --parallel 6
    if ($LASTEXITCODE) { throw 'Linyuan build failed' }
    ctest --test-dir build-linyuan -C Release --output-on-failure
    if ($LASTEXITCODE) { throw 'Rule tests failed' }
    if (!$BuildOnly) {
        $runtime = Join-Path $repo 'build-linyuan/runtime'
        cmake --install build-linyuan --config Release --component GameRuntime --prefix $runtime
        if ($LASTEXITCODE) { throw 'Linyuan runtime installation failed' }
        python -X utf8 tools/player/package_linyuan.py $runtime $Output
        if ($LASTEXITCODE) { throw 'Linyuan packaging failed' }
    }
} finally { Pop-Location }
