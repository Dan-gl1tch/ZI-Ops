param([string]$ProjectRoot = (Join-Path $PSScriptRoot '..'))
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
$ProjectRoot = [IO.Path]::GetFullPath($ProjectRoot)
$app = Join-Path $ProjectRoot 'build\compose\binaries\main\app\ZI-Ops'
if (-not (Test-Path -LiteralPath (Join-Path $app 'ZI-Ops.exe'))) { throw 'Build createDistributable first.' }
$versionText = Get-Content -LiteralPath (Join-Path $ProjectRoot 'src/main/resources/app-version.properties') -Raw
$version = [regex]::Match($versionText, '(?m)^app\.version\s*=\s*(\d+\.\d+\.\d+\.\d+)\s*$').Groups[1].Value
if (-not $version) { throw 'Package version not found.' }
$temporary = Join-Path $ProjectRoot 'build\portable'
$out = Join-Path $ProjectRoot 'dist'
[IO.Directory]::CreateDirectory($temporary) | Out-Null
[IO.Directory]::CreateDirectory($out) | Out-Null
$payload = Join-Path $temporary 'Payload.zip'
if (Test-Path -LiteralPath $payload) { Remove-Item -LiteralPath $payload }
Write-Host 'Compressing application and bundled Java runtime...'
[IO.Compression.ZipFile]::CreateFromDirectory($app, $payload, [IO.Compression.CompressionLevel]::Optimal, $false)
$inputStream = [IO.File]::OpenRead($payload)
$sha = [Security.Cryptography.SHA256]::Create()
try { $hash = [BitConverter]::ToString($sha.ComputeHash($inputStream)).Replace('-', '').ToLowerInvariant() }
finally { $inputStream.Dispose(); $sha.Dispose() }
$metadata = Join-Path $temporary 'PayloadInfo.cs'
@"
using System.Reflection;
[assembly: AssemblyTitle("ZI-Ops")]
[assembly: AssemblyProduct("ZI-Ops")]
[assembly: AssemblyCompany("danilmine_D47")]
[assembly: AssemblyVersion("$version")]
[assembly: AssemblyFileVersion("$version")]
internal static class PayloadInfo { public const string Hash = "$hash"; }
"@ | Set-Content -LiteralPath $metadata -Encoding utf8
$csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $csc)) { $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe' }
if (-not (Test-Path -LiteralPath $csc)) { throw 'Windows .NET Framework C# compiler was not found.' }
$executable = Join-Path $out 'ZI-Ops.exe'
$compilerArgs = @('/nologo', '/target:winexe', '/platform:x64', '/optimize+', "/out:$executable", "/win32icon:$(Join-Path $ProjectRoot 'src\main\resources\ZI-Ops.ico')", '/reference:System.Windows.Forms.dll', '/reference:System.IO.Compression.dll', '/reference:System.IO.Compression.FileSystem.dll', "/resource:$payload,Payload.zip", (Join-Path $ProjectRoot 'launcher\PortableLauncher.cs'), $metadata)
& $csc @compilerArgs
if ($LASTEXITCODE -ne 0) { throw "Portable launcher compiler failed: $LASTEXITCODE" }
Write-Host "Single-file application: $executable"
