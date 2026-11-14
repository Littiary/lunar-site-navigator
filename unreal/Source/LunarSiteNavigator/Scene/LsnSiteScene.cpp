#include "Scene/LsnSiteScene.h"

#include "LunarSiteNavigator.h"
#include "Components/DirectionalLightComponent.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"

namespace
{
	/** Display values of stage 1. They are not photometry. */
	constexpr float SunLightLux = 10.0f;
	constexpr float SunDiscEmissive = 30.0f;
	constexpr float HorizonLineEmissive = 3.0f;
	constexpr float RegolithAlbedo = 0.13f;

	/** How far below the lowest horizon elevation the reference sphere is kept, and how far below the site. */
	constexpr double SphereCapMarginDeg = 1.0;
	constexpr double SphereSinkM = 500.0;
	constexpr double SphereGridStepDeg = 2.0;

	UProceduralMeshComponent* MakeMeshComponent(AActor* Owner, const TCHAR* Name, bool bCastShadow)
	{
		UProceduralMeshComponent* Component = Owner->CreateDefaultSubobject<UProceduralMeshComponent>(Name);
		Component->SetMobility(EComponentMobility::Movable);
		Component->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Component->SetCastShadow(bCastShadow);
		Component->bCastShadowAsTwoSided = bCastShadow;
		Component->bUseAsyncCooking = false;
		Component->bAffectDistanceFieldLighting = false;
		return Component;
	}
}

ALsnSiteScene::ALsnSiteScene()
{
	PrimaryActorTick.bCanEverTick = false;

	USceneComponent* Root = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Root->SetMobility(EComponentMobility::Movable);
	SetRootComponent(Root);

	Terrain = MakeMeshComponent(this, TEXT("Terrain"), true);
	MoonSphere = MakeMeshComponent(this, TEXT("MoonSphere"), false);
	HorizonLine = MakeMeshComponent(this, TEXT("HorizonLine"), false);
	SunDisc = MakeMeshComponent(this, TEXT("SunDisc"), false);
	EarthDisc = MakeMeshComponent(this, TEXT("EarthDisc"), false);
	for (UProceduralMeshComponent* Component : { Terrain.Get(), MoonSphere.Get(), HorizonLine.Get(), SunDisc.Get(), EarthDisc.Get() })
	{
		Component->SetupAttachment(Root);
	}
	HorizonLine->SetVisibility(false);

	SunLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("SunLight"));
	SunLight->SetupAttachment(Root);
	SunLight->SetMobility(EComponentMobility::Movable);
	SunLight->SetIntensity(SunLightLux);
	SunLight->SetCastShadows(true);
	SunLight->SetAtmosphereSunLight(false);
	// The terrain reaches out to the package's horizon search radius; shadows must not be cut off before it.
	SunLight->DynamicShadowDistanceMovableLight = 1.0e9f;
	SunLight->SetVisibility(false);
}

FVector ALsnSiteScene::GetEyeUnreal() const
{
	const double EyeHeightM = bHasPackage ? Package.ObserverHeightsM[HeightIndex] : 0.0;
	return FVector(0.0, 0.0, EyeHeightM * FLsnSiteFrame::CmPerM);
}

FVector ALsnSiteScene::GetSunDirectionFromLight() const
{
	return -SunLight->GetComponentRotation().Vector();
}

bool ALsnSiteScene::LoadPackageDirectory(const FString& PackageDirectory, FString& OutError)
{
	FLsnSitePackage Loaded;
	if (!LsnPackageIO::LoadSitePackage(PackageDirectory, Loaded, OutError))
	{
		UE_LOG(LogLsn, Error, TEXT("Package refused: %s"), *OutError);
		return false;
	}
	Package = MoveTemp(Loaded);
	Frame = FLsnSiteFrame::Make(Package.LatDeg, Package.LonDeg, Package.ReferenceRadiusM, Package.SurfaceHeightM);
	bHasPackage = true;
	HeightIndex = Package.DefaultHeightIndex;
	TimeIndex = 0;

	if (!SurfaceMaterial)
	{
		SurfaceMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Lsn/M_LsnSurface.M_LsnSurface"));
		if (!SurfaceMaterial)
		{
			UE_LOG(LogLsn, Warning, TEXT("Material /Game/Lsn/M_LsnSurface is missing; run Scripts/make_materials.py. Using the engine default material."));
			SurfaceMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
		}
	}
	if (!EmissiveMaterial)
	{
		EmissiveMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Lsn/M_LsnEmissive.M_LsnEmissive"));
		if (!EmissiveMaterial)
		{
			UE_LOG(LogLsn, Warning, TEXT("Material /Game/Lsn/M_LsnEmissive is missing; run Scripts/make_materials.py. Using the engine default material."));
			EmissiveMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
		}
	}

	RebuildGeometry();
	SetTimeIndex(0);

	UE_LOG(LogLsn, Display, TEXT("Loaded site package %s (%s), contract %s, synthetic=%d, timeline=%d"),
		*Package.PackageId, *Package.SiteId, *Package.ContractVersion, Package.bSynthetic ? 1 : 0, Package.bHasTimeline ? 1 : 0);
	return true;
}

