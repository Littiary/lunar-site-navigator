#include "Scene/LsnSiteScene.h"

#include "LunarSiteNavigator.h"
#include "Components/DirectionalLightComponent.h"
#include "Materials/Material.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Mesh/LsnProps.h"
#include "Misc/Paths.h"
#include "ProceduralMeshComponent.h"

namespace
{
	/** Display values of stage 1. They are not photometry. */
	constexpr float SunLightLux = 10.0f;
	constexpr float FillLightLux = 0.25f;
	constexpr float SunDiscEmissive = 30.0f;
	constexpr float HorizonLineEmissive = 3.0f;
	constexpr float ObstacleEmissive = 6.0f;
	/** Angular height of the highlight band above the horizon. A drawing choice. */
	constexpr double ObstacleBandDeg = 0.10;
	const FColor SunObstacleColor(255, 70, 10, 255);
	const FColor EarthObstacleColor(20, 200, 255, 255);
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
	SunObstacle = MakeMeshComponent(this, TEXT("SunObstacle"), false);
	EarthObstacle = MakeMeshComponent(this, TEXT("EarthObstacle"), false);
	SunDisc = MakeMeshComponent(this, TEXT("SunDisc"), false);
	EarthDisc = MakeMeshComponent(this, TEXT("EarthDisc"), false);
	ScaleObjects = MakeMeshComponent(this, TEXT("ScaleObjects"), true);
	Mast = MakeMeshComponent(this, TEXT("Mast"), true);
	for (UProceduralMeshComponent* Component : { Terrain.Get(), MoonSphere.Get(), HorizonLine.Get(), SunObstacle.Get(), EarthObstacle.Get(), SunDisc.Get(), EarthDisc.Get(), ScaleObjects.Get(), Mast.Get() })
	{
		Component->SetupAttachment(Root);
	}
	ScaleObjects->SetVisibility(false);
	Mast->SetVisibility(false);
	bScaleObjectsVisible = !FParse::Param(FCommandLine::Get(), TEXT("LsnNoScaleObjects"));
	HorizonLine->SetVisibility(false);
	SunObstacle->SetVisibility(false);
	EarthObstacle->SetVisibility(false);

	SunLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("SunLight"));
	SunLight->SetupAttachment(Root);
	SunLight->SetMobility(EComponentMobility::Movable);
	SunLight->SetIntensity(SunLightLux);
	// -LsnNoShadows exists for one measurement: whether a pattern on the ground is a shadow or shading.
	SunLight->SetCastShadows(!FParse::Param(FCommandLine::Get(), TEXT("LsnNoShadows")));
	SunLight->SetAtmosphereSunLight(false);
	// The terrain reaches out to the package's horizon search radius; shadows must not be cut off before it.
	SunLight->DynamicShadowDistanceMovableLight = 1.0e9f;
	SunLight->SetVisibility(false);

	FillLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("FillLight"));
	FillLight->SetupAttachment(Root);
	FillLight->SetMobility(EComponentMobility::Movable);
	FillLight->SetIntensity(FillLightLux);
	FillLight->SetCastShadows(false);
	FillLight->SetAtmosphereSunLight(false);
	FillLight->SetWorldRotation(FRotator(-90.0, 0.0, 0.0));
	// The Sun is the light the engine treats as the main directional light.
	SunLight->ForwardShadingPriority = 1;
	FillLight->ForwardShadingPriority = 0;
}

void ALsnSiteScene::SetObstacleViewEnabled(bool bEnabled)
{
	bObstacleViewEnabled = bEnabled;
	SetTimePosition(TimePosition);
	if (!bEnabled)
	{
		SunObstacle->SetVisibility(false);
		EarthObstacle->SetVisibility(false);
	}
}

UProceduralMeshComponent* ALsnSiteScene::GetObstacleHighlight(const TCHAR* Body) const
{
	return FCString::Stricmp(Body, TEXT("EARTH")) == 0 ? EarthObstacle : SunObstacle;
}

