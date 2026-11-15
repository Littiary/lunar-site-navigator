# Produces the material for the pitch and the video from the published packages
# (packages/ at the root of the repository): one continuous clip and six stills at
# 1920x1080, and a text file that says which package, site and time each one shows.
#
# Everything is a real render of the running scene. Times are given by UTC, so the script
# gives the same views again after the packages have been regenerated. A view whose data
# the published packages do not carry is not produced; the text file says which and why.
#
#   unreal\Scripts\pitch.ps1                     # everything
#   unreal\Scripts\pitch.ps1 -Only stills        # or: -Only clip
#
# Rehearsal: -PackageRoot <other package root> -Out <folder outside the repository> runs
# the same views on other packages, to check the script before the published ones carry a
# field. Such output is marked as a rehearsal and must not be put into the repository.
param(
    [string]$Out = "",
    [ValidateSet("all", "clip", "stills")][string]$Only = "all",
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    # The story: the Sun sets behind a ridge at SiteA while SiteB stays in sunlight.
    [string]$SiteA = "shackleton-rim-crest",
    [string]$SiteB = "de-gerlache-rim-crest",
    # The clip starts shortly before the Sun touches the ridge at SiteA and ends after it has set,
    # so that a first-time viewer sees what happens within the first seconds.
    [string]$ClipFromUtc = "2027-07-28T16:30:00Z",
    [string]$ClipToUtc = "2027-07-28T20:00:00Z",
    [string]$ClipCaption = "The same hour at two landing sites near the Moon's south pole: on the left the Sun is setting behind a ridge|Left: the Sun has set behind the highlighted ridge. Right: 40 km away, the Sun is still up",
    [double]$ClipSeconds = 26,
    [string]$HiddenUtc = "2027-07-29T06:00:00Z",
    [string]$BandUtc = "2027-07-28T17:00:00Z",
    [string]$WideUtc = "2027-09-19T13:00:00Z",
    # The key moment: the Sun goes behind the ridge nearer than 1 km to SiteA that costs it most
    # Sun. The ridge and its times are taken from the package (see below); these override them.
    [string]$NearStillUtc = "",
    [string]$NearFromUtc = "",
    [string]$NearToUtc = "",
    [string]$PackageRoot = ""
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$repo = Split-Path -Parent $root
if ($Out -eq "") { $Out = Join-Path $repo "docs\unreal\pitch" }
$Out = [System.IO.Path]::GetFullPath($Out)
New-Item -ItemType Directory -Force $Out | Out-Null
$capture = Join-Path $PSScriptRoot "capture.ps1"
$record = Join-Path $PSScriptRoot "record.ps1"

# What the published packages carry decides what can be shown.
$packages = Join-Path $repo "packages"
$rehearsal = $PackageRoot -ne ""
$rootArgument = ""
if ($rehearsal) {
    $packages = [System.IO.Path]::GetFullPath($PackageRoot)
    if ($Out.StartsWith($repo, [System.StringComparison]::OrdinalIgnoreCase)) { throw "A rehearsal on packages that are not the published ones must be written outside the repository (-Out)." }
    $rootArgument = " -LsnPackageRoot=`"$packages`""
}
$index = Get-Content (Join-Path $packages "index.json") -Raw | ConvertFrom-Json
function Get-Site([string]$siteId) {
    $entry = $index.packages | Where-Object { $_.kind -eq "site" -and $_.site_id -eq $siteId } | Select-Object -First 1
    if (-not $entry) { throw "packages/ has no site '$siteId'" }
    $manifest = Get-Content (Join-Path $packages (Join-Path $entry.path "manifest.json")) -Raw | ConvertFrom-Json
    [pscustomobject]@{
        Id = $siteId; Name = $manifest.site.name; Package = $manifest.package_id; Contract = $manifest.contract.version; Synthetic = [bool]$manifest.synthetic
        Obstacles = [bool]($manifest.horizon.PSObject.Properties.Name -contains "obstacles")
        Calendar = [bool]($manifest.timeline.PSObject.Properties.Name -contains "calendar")
        Band = [bool]($manifest.timeline.PSObject.Properties.Name -contains "uncertainty")
    }
}
$a = Get-Site $SiteA
$b = Get-Site $SiteB
if ($a.Synthetic -or $b.Synthetic) { throw "The published packages are synthetic; pitch material is made from real packages only." }
$commit = (git -C $repo rev-parse --short HEAD).Trim()
$notes = New-Object System.Collections.Generic.List[string]
if ($rehearsal) { $notes.Add("REHEARSAL on $packages - NOT the published packages. Not for the repository, not for the pitch."); $notes.Add("") }
$notes.Add("Pitch material of the Unreal planner view. Every file is a real render of the running scene")
$notes.Add("from the published packages (packages/ of the repository). Made by unreal/Scripts/pitch.ps1")
$notes.Add("at repository commit $commit on $((Get-Date).ToUniversalTime().ToString('yyyy-MM-dd HH:mm')) UTC.")
$notes.Add("")
$notes.Add("Packages: $($a.Name): $($a.Package) (contract $($a.Contract)); $($b.Name): $($b.Package) (contract $($b.Contract)).")
$notes.Add("Published fields: obstacles and their cost: $($a.Obstacles -and $b.Obstacles); lunar-day calendar: $($a.Calendar); stated horizon error or landing ellipse: $($a.Band).")
$notes.Add("")

function Add-Note([string]$file, [string]$text) { $script:notes.Add("$file"); $script:notes.Add("    $text"); $script:notes.Add("") }
function Remove-Old([string]$file) { $path = Join-Path $Out $file; if (Test-Path $path) { Remove-Item $path } }
function Still([string]$file, [string]$text, [hashtable]$params) {
    & $capture -Out (Join-Path $Out $file) -EngineRoot $EngineRoot -ResX 1920 -ResY 1080 @params | Out-Host
    if (-not (Test-Path (Join-Path $Out $file))) { throw "$file was not written" }
    Add-Note $file $text
    # Every still in two versions: with the interface and clean (the picture with one line that
    # says what it shows). The one named above is the version meant for the slide.
    $other = @{} + $params
    $extra = "$($params.Extra)"
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($file)
    if ($extra -match "-LsnNoHud") {
        $twin = "${stem}_interface.png"
        $other.Extra = ($extra -replace "-LsnNoHud", "").Trim()
        $twinText = "The same picture with the interface of the tool."
    } else {
        $twin = "${stem}_clean.png"
        $other.Extra = (($extra -replace '-LsnPresentation', '') -replace '-LsnCaption="[^"]*"', '' -replace '-LsnPage=\S+', '' -replace '-LsnDo=page_\S+', '' -replace '-LsnControls', '').Trim() + " -LsnNoHud"
        $twinText = "The same picture without the interface: the view alone, with one line that says which site, time and package it shows."
    }
    & $capture -Out (Join-Path $Out $twin) -EngineRoot $EngineRoot -ResX 1920 -ResY 1080 @other | Out-Host
    if (-not (Test-Path (Join-Path $Out $twin))) { throw "$twin was not written" }
    Add-Note $twin $twinText
}
function Skip([string]$file, [string]$what) {
    Remove-Old $file
    Add-Note "$file  -  NOT PRODUCED" "$what is not in the published packages (contract $($a.Contract)). Run this script again once packages/ carries it."
}
$compare = "-LsnCompare=$SiteA,$SiteB$rootArgument"
$inv = [System.Globalization.CultureInfo]::InvariantCulture
function Later([string]$utc, [double]$hours) {
    [datetime]::Parse($utc, $inv, [System.Globalization.DateTimeStyles]::AdjustToUniversal).AddHours($hours).ToString("yyyy-MM-ddTHH:mm:ssZ")
}
function Clip([string]$path, [hashtable]$params) {
    if (Test-Path $path) { Remove-Item $path }
    & $record -Out $path -EngineRoot $EngineRoot -Fps 60 -ResX 1920 -ResY 1080 @params | Out-Host
    if (-not (Test-Path $path)) { throw "$path was not written" }
}
# What an earlier run of this script left behind.
Get-ChildItem -Path $Out -File | Where-Object { $_.Extension -in ".png", ".mp4" } | Remove-Item

# The key moment (item c): the Sun goes behind the costliest ridge of SiteA nearer than 1 km.
# It is chosen from the package, not by its number (obstacle ids change when a package is
# computed again): among the Sun blockers at the default observer height, the one whose peak is
# nearer than 1 km and that costs the most time. The moment is its first interval: the still two
# hours after the interval begins, the clip from eight hours before to an hour and a half after.
$siteEntry = $index.packages | Where-Object { $_.kind -eq "site" -and $_.site_id -eq $SiteA } | Select-Object -First 1
$siteManifest = Get-Content (Join-Path $packages (Join-Path $siteEntry.path "manifest.json")) -Raw | ConvertFrom-Json
$defaultHeight = [int]$siteManifest.horizon.default_height_index
$near = $siteManifest.timeline.blockers | Where-Object { $_.body -eq "SUN" -and [int]$_.height_index -eq $defaultHeight -and [double]$_.peak_distance_m -lt 1000.0 } |
    Sort-Object -Property @{ Expression = { [double]$_.lost_s }; Descending = $true } | Select-Object -First 1
if (-not $near) { throw "$($a.Name): no Sun blocker nearer than 1 km in the package" }
$nearDistance = [string]::Format($inv, "{0:F0} m", [double]$near.peak_distance_m)
$nearRidge = "the ridge $nearDistance away at azimuth $(([double]$near.peak_azimuth_deg).ToString('0.0', $inv)) deg"
$nearCost = "$(([double]$near.lost_s / 3600.0).ToString('0.0', $inv)) h of Sun"
$nearBegins = [datetime]::Parse($near.intervals_utc[0][0], $inv, [System.Globalization.DateTimeStyles]::AdjustToUniversal)
$nearHour = New-Object DateTime ($nearBegins.Year, $nearBegins.Month, $nearBegins.Day, $nearBegins.Hour, 0, 0, [DateTimeKind]::Utc)
if ($NearStillUtc -eq "") { $NearStillUtc = $nearHour.AddHours(2).ToString("yyyy-MM-ddTHH:mm:ssZ") }
if ($NearFromUtc -eq "") { $NearFromUtc = $nearHour.AddHours(-8).ToString("yyyy-MM-ddTHH:mm:ssZ") }
if ($NearToUtc -eq "") { $NearToUtc = $nearHour.AddHours(1.5).ToString("yyyy-MM-ddTHH:mm:ssZ") }
$nearCaption = "A ridge $nearDistance away is about to hide the Sun|The Sun is behind a ridge $nearDistance away: the package names it and what it costs"
$nearExtra = "-LsnFollowSun -LsnPresentation -LsnCaption=`"$nearCaption`"$rootArgument"

if ($Only -ne "clip") {
    Still "a_opening_south_pole_wide.png" "Opening. The south-polar terrain around $($a.Name) at $WideUtc, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg, the Sun low over the horizon on the left. LOLA elevation data sampled for drawing; a weak fill light is on as a viewing aid, the shadows are black without it." @{ Site = $SiteA; Utc = $WideUtc; Yaw = 128; Pitch = -8; Fov = 60; Extra = "-LsnCameraUp=12000 -LsnCameraBack=30000 -LsnNoHud -LsnViewingAidFill$rootArgument" }
    Still "b_product_two_sites.png" "Product. $($a.Name) and $($b.Name) side by side at $HiddenUtc, observer 2 m, each view on its own Sun: the default view, drawer closed, the obstacle view switched off (no outline, no card)." @{ Utc = $HiddenUtc; Pitch = 0.5; Fov = 30; Extra = "$compare -LsnDo=obstacle" }
    Still "c_key_moment_near_ridge.png" "Key moment. $($a.Name) at $NearStillUtc, observer 2 m, looking at the Sun's azimuth: the Sun is behind $nearRidge, which costs $nearCost in the window of the package (14 November 2026 to 14 November 2028). The package flags it as within 1 km: it depends on single pixels of the elevation model (here the 5 m site model)." @{ Site = $SiteA; Utc = $NearStillUtc; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun$rootArgument" }
    Still "d_calendar_drawer.png" "$($a.Name) at ${BandUtc}: the drawer open on the lunar-day calendar and the landing windows of the example requirement." @{ Site = $SiteA; Utc = $BandUtc; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun -LsnDo=page_calendar$rootArgument" }
    Still "d_uncertainty_drawer.png" "$($a.Name) at ${BandUtc}: the drawer open on the uncertainty page (the survey of the stated landing ellipse; the band of each event stands under its countdown)." @{ Site = $SiteA; Utc = $BandUtc; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun -LsnDo=page_uncertainty$rootArgument" }
    Still "e_lander_lit_side.png" "$($a.Name) at ${WideUtc}: a camera on the lander's sunlit side, the Sun 50 deg off the view axis behind it (not the observer's view), with the mast that carries the observer in the background. Lander, mast and boulders are scale objects of the team's own design, not part of the package." @{ Site = $SiteA; Utc = $WideUtc; Extra = "-LsnView=lit -LsnNoHud$rootArgument" }
}
if ($Only -ne "stills") {
    $clipFile = Join-Path $Out "c_key_moment_near_ridge.mp4"
    Clip $clipFile @{ Site = $SiteA; FromUtc = $NearFromUtc; ToUtc = $NearToUtc; Seconds = 9; Pitch = 0.5; Fov = 30; Extra = $nearExtra }
    Add-Note "c_key_moment_near_ridge.mp4" "Key moment, 9 s at 60 frames per second. $($a.Name), observer 2 m, the view on the Sun; time runs from $NearFromUtc to $NearToUtc. The Sun goes behind ${nearRidge}: when the package gives the Sun as partly hidden the outline of the ridge lights up and the card with its cost appears; the caption changes when the package gives the Sun as hidden."

    # One video of at most 28 s (item f): five parts, each a real render, joined without any added text.
    $parts = Join-Path $env:TEMP "lsn_pitch_parts"
    New-Item -ItemType Directory -Force $parts | Out-Null
    $list = @(
        @{ File = "1_arrival.mp4"; P = @{ Site = $SiteA; FromUtc = $WideUtc; ToUtc = (Later $WideUtc 0.2); Seconds = 5.9; Extra = "-LsnView=hero -LsnDo=arrival -LsnArrivalSeconds=5.4 -LsnNoHud$rootArgument" } },
        @{ File = "2_two_sites.mp4"; P = @{ FromUtc = $ClipFromUtc; ToUtc = $ClipToUtc; Seconds = 6; Pitch = 0.5; Fov = 30; Extra = "$compare -LsnPresentation -LsnCaption=`"$ClipCaption`"" } },
        @{ File = "3_near_ridge.mp4"; P = @{ Site = $SiteA; FromUtc = $NearFromUtc; ToUtc = $NearToUtc; Seconds = 8; Pitch = 0.5; Fov = 30; Extra = $nearExtra } },
        @{ File = "4_calendar.mp4"; P = @{ Site = $SiteA; FromUtc = $BandUtc; ToUtc = (Later $BandUtc 120); Seconds = 4; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun -LsnDo=page_calendar$rootArgument" } },
        @{ File = "5_wide.mp4"; P = @{ Site = $SiteA; FromUtc = $WideUtc; ToUtc = (Later $WideUtc 36); Seconds = 4; Extra = "-LsnView=wide -LsnNoHud$rootArgument" } }
    )
    $inputs = @()
    foreach ($part in $list) {
        $path = Join-Path $parts $part.File
        Clip $path $part.P
        $inputs += @("-i", $path)
    }
    $video = Join-Path $Out "f_pitch_video_1080p60.mp4"
    & ffmpeg -hide_banner -loglevel error -y @inputs -filter_complex "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0,fps=60,format=yuv420p" -c:v libx264 -crf 18 -an -movflags +faststart $video
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $video)) { throw "the video was not written" }
    $seconds = [double](& ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 $video)
    if ($seconds -gt 28.0) { throw ("the video is {0:N2} s long, more than 28 s" -f $seconds) }
    Add-Note "f_pitch_video_1080p60.mp4" ("One video, {0} s, 1920 x 1080 at 60 frames per second, H.264, no audio. Five parts, each a real render of the running scene: (1) 5.9 s, a camera move from 9 km above down to the lander at $($a.Name), $WideUtc (a camera move only; no descent is simulated); (2) 6 s, $($a.Name) and $($b.Name) side by side from $ClipFromUtc to ${ClipToUtc}: the Sun sets behind a ridge on the left and stays up on the right; (3) 8 s, the key moment as in c_key_moment_near_ridge.mp4; (4) 4 s, the calendar drawer while five days pass from ${BandUtc}; (5) 4 s, the wide view with lander, mast and boulders while 36 h pass from $WideUtc. The only text is that of the interface and its caption line." -f $seconds.ToString("0.00", $inv))
}

$notes.Add("The ground is LOLA elevation data sampled on 480 rings per azimuth (the 5 m site models near the three project sites). Roughness and small craters finer than that data are")
$notes.Add("illustrative shading computed in the surface shader: positions, shadows and the horizon are those of the data. Stars are the")
$notes.Add("Yale Bright Star Catalogue, turned for the date. Lander, mast and boulders are scale objects of the team's own design, not part")
$notes.Add("of any package. Surface shading, exposure, the glare of the Sun and the fill light while the Sun is down are display choices")
$notes.Add("(see unreal/README.md). The Earth carries the Blue Marble map of NASA (see CREDITS.md). Not in any of these: an atmosphere, clouds or night lights.")
$notesFile = Join-Path $Out "README.txt"
if ($Only -ne "all" -and (Test-Path $notesFile)) { Add-Content -Path $notesFile -Encoding ascii -Value @("", "---- partial run (-Only $Only) ----") ; Add-Content -Path $notesFile -Encoding ascii -Value $notes }
else { Set-Content -Path $notesFile -Encoding ascii -Value $notes }
Write-Host "Pitch material written to $Out"