bool ALsnSiteScene::SetHeightIndex(int32 NewHeightIndex)
{
	if (!bHasPackage || NewHeightIndex < 0 || NewHeightIndex >= Package.NumHeights())
	{
		return false;
	}
	HeightIndex = NewHeightIndex;
	RebuildGeometry();
	SetTimeIndex(TimeIndex);
	return true;
}

void ALsnSiteScene::ApplyMesh(UProceduralMeshComponent* Component, const FLsnMeshData& Mesh, UMaterialInterface* Material)
{
	Component->ClearAllMeshSections();
	Component->CreateMeshSection(0, Mesh.Positions, Mesh.Triangles, Mesh.Normals, Mesh.UV0, Mesh.Colors, TArray<FProcMeshTangent>(), false);
	Component->SetMaterial(0, Material);
}

void ALsnSiteScene::RebuildGeometry()
{
	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];

	// Terrain: its outer edge is the package horizon.
	FLsnHorizonTerrainParams TerrainParams;
	TerrainParams.Albedo = RegolithAlbedo;
	LsnMesh::BuildHorizonTerrain(Frame, Package, HeightIndex, TerrainParams, TerrainData, SkippedHorizonSamples);
	TerrainData.RoundPositionsToFloat();
	Terrain->SetWorldLocation(FVector::ZeroVector);
	ApplyMesh(Terrain, TerrainData, SurfaceMaterial);
	if (SkippedHorizonSamples > 0)
	{
		UE_LOG(LogLsn, Warning, TEXT("%d horizon samples could not be placed (unknown values in the package)."), SkippedHorizonSamples);
	}

	// Reference sphere, kept below everything the eye can see near the site.
	double LowestHorizonDeg = TNumericLimits<double>::Max();
	for (int32 A = 0; A < Package.AzimuthCount; ++A)
	{
		const double El = Package.HorizonElevationAt(HeightIndex, A);
		if (!FMath::IsNaN(El))
		{
			LowestHorizonDeg = FMath::Min(LowestHorizonDeg, El);
		}
	}
	if (LowestHorizonDeg == TNumericLimits<double>::Max())
	{
		LowestHorizonDeg = -45.0;
	}
	const double CapDeg = FMath::Max(LowestHorizonDeg - SphereCapMarginDeg, -89.0);
	const FLsnSiteFrame& F = Frame;
	LsnMesh::BuildMoonSphere(Frame, SphereGridStepDeg,
		[&F, EyeHeightM, CapDeg](double AngleFromSiteRad)
		{
			return LsnMesh::SunkSphereRadiusM(F, EyeHeightM, CapDeg, SphereSinkM, AngleFromSiteRad);
		},
		RegolithAlbedo, MoonSphereData);
	MoonSphereData.RoundPositionsToFloat();
	MoonSphere->SetWorldLocation(Frame.MoonCentreUnreal());
	ApplyMesh(MoonSphere, MoonSphereData, SurfaceMaterial);

	// Overlay: the package horizon as a line.
	FLsnMeshData LineData;
	LsnMesh::BuildHorizonLine(Frame, Package, HeightIndex, 0.04, FColor(255, 120, 20, 255), LineData);
	HorizonLine->SetWorldLocation(FVector::ZeroVector);
	UMaterialInstanceDynamic* LineMaterial = UMaterialInstanceDynamic::Create(EmissiveMaterial, this);
	LineMaterial->SetScalarParameterValue(TEXT("Intensity"), HorizonLineEmissive);
	ApplyMesh(HorizonLine, LineData, LineMaterial);

	// Discs.
	UMaterialInstanceDynamic* SunMaterial = UMaterialInstanceDynamic::Create(EmissiveMaterial, this);
	SunMaterial->SetScalarParameterValue(TEXT("Intensity"), SunDiscEmissive);
	EnsureUnitSphere(SunDisc, FColor(255, 250, 240, 255), SunMaterial);
	// Placeholder colour until a NASA Earth texture is credited and added.
	EnsureUnitSphere(EarthDisc, FColor(40, 70, 130, 255), SurfaceMaterial);
}