void ALsnSiteScene::UpdateObstacleHighlight(const TCHAR* Body, UProceduralMeshComponent* Highlight, int32& InOutShownObstacleId, const FColor& Color)
{
	// Which obstacle, and whether the body is hidden behind it, is read from the package
	// at the sample the time position belongs to. The scene only draws the run it is given.
	FLsnBlocking Blocking;
	if (!bObstacleViewEnabled || !bHasPackage || !Package.BlockingAt(Body, HeightIndex, TimeIndex, Blocking) || !Blocking.bHiddenOrPartly || !Blocking.Obstacle)
	{
		Highlight->SetVisibility(false);
		return;
	}
	if (InOutShownObstacleId != Blocking.ObstacleId)
	{
		TArray<int32> Run;
		Package.ObstacleRun(*Blocking.Obstacle, Run);
		FLsnMeshData Band;
		LsnMesh::BuildObstacleBand(Frame, Package, HeightIndex, Run, ObstacleBandDeg, Color, Band);
		UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(EmissiveMaterial, this);
		Material->SetScalarParameterValue(TEXT("Intensity"), ObstacleEmissive);
		Highlight->SetRelativeLocation(FVector::ZeroVector);
		ApplyMesh(Highlight, Band, Material);
		InOutShownObstacleId = Blocking.ObstacleId;
	}
	Highlight->SetVisibility(true);
}

void ALsnSiteScene::SetFillLightVisible(bool bVisible)
{
	FillLight->SetVisibility(bVisible);
}

bool ALsnSiteScene::IsFillLightVisible() const
{
	return FillLight->IsVisible();
}

FVector ALsnSiteScene::GetEyeUnreal() const
{
	const double EyeHeightM = bHasPackage ? Package.ObserverHeightsM[HeightIndex] : 0.0;
	return GetActorLocation() + FVector(0.0, 0.0, EyeHeightM * FLsnSiteFrame::CmPerM);
}

void ALsnSiteScene::SetSceneSlot(int32 Slot)
{
	SceneSlot = FMath::Clamp(Slot, 0, 2);
	const bool b0 = SceneSlot == 0, b1 = SceneSlot == 1, b2 = SceneSlot == 2;
	SunLight->SetLightingChannels(b0, b1, b2);
	FillLight->SetLightingChannels(b0, b1, b2);
	for (UProceduralMeshComponent* Component : { Terrain.Get(), MoonSphere.Get(), HorizonLine.Get(), SunObstacle.Get(), EarthObstacle.Get(), SunDisc.Get(), EarthDisc.Get(), ScaleObjects.Get(), Mast.Get() })
	{
		Component->SetLightingChannels(b0, b1, b2);
	}
}

FString ALsnSiteScene::GetGroundNote() const
{
	if (!bHasRealTerrain)
	{
		return TEXT("Ground between the site and the horizon line is a placeholder surface, not elevation data.");
	}
	FString Note = FString::Printf(TEXT("Ground: elevation data %s sampled on %d rings per azimuth (drawing only); the horizon line is the package's."),
		*TerrainGrid.DemSetId, TerrainGrid.RingDistanceM.Num());
	if (UnknownTerrainSamples > 0)
	{
		Note += FString::Printf(TEXT(" %d samples have no data."), UnknownTerrainSamples);
	}
	if (bHasScaleObjects && bScaleObjectsVisible)
	{
		Note += TEXT(" Lander, mast and boulders are scale objects, not part of the package.");
	}
	return Note;
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

	// Real elevation samples for this very package, if they were exported; else the placeholder surface.
	FString GridError;
	bHasRealTerrain = !Package.bSynthetic && FLsnTerrainGrid::LoadForSite(Package.SiteId, TerrainGrid, GridError) && TerrainGrid.Matches(Package, GridError);
	if (!bHasRealTerrain)
	{
		TerrainGrid = FLsnTerrainGrid();
		UE_LOG(LogLsn, Display, TEXT("No real terrain for %s: %s. The placeholder surface is drawn."), *Package.SiteId, *GridError);
	}
	TimePosition = 0.0;

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

	RegolithMaterial = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
	EarthMaterial = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
	EarthMaterial->SetScalarParameterValue(TEXT("RegolithShading"), 0.0f);
	ObjectMaterial = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
	ObjectMaterial->SetScalarParameterValue(TEXT("RegolithShading"), 0.0f);

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
	SetTimePosition(TimePosition);
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
	// The highlights belong to an observer height and a package: build them anew when needed.
	ShownSunObstacleId = -1;
	ShownEarthObstacleId = -1;

	const double EyeHeightM = Package.ObserverHeightsM[HeightIndex];

	// Terrain: its outer edge is the package horizon.
	FLsnHorizonTerrainParams TerrainParams;
	TerrainParams.Albedo = RegolithAlbedo;
	UnknownTerrainSamples = 0;
	if (bHasRealTerrain)
	{
		// -LsnRawNormals shows the unsmoothed normals, for comparison.
		const double Smoothing = FParse::Param(FCommandLine::Get(), TEXT("LsnRawNormals")) ? 0.0 : LsnMesh::DefaultNormalSmoothingM;
		LsnMesh::BuildGridTerrain(Frame, Package, HeightIndex, TerrainGrid, RegolithAlbedo, Smoothing, TerrainData, SkippedHorizonSamples, UnknownTerrainSamples);
	}
	else
	{
		LsnMesh::BuildHorizonTerrain(Frame, Package, HeightIndex, TerrainParams, TerrainData, SkippedHorizonSamples);
	}
	TerrainData.RoundPositionsToFloat();
	Terrain->SetRelativeLocation(FVector::ZeroVector);
	ApplyMesh(Terrain, TerrainData, RegolithMaterial);
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
	MoonSphere->SetRelativeLocation(Frame.MoonCentreUnreal());
	ApplyMesh(MoonSphere, MoonSphereData, RegolithMaterial);

	// Overlay: the package horizon as a line.
	FLsnMeshData LineData;
	LsnMesh::BuildHorizonLine(Frame, Package, HeightIndex, 0.04, FColor(255, 120, 20, 255), LineData);
	HorizonLine->SetRelativeLocation(FVector::ZeroVector);
	UMaterialInstanceDynamic* LineMaterial = UMaterialInstanceDynamic::Create(EmissiveMaterial, this);
	LineMaterial->SetScalarParameterValue(TEXT("Intensity"), HorizonLineEmissive);
	ApplyMesh(HorizonLine, LineData, LineMaterial);

	RebuildScaleObjects();

	// Discs.
	UMaterialInstanceDynamic* SunMaterial = UMaterialInstanceDynamic::Create(EmissiveMaterial, this);
	SunMaterial->SetScalarParameterValue(TEXT("Intensity"), SunDiscEmissive);
	EnsureUnitSphere(SunDisc, FColor(255, 250, 240, 255), SunMaterial);
	// A plain sphere in the Earth's direction and angular size, lit by the scene's Sun, so
	// that its phase follows from the two package directions. It carries no map: the
	// package does not say which side of the Earth faces the Moon.
	EnsureUnitSphere(EarthDisc, FColor(86, 118, 178, 255), EarthMaterial);
}

