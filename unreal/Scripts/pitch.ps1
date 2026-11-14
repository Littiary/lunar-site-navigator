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
}
function Skip([string]$file, [string]$what) {
    Remove-Old $file
    Add-Note "$file  -  NOT PRODUCED" "$what is not in the published packages (contract $($a.Contract)). Run this script again once packages/ carries it."
}
$compare = "-LsnCompare=$SiteA,$SiteB$rootArgument"

if ($Only -ne "stills") {
    $file = "pitch_two_sites_sunset_1080p60.mp4"
    $story = if ($a.Obstacles) { "the blocking ridge lights up with the hours it costs" } else { "the ridge is NOT highlighted and no cost is shown, because the published packages (contract $($a.Contract)) carry no obstacles" }
    & $record -Out (Join-Path $Out $file) -EngineRoot $EngineRoot -FromUtc $ClipFromUtc -ToUtc $ClipToUtc -Seconds $ClipSeconds -Fps 60 -ResX 1920 -ResY 1080 -Pitch 0.5 -Fov 30 -Extra "$compare -LsnPresentation -LsnCaption=`"$ClipCaption`"" | Out-Host
    if (-not (Test-Path (Join-Path $Out $file))) { throw "$file was not written" }
    Add-Note $file "$($a.Name) (left) and $($b.Name) (right), the same instant in both halves, observer 2 m, each view on its own Sun. Time runs from $ClipFromUtc to $ClipToUtc in $ClipSeconds s at 60 frames per second; the Sun sets behind a ridge at the left site and stays up at the right one; $story. Shown without the controls of the tool; the caption across the picture is part of the clip, and its second text appears when the package gives the Sun of the left site as hidden."
}
if ($Only -ne "clip") {
    Still "still_1_planner_two_sites.png" "$($a.Name) and $($b.Name) side by side at $HiddenUtc, observer 2 m: state chips and time strip of each site, without the controls, with a caption; readable when shown small." @{ Utc = $HiddenUtc; Pitch = 0.5; Fov = 30; Extra = "$compare -LsnPresentation -LsnCaption=`"One instant, two sites: Sun, Earth and landing state of each, read from the computed packages`"" }
    Still "still_1b_planner_with_controls.png" "The same view with the controls of the tool: the three main actions, the horizon all round and the grouped bar. Dense; meant for a close look, not for a small picture on a slide." @{ Utc = $HiddenUtc; Pitch = 0.5; Fov = 30; Extra = $compare }
    if ($a.Obstacles) {
        Still "still_2_obstacle_highlight.png" "$($a.Name) at $HiddenUtc, observer 2 m: the Sun behind the ridge the package names, its distance, azimuth and the hours it costs in the computed window." @{ Site = $SiteA; Utc = $HiddenUtc; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun -LsnPresentation -LsnCaption=`"Which terrain hides the Sun, how far away it is, and how many hours of sunlight it costs`"$rootArgument" }
    } else { Skip "still_2_obstacle_highlight.png" "The obstacle that hides the Sun and the hours it costs (contract 0.2, SPEC 5.5)" }
    if ($a.Calendar) {
        Still "still_3_calendar.png" "$($a.Name) and $($b.Name) at ${HiddenUtc}: lunar-day calendar of both sites on one time axis, landing windows of the example requirement and the slip of a landing at that time." @{ Utc = $HiddenUtc; Pitch = 0.5; Fov = 30; Extra = "$compare -LsnPage=calendar" }
    } else { Skip "still_3_calendar.png" "The lunar-day calendar and the landing windows (contract 0.3, SPEC 5.6)" }
    if ($a.Band) {
        Still "still_4_uncertainty_band.png" "$($a.Name) at $BandUtc, observer 2 m: the band of the stated horizon error on the time strips and under the countdown, and the survey of the stated landing ellipse." @{ Site = $SiteA; Utc = $BandUtc; Pitch = 0.5; Fov = 30; Extra = "-LsnFollowSun -LsnPage=uncertainty$rootArgument" }
    } else { Skip "still_4_uncertainty_band.png" "The band for a stated horizon error and the landing-ellipse survey (contract 0.4, SPEC 5.7)" }
    Still "still_5_south_pole_wide.png" "The south-polar terrain around $($a.Name) at $WideUtc, seen from 12 km above and 30 km behind the site (not the observer's view), looking towards azimuth 128 deg: LOLA elevation data sampled for drawing, the Sun and the Earth in the directions and sizes of the package. A weak fill light is on for this still only, as a viewing aid, so that the terrain in shadow can be told apart; without it shadows are black (the still says so)." @{ Site = $SiteA; Utc = $WideUtc; Yaw = 128; Pitch = -8; Fov = 60; Extra = "-LsnCameraUp=12000 -LsnCameraBack=30000 -LsnNoHud -LsnViewingAidFill$rootArgument" }
    Still "still_7_mast_and_lander.png" "$($a.Name) at ${WideUtc}: the camera stands 5 m above and 22 m behind the observer (not the observer's view) and shows the mast that carries the observer at 10 m and the lander beside it. Both are scale objects of the team's own design, not part of the package." @{ Site = $SiteA; Utc = $WideUtc; Yaw = 140; Pitch = -6; Fov = 50; Extra = "-LsnCameraUp=5 -LsnCameraBack=22 -LsnHeight=4 -LsnNoHud$rootArgument" }
    Still "still_6_astronaut_height.png" "$($a.Name) at $WideUtc from the observer height of 2 m, looking towards azimuth 128 deg with a 62 deg field of view: the Sun low on the left, the Earth as a crescent on the right." @{ Site = $SiteA; Utc = $WideUtc; Yaw = 128; Pitch = 3; Fov = 62; Extra = "-LsnNoHud$rootArgument" }
    Still "still_8_camera_near_lander.png" "$($a.Name) at ${WideUtc}: a camera 16 m behind the lander and 5.5 m up, looking towards the Sun (not the observer's view). The lander is a scale object of the team's own design; the ground, the light and the shadows are those of the package and the elevation data." @{ Site = $SiteA; Utc = $WideUtc; Extra = "-LsnView=hero -LsnNoHud$rootArgument" }
    Still "still_9_wide_view.png" "$($a.Name) at ${WideUtc}: the wide view from 120 m away and 30 m up with the Sun 60 deg to the right, outside the picture (not the observer's view): lander, mast and boulders with their shadows, for scale." @{ Site = $SiteA; Utc = $WideUtc; Extra = "-LsnView=wide -LsnNoHud$rootArgument" }
    # The recorder plays a stretch of the timeline: ten minutes of the package pass during the move.
    $arrivalEndUtc = [datetime]::Parse($WideUtc, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::AdjustToUniversal).AddMinutes(10).ToString("yyyy-MM-ddTHH:mm:ssZ")
    Remove-Old "clip_arrival.mp4"
    & $record -Out (Join-Path $Out "clip_arrival.mp4") -EngineRoot $EngineRoot -Site $SiteA -FromUtc $WideUtc -ToUtc $arrivalEndUtc -Seconds 10 -Fps 60 -ResX 1920 -ResY 1080 -Extra "-LsnView=hero -LsnDo=arrival -LsnNoHud$rootArgument" | Out-Host
    if (-not (Test-Path (Join-Path $Out "clip_arrival.mp4"))) { throw "clip_arrival.mp4 was not written" }
    Add-Note "clip_arrival.mp4" "$($a.Name) at ${WideUtc}: a camera move of 8 s from 9 km above and 26 km behind the site down to the camera near the lander, for the opening of the video. A camera move only: no descent, trajectory or engine is simulated, and ten minutes of the package pass during the move."
}
$notes.Add("The ground is LOLA elevation data sampled on 320 rings per azimuth. Roughness and small craters finer than that data are")
$notes.Add("illustrative shading computed in the surface shader: positions, shadows and the horizon are those of the data. Stars are the")
$notes.Add("Yale Bright Star Catalogue, turned for the date. Lander, mast and boulders are scale objects of the team's own design, not part")
$notes.Add("of any package. Surface shading, exposure, the glare of the Sun and the fill light while the Sun is down are display choices")
$notes.Add("(see unreal/README.md). Not in any of these: image textures, an atmosphere or a map of the Earth.")
$notesFile = Join-Path $Out "README.txt"
if ($Only -ne "all" -and (Test-Path $notesFile)) { Add-Content -Path $notesFile -Encoding ascii -Value @("", "---- partial run (-Only $Only) ----") ; Add-Content -Path $notesFile -Encoding ascii -Value $notes }
else { Set-Content -Path $notesFile -Encoding ascii -Value $notes }
Write-Host "Pitch material written to $Out"