void ALsnSiteScene::EnsureUnitSphere(UProceduralMeshComponent* Component, const FColor& Color, UMaterialInterface* Material)
{
	FLsnMeshData Sphere;
	LsnMesh::BuildUnitSphere(32, 64, Color, Sphere);
	ApplyMesh(Component, Sphere, Material);
}

void ALsnSiteScene::PlaceDisc(UProceduralMeshComponent* Disc, const FLsnBodySeries* Series, double ProxyDistanceM)
{
	// A disc needs a direction and an angular radius; both are optional parts
	// of a package. Without them the disc is hidden rather than guessed.
	if (!Series || !Series->AzimuthDeg.IsValidIndex(TimeIndex) || !Series->AngularRadiusDeg.IsValidIndex(TimeIndex))
	{
		Disc->SetVisibility(false);
		return;
	}
	const double Az = Series->AzimuthDeg[TimeIndex];
	const double El = Series->ElevationDeg[TimeIndex];
	const double AngularRadiusDeg = Series->AngularRadiusDeg[TimeIndex];
	if (FMath::IsNaN(Az) || FMath::IsNaN(El) || FMath::IsNaN(AngularRadiusDeg))
	{
		Disc->SetVisibility(false);
		return;
	}
	const double DistanceCm = ProxyDistanceM * FLsnSiteFrame::CmPerM;
	// A sphere of radius r at distance d subtends an angular radius asin(r / d).
	const double RadiusCm = DistanceCm * FMath::Sin(FMath::DegreesToRadians(AngularRadiusDeg));
	Disc->SetWorldLocation(GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(Az, El) * DistanceCm);
	Disc->SetWorldScale3D(FVector(RadiusCm));
	Disc->SetVisibility(true);
}

bool ALsnSiteScene::SetTimeIndex(int32 NewTimeIndex)
{
	if (!bHasPackage || !Package.bHasTimeline)
	{
		// No timeline in the package: no Sun, no Earth, no light direction to show.
		SunLight->SetVisibility(false);
		SunDisc->SetVisibility(false);
		EarthDisc->SetVisibility(false);
		return false;
	}
	if (NewTimeIndex < 0 || NewTimeIndex >= Package.Time.Count)
	{
		return false;
	}
	TimeIndex = NewTimeIndex;

	const FLsnBodySeries* Sun = Package.FindSeries(TEXT("SUN"));
	const FLsnBodySeries* Earth = Package.FindSeries(TEXT("EARTH"));

	if (Sun && Sun->AzimuthDeg.IsValidIndex(TimeIndex) && !FMath::IsNaN(Sun->AzimuthDeg[TimeIndex]) && !FMath::IsNaN(Sun->ElevationDeg[TimeIndex]))
	{
		const FVector ToSun = FLsnSiteFrame::AzElToUnrealDir(Sun->AzimuthDeg[TimeIndex], Sun->ElevationDeg[TimeIndex]);
		// A directional light shines along its forward axis: away from the Sun.
		SunLight->SetWorldRotation((-ToSun).Rotation());
		if (Sun->AngularRadiusDeg.IsValidIndex(TimeIndex) && !FMath::IsNaN(Sun->AngularRadiusDeg[TimeIndex]))
		{
			// The engine's source angle is the angular diameter of the light source.
			SunLight->SetLightSourceAngle(2.0f * Sun->AngularRadiusDeg[TimeIndex]);
		}
		SunLight->SetVisibility(true);
	}
	else
	{
		SunLight->SetVisibility(false);
	}
	PlaceDisc(SunDisc, Sun, SunProxyDistanceM);
	PlaceDisc(EarthDisc, Earth, EarthProxyDistanceM);
	return true;
}

void ALsnSiteScene::SetHorizonLineVisible(bool bVisible)
{
	HorizonLine->SetVisibility(bVisible);
}

bool ALsnSiteScene::IsHorizonLineVisible() const
{
	return HorizonLine->IsVisible();
}