bool ALsnSiteScene::GroundPointUnreal(double AzimuthDeg, double DistanceM, FVector& OutPoint) const
{
	const int32 NumRings = TerrainGrid.RingDistanceM.Num();
	if (!bHasRealTerrain || NumRings < 2 || TerrainGrid.AzimuthCount <= 0 || DistanceM > TerrainGrid.RingDistanceM.Last())
	{
		return false;
	}
	// The nearest azimuth sample of the elevation samples; linear between its two rings.
	const int32 Nearest = FMath::RoundToInt32((AzimuthDeg - TerrainGrid.AzimuthStartDeg) / TerrainGrid.AzimuthStepDeg);
	const int32 A = ((Nearest % TerrainGrid.AzimuthCount) + TerrainGrid.AzimuthCount) % TerrainGrid.AzimuthCount;
	int32 R = 0;
	while (R + 2 < NumRings && TerrainGrid.RingDistanceM[R + 1] < DistanceM)
	{
		++R;
	}
	const double D0 = TerrainGrid.RingDistanceM[R], D1 = TerrainGrid.RingDistanceM[R + 1];
	const double F = FMath::Clamp((DistanceM - D0) / (D1 - D0), 0.0, 1.0);
	const float H0 = TerrainGrid.HeightsM[A * NumRings + R], H1 = TerrainGrid.HeightsM[A * NumRings + R + 1];
	if (FMath::IsNaN(H0) || FMath::IsNaN(H1))
	{
		return false;
	}
	OutPoint = Frame.SurfacePointUnreal(AzimuthDeg, DistanceM, (1.0 - F) * H0 + F * H1);
	return true;
}

