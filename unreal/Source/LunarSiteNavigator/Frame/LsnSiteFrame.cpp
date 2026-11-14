#include "Frame/LsnSiteFrame.h"

// Stub: the frame tests are written first and must fail against this.

FLsnSiteFrame FLsnSiteFrame::Make(double, double, double, double) { return FLsnSiteFrame(); }
FVector FLsnSiteFrame::AzElToUnrealDir(double, double) { return FVector::ZeroVector; }
void FLsnSiteFrame::UnrealDirToAzEl(const FVector&, double& OutAzimuthDeg, double& OutElevationDeg) { OutAzimuthDeg = 0.0; OutElevationDeg = 0.0; }
FVector FLsnSiteFrame::EnuMToUnreal(const FVector&) { return FVector::ZeroVector; }
FVector FLsnSiteFrame::UnrealToEnuM(const FVector&) { return FVector::ZeroVector; }
FVector FLsnSiteFrame::BodyDirToUnreal(const FVector&) const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::UnrealDirToBody(const FVector&) const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::BodyPointMToUnreal(const FVector&) const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::UnrealToBodyPointM(const FVector&) const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::MoonCentreUnreal() const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::LatLonToBodyDir(double, double) { return FVector::ZeroVector; }
FVector FLsnSiteFrame::SurfacePointUnreal(double, double, double) const { return FVector::ZeroVector; }
FVector FLsnSiteFrame::SightPointUnreal(double, double, double, double) { return FVector::ZeroVector; }
