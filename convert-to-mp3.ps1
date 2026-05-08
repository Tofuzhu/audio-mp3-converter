#Requires -Version 5.1

param(
    [string]$SourceDir   = $PSScriptRoot,
    [string]$DestDrive   = "F:",
    [string]$DestFolder  = "Podcasts\luoyonghao",
    [string]$FFmpegDir   = "D:\ffmpeg",
    [int]$BitRate        = 192
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Ensure-FFmpeg {
    param([ref]$FFmpegExe)

    $found = Get-Command ffmpeg -ErrorAction SilentlyContinue
    if ($found) { $FFmpegExe.Value = "ffmpeg"; return }

    $localExe = Join-Path $FFmpegDir "bin\ffmpeg.exe"
    if (Test-Path $localExe) { $FFmpegExe.Value = $localExe; return }

    Write-Host "ffmpeg not found, downloading to $FFmpegDir ..." -ForegroundColor Yellow

    $zipUrl  = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    $zipPath = Join-Path $env:TEMP "ffmpeg-latest.zip"

    Write-Host "Downloading: $zipUrl" -ForegroundColor Cyan
    $wc = New-Object System.Net.WebClient
    $wc.DownloadFile($zipUrl, $zipPath)

    Write-Host "Extracting to D:\ ..." -ForegroundColor Cyan
    if (Test-Path $FFmpegDir) { Remove-Item $FFmpegDir -Recurse -Force }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zipPath, "D:\")
    Remove-Item $zipPath -Force

    $extracted = Get-ChildItem "D:\" -Directory | Where-Object { $_.Name -like "ffmpeg-*" } | Select-Object -First 1
    if ($extracted -and $extracted.FullName -ne $FFmpegDir) {
        Rename-Item $extracted.FullName $FFmpegDir
    }

    if (-not (Test-Path $localExe)) {
        Write-Error "ffmpeg.exe not found at $localExe after extraction."
    }

    $FFmpegExe.Value = $localExe
    Write-Host "ffmpeg ready: $localExe" -ForegroundColor Green
}

function Assert-DestDrive {
    if (-not (Test-Path "$DestDrive\")) {
        Write-Error "Drive $DestDrive not accessible. Please connect the USB device."
    }
}

function Convert-ToMp3 {
    param([string]$FFExe, [System.IO.FileInfo]$File, [string]$OutPath)

    if (Test-Path $OutPath) {
        Write-Host "  [skip] already exists: $(Split-Path $OutPath -Leaf)" -ForegroundColor DarkGray
        return $true
    }

    Write-Host "  Converting: $($File.Name)" -ForegroundColor Cyan
    $argList = @("-i", $File.FullName, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "${BitRate}k", "-y", $OutPath)
    $proc = Start-Process -FilePath $FFExe -ArgumentList $argList -Wait -PassThru -NoNewWindow `
                          -RedirectStandardOutput "NUL" -RedirectStandardError "NUL"

    if ($proc.ExitCode -ne 0) {
        Write-Warning "Conversion failed: $($File.Name)"
        return $false
    }
    return $true
}

# --- main ---

$ffmpegExe = ""
Ensure-FFmpeg -FFmpegExe ([ref]$ffmpegExe)
Assert-DestDrive

$destPath = Join-Path $DestDrive $DestFolder
New-Item -ItemType Directory -Force -Path $destPath | Out-Null

$audioExtensions = @('.m4a', '.aac', '.flac', '.wav', '.ogg', '.wma', '.opus', '.mp3')
$files = Get-ChildItem -LiteralPath $SourceDir -File |
         Where-Object { $audioExtensions -contains $_.Extension.ToLower() }

if ($files.Count -eq 0) {
    Write-Host "No audio files found in $SourceDir" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Found $($files.Count) audio files -> $destPath"
Write-Host ""

$success = 0
$failed  = 0

foreach ($file in $files) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $mp3Name  = "$baseName.mp3"
    $mp3Dest  = Join-Path $destPath $mp3Name

    if ($file.Extension.ToLower() -eq '.mp3') {
        if (Test-Path $mp3Dest) {
            Write-Host "  [skip] already on USB: $mp3Name" -ForegroundColor DarkGray
        } else {
            Write-Host "  Copying to USB: $mp3Name" -ForegroundColor Green
            Copy-Item -LiteralPath $file.FullName -Destination $mp3Dest -Force
        }
        $success++
        continue
    }

    $tmpDir = Join-Path $FFmpegDir "tmp"
    New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
    $tmpMp3 = Join-Path $tmpDir $mp3Name

    $ok = Convert-ToMp3 -FFExe $ffmpegExe -File $file -OutPath $tmpMp3
    if (-not $ok) { $failed++; continue }

    if (Test-Path $mp3Dest) {
        Write-Host "  [skip] already on USB: $mp3Name" -ForegroundColor DarkGray
    } else {
        Write-Host "  Copying to USB: $mp3Name" -ForegroundColor Green
        Copy-Item -LiteralPath $tmpMp3 -Destination $mp3Dest -Force
    }

    Remove-Item -LiteralPath $tmpMp3 -Force
    $success++
}

$tmpDir = Join-Path $FFmpegDir "tmp"
if (Test-Path $tmpDir) { Remove-Item $tmpDir -Recurse -Force }

Write-Host ""
Write-Host "Done: $success succeeded, $failed failed." -ForegroundColor White
Write-Host "Files saved to: $destPath" -ForegroundColor Green