void ALsnSiteScene::RebuildScaleObjects()
{
	bHasScaleObjects = false;
	ScaleObjects->ClearAllMeshSections();
	Mast->ClearAllMeshSections();
	if (bHasRealTerrain)
	{
		// Where the objects stand: azimuth and distance from the site, turn about the vertical,
		// size factor. Chosen for the look; the lander is far enough to stay small in the view.
		struct FPlaced { const TCHAR* Model; double AzimuthDeg; double DistanceM; double YawDeg; double Scale; };
		static const FPlaced Placed[] = {
			{ TEXT("lander"), 150.0, 38.0, 20.0, 1.0 },
			{ TEXT("boulder_1"), 118.0, 9.0, 0.0, 1.0 }, { TEXT("boulder_2"), 131.0, 6.0, 70.0, 1.0 }, { TEXT("boulder_3"), 100.0, 16.0, 140.0, 1.0 },
			{ TEXT("boulder_2"), 145.0, 12.0, 200.0, 1.3 }, { TEXT("boulder_1"), 300.0, 11.0, 250.0, 1.0 }, { TEXT("boulder_3"), 215.0, 22.0, 30.0, 1.0 },
			{ TEXT("boulder_2"), 20.0, 7.0, 110.0, 1.0 }, { TEXT("boulder_1"), 70.0, 14.0, 300.0, 0.8 },
		};
		FLsnMeshData All;
		TMap<FString, FLsnMeshData> Models;
		FString Error;
		for (const FPlaced& Item : Placed)
		{
			FLsnMeshData* Model = Models.Find(Item.Model);
			if (!Model)
			{
				FLsnMeshData Loaded;
				if (!LsnProps::LoadObj(FPaths::Combine(LsnProps::ModelDirectory(), FString(Item.Model) + TEXT(".obj")), Loaded, Error))
				{
					UE_LOG(LogLsn, Warning, TEXT("Scale object not drawn: %s"), *Error);
					continue;
				}
				Model = &Models.Add(Item.Model, MoveTemp(Loaded));
			}
			FVector Ground;
			if (GroundPointUnreal(Item.AzimuthDeg, Item.DistanceM, Ground))
			{
				LsnProps::Append(*Model, FVector(Item.Scale), Item.YawDeg, Ground, All);
			}
		}
		if (All.Triangles.Num() > 0)
		{
			ScaleObjects->SetRelativeLocation(FVector::ZeroVector);
			ApplyMesh(ScaleObjects, All, ObjectMaterial);
			bHasScaleObjects = true;
		}
		FLsnMeshData MastMesh;
		if (LsnProps::BuildMast(Package.ObserverHeightsM[HeightIndex], MastMesh, Error))
		{
			Mast->SetRelativeLocation(FVector::ZeroVector);
			ApplyMesh(Mast, MastMesh, ObjectMaterial);
		}
	}
	ScaleObjects->SetVisibility(bHasScaleObjects && bScaleObjectsVisible);
	Mast->SetVisibility(bHasScaleObjects && bScaleObjectsVisible && bMastVisible);
}

void ALsnSiteScene::SetScaleObjectsVisible(bool bVisible)
{
	bScaleObjectsVisible = bVisible;
	ScaleObjects->SetVisibility(bHasScaleObjects && bScaleObjectsVisible);
	Mast->SetVisibility(bHasScaleObjects && bScaleObjectsVisible && bMastVisible);
}

void ALsnSiteScene::SetMastVisible(bool bVisible)
{
	bMastVisible = bVisible;
	Mast->SetVisibility(bHasScaleObjects && bScaleObjectsVisible && bMastVisible);
}

void ALsnSiteScene::EnsureUnitSphere(UProceduralMeshComponent* Component, const FColor& Color, UMaterialInterface* Material)
{
	FLsnMeshData Sphere;
	LsnMesh::BuildUnitSphere(32, 64, Color, Sphere);
	ApplyMesh(Component, Sphere, Material);
}

bool ALsnSiteScene::SampleBody(const TCHAR* Body, double SamplePosition, FLsnBodyAtTime& Out) const
{
	Out = FLsnBodyAtTime();
	const FLsnBodySeries* S = (bHasPackage && Package.bHasTimeline) ? Package.FindSeries(Body) : nullptr;
	if (!S || SamplePosition < 0.0 || SamplePosition > Package.Time.Count - 1)
	{
		return false;
	}
	const int32 T0 = FMath::Min(static_cast<int32>(FMath::FloorToDouble(SamplePosition)), Package.Time.Count - 1);
	const double F = SamplePosition - T0;
	if (!S->AzimuthDeg.IsValidIndex(T0) || !S->ElevationDeg.IsValidIndex(T0) || FMath::IsNaN(S->AzimuthDeg[T0]) || FMath::IsNaN(S->ElevationDeg[T0]))
	{
		return false;
	}
	Out.AzimuthDeg = S->AzimuthDeg[T0];
	Out.ElevationDeg = S->ElevationDeg[T0];
	Out.bHasAngularRadius = S->AngularRadiusDeg.IsValidIndex(T0) && !FMath::IsNaN(S->AngularRadiusDeg[T0]);
	Out.AngularRadiusDeg = Out.bHasAngularRadius ? S->AngularRadiusDeg[T0] : 0.0;
	if (F > 0.0)
	{
		// Between two samples: linear interpolation of the package series over one time
		// step, the azimuth along the shorter way round. A whole position never gets here,
		// so it shows the package values unchanged.
		const int32 T1 = T0 + 1;
		if (!S->AzimuthDeg.IsValidIndex(T1) || FMath::IsNaN(S->AzimuthDeg[T1]) || FMath::IsNaN(S->ElevationDeg[T1]))
		{
			return false;
		}
		const double DeltaAz = FMath::Fmod(static_cast<double>(S->AzimuthDeg[T1]) - Out.AzimuthDeg + 540.0, 360.0) - 180.0;
		Out.AzimuthDeg = FMath::Fmod(Out.AzimuthDeg + F * DeltaAz + 360.0, 360.0);
		Out.ElevationDeg = (1.0 - F) * Out.ElevationDeg + F * S->ElevationDeg[T1];
		Out.bHasAngularRadius = Out.bHasAngularRadius && S->AngularRadiusDeg.IsValidIndex(T1) && !FMath::IsNaN(S->AngularRadiusDeg[T1]);
		Out.AngularRadiusDeg = Out.bHasAngularRadius ? (1.0 - F) * Out.AngularRadiusDeg + F * S->AngularRadiusDeg[T1] : 0.0;
	}
	Out.bValid = true;
	return true;
}

void ALsnSiteScene::PlaceDisc(UProceduralMeshComponent* Disc, const FLsnBodyAtTime& Body, double ProxyDistanceM)
{
	// A disc needs a direction and an angular radius; both are optional parts
	// of a package. Without them the disc is hidden rather than guessed.
	if (!Body.bValid || !Body.bHasAngularRadius)
	{
		Disc->SetVisibility(false);
		return;
	}
	const double DistanceCm = ProxyDistanceM * FLsnSiteFrame::CmPerM;
	// A sphere of radius r at distance d subtends an angular radius asin(r / d).
	const double RadiusCm = DistanceCm * FMath::Sin(FMath::DegreesToRadians(Body.AngularRadiusDeg));
	Disc->SetWorldLocation(GetEyeUnreal() + FLsnSiteFrame::AzElToUnrealDir(Body.AzimuthDeg, Body.ElevationDeg) * DistanceCm);
	Disc->SetWorldScale3D(FVector(RadiusCm));
	Disc->SetVisibility(true);
}

bool ALsnSiteScene::SetTimeIndex(int32 NewTimeIndex)
{
	return SetTimePosition(static_cast<double>(NewTimeIndex));
}

bool ALsnSiteScene::SetTimePosition(double NewTimePosition)
{
	if (!bHasPackage || !Package.bHasTimeline)
	{
		// No timeline in the package: no Sun, no Earth, no light direction to show.
		SunLight->SetVisibility(false);
		SunDisc->SetVisibility(false);
		EarthDisc->SetVisibility(false);
		return false;
	}
	if (FMath::IsNaN(NewTimePosition) || NewTimePosition < 0.0 || NewTimePosition > Package.Time.Count - 1)
	{
		return false;
	}
	TimePosition = NewTimePosition;
	TimeIndex = static_cast<int32>(FMath::FloorToDouble(TimePosition));

	FLsnBodyAtTime Sun, Earth;
	SampleBody(TEXT("SUN"), TimePosition, Sun);
	SampleBody(TEXT("EARTH"), TimePosition, Earth);
	if (Sun.bValid)
	{
		const FVector ToSun = FLsnSiteFrame::AzElToUnrealDir(Sun.AzimuthDeg, Sun.ElevationDeg);
		if (RegolithMaterial)
		{
			// The regolith shading needs the direction of the Sun; it is the package's.
			RegolithMaterial->SetVectorParameterValue(TEXT("SunDirection"), FLinearColor(ToSun.X, ToSun.Y, ToSun.Z, 0.0f));
		}
		// A directional light shines along its forward axis: away from the Sun.
		SunLight->SetWorldRotation((-ToSun).Rotation());
		if (Sun.bHasAngularRadius)
		{
			// The engine's source angle is the angular diameter of the light source.
			SunLight->SetLightSourceAngle(static_cast<float>(2.0 * Sun.AngularRadiusDeg));
		}
		SunLight->SetVisibility(true);
	}
	else
	{
		SunLight->SetVisibility(false);
	}
	PlaceDisc(SunDisc, Sun, SunProxyDistanceM);
	PlaceDisc(EarthDisc, Earth, EarthProxyDistanceM);
	UpdateObstacleHighlight(TEXT("SUN"), SunObstacle, ShownSunObstacleId, SunObstacleColor);
	UpdateObstacleHighlight(TEXT("EARTH"), EarthObstacle, ShownEarthObstacleId, EarthObstacleColor);
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
