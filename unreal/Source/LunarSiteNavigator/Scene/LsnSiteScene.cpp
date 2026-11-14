#include "Scene/LsnSiteScene.h"

#include "LunarSiteNavigator.h"
#include "Components/DirectionalLightComponent.h"
#include "Materials/Material.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Mesh/LsnProps.h"
#include "Sky/LsnEarthView.h"
#include "Scene/LsnLook.h"
#include "Misc/Paths.h"
#include "ProceduralMeshComponent.h"

namespace
{
	/** Display values of stage 1. They are not photometry. */
	constexpr float SunLightLux = 10.0f;
	constexpr float FillLightLux = 0.12f;
	constexpr float SunDiscEmissive = 120.0f;
	/** The stars: emissive of the brightest star in a dark scene, and the share left while the Sun is wholly visible. */
	constexpr float StarEmissive = 6.0f;
	constexpr float StarShareInSunlight = 0.10f;
	/** Radius of the star sphere: beyond the discs of the Sun and the Earth. */
	constexpr double StarSphereRadiusCm = 2.5e11;
	/** Emissive share of the scale objects' grey value while the Sun is wholly visible: sunlight reflected from the ground. */
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
	Stars = MakeMeshComponent(this, TEXT("Stars"), false);
	Stars->SetupAttachment(Root);
	Stars->SetVisibility(false);
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
	bFillLightWanted = bVisible;
	UpdateLook();
}

bool ALsnSiteScene::IsFillLightVisible() const
{
	return bFillLightWanted;
}

double ALsnSiteScene::GetSunVisibleFraction() const
{
	const FLsnBodySeries* Sun = (bHasPackage && Package.bHasTimeline) ? Package.FindSeries(TEXT("SUN")) : nullptr;
	const int32 Flat = HeightIndex * Package.Time.Count + TimeIndex;
	if (!Sun || !Sun->VisibleFraction.IsValidIndex(Flat) || FMath::IsNaN(Sun->VisibleFraction[Flat]))
	{
		return 0.0;
	}
	return FMath::Clamp(static_cast<double>(Sun->VisibleFraction[Flat]), 0.0, 1.0);
}

void ALsnSiteScene::UpdateLook()
{
	// How the scene is drawn follows one package value: the share of the Sun's disc that is
	// visible at the selected sample. Nothing here changes a number or a position.
	const double SunShare = GetSunVisibleFraction();
	// The exposure is fixed for ground under a low Sun. Under a high Sun the same ground is several
	// times brighter, so the display intensity is taken down as a camera would stop down: between
	// 5 and 45 degrees of the package's Sun elevation. A display choice; no number comes from it.
	float HighSun = 1.0f;
	FLsnBodyAtTime SunForExposure;
	if (SampleBody(TEXT("SUN"), TimePosition, SunForExposure))
	{
		HighSun = FMath::Lerp(1.0f, LsnLook::HighSunExposure.GetValueOnGameThread(), FMath::SmoothStep(5.0f, 45.0f, static_cast<float>(SunForExposure.ElevationDeg)));
	}
	SunLight->SetIntensity(LsnLook::SunLux.GetValueOnGameThread() * HighSun);
	FillLight->SetIntensity(LsnLook::FillLux.GetValueOnGameThread());
	if (RegolithMaterial)
	{
		RegolithMaterial->SetScalarParameterValue(TEXT("CraterStrength"), LsnLook::CraterStrength.GetValueOnGameThread());
		RegolithMaterial->SetScalarParameterValue(TEXT("NoiseStrength"), LsnLook::NoiseStrength.GetValueOnGameThread());
	}
	// The fill only while the Sun is wholly hidden: with the Sun up, shadows stay black.
	bForceFill = FParse::Param(FCommandLine::Get(), TEXT("LsnViewingAidFill"));
	// Without a timeline there is no Sun to light the terrain: the fill keeps it readable.
	FillLight->SetVisibility(bHasPackage && (bForceFill || (bFillLightWanted && SunShare <= 0.0)));
	// Ground close to the site that the drawing puts in its own shadow while the package gives the Sun as visible.
	NearGroundShadeShare = 0.0;
	FLsnBodyAtTime SunNow;
	// Only while the whole disc is up and clear of the horizon: at sunset the dark ground needs no explanation.
	if (bHasRealTerrain && SunShare > 0.0 && SampleBody(TEXT("SUN"), TimePosition, SunNow))
	{
		NearGroundShadeShare = LsnMesh::NearGroundFacingAwayShare(TerrainGrid, Package.SurfaceHeightM, SunNow.AzimuthDeg, SunNow.ElevationDeg, FMath::Max(Package.HorizonSearchStartM(), 5.0));
	}
	// The shaded sides of the scale objects: with the Sun up, light reflected from the sunlit
	// ground reaches them; with the fill on, a little of it. Stand-ins chosen by eye.
	const float Ambient = LsnLook::ObjectAmbient.GetValueOnGameThread() * static_cast<float>(SunShare) + (FillLight->IsVisible() ? 0.035f : 0.0f);
	if (ObjectMaterial)
	{
		ObjectMaterial->SetScalarParameterValue(TEXT("Ambient"), Ambient);
	}
	if (RockMaterial)
	{
		RockMaterial->SetScalarParameterValue(TEXT("Ambient"), 1.5f * Ambient);
	}
	if (StarMaterial)
	{
		// Dimmed while sunlit ground is in view: the eye and a camera set for sunlit ground see few stars.
		StarMaterial->SetScalarParameterValue(TEXT("Intensity"), StarEmissive * FMath::Lerp(1.0f, StarShareInSunlight, static_cast<float>(SunShare)));
	}
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
	if (bHasRealTerrain && !FParse::Param(FCommandLine::Get(), TEXT("LsnNoDetail")))
	{
		Note += TEXT(" Roughness and small craters finer than the elevation data are illustrative shading, not data.");
	}
	if (bHasSky)
	{
		Note += TEXT(" Stars: Yale Bright Star Catalogue, turned for the date; decoration.");
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
	RockMaterial = UMaterialInstanceDynamic::Create(SurfaceMaterial, this);
	// Detail finer than the data on real elevation data only; the placeholder surface is no data at all.
	RegolithMaterial->SetScalarParameterValue(TEXT("DetailStrength"), (bHasRealTerrain && !FParse::Param(FCommandLine::Get(), TEXT("LsnNoDetail"))) ? 1.0f : 0.0f);

	// The star field, if the star list and the orientation exported for this very package are there.
	FString SkyError;
	static FLsnStarCatalogue Catalogue;
	static bool bCatalogueTried = false, bCatalogueLoaded = false;
	if (!bCatalogueTried)
	{
		bCatalogueTried = true;
		bCatalogueLoaded = FLsnStarCatalogue::Load(Catalogue, SkyError);
	}
	bHasSky = bCatalogueLoaded && !Package.bSynthetic && Package.bHasTimeline && !FParse::Param(FCommandLine::Get(), TEXT("LsnNoStars"))
		&& FLsnSkyOrientation::LoadForSite(Package.SiteId, Sky, SkyError) && Sky.Matches(Package, SkyError);
	if (bHasSky)
	{
		if (!StarBaseMaterial)
		{
			StarBaseMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Lsn/M_LsnStar.M_LsnStar"));
		}
		bHasSky = StarBaseMaterial != nullptr;
	}
	if (bHasSky)
	{
		FLsnMeshData StarMesh;
		LsnSky::BuildStarMesh(Catalogue, StarSphereRadiusCm, StarMesh);
		StarMaterial = UMaterialInstanceDynamic::Create(StarBaseMaterial, this);
		ApplyMesh(Stars, StarMesh, StarMaterial);
	}
	else
	{
		UE_LOG(LogLsn, Display, TEXT("No star field for %s: %s"), *Package.SiteId, *SkyError);
	}
	Stars->SetVisibility(bHasSky);

	// The Earth's map, if the direction table of this package says how the Earth is turned.
	bHasEarthMap = false;
	FString TableError;
	const FString TableDirectory = FPaths::Combine(PackageDirectory, TEXT("../../../direction_table"), Package.DirectionTableId);
	if (Package.bHasTimeline && !Package.DirectionTableId.IsEmpty() && !FParse::Param(FCommandLine::Get(), TEXT("LsnNoEarthMap"))
		&& (DirectionTable.PackageId == Package.DirectionTableId || LsnPackageIO::LoadDirectionTable(TableDirectory, DirectionTable, TableError)) && DirectionTable.bHasEarthView)
	{
		if (!EarthMapBaseMaterial)
		{
			EarthMapBaseMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Game/Lsn/M_LsnEarth.M_LsnEarth"));
		}
		if (EarthMapBaseMaterial)
		{
			EarthMapMaterial = UMaterialInstanceDynamic::Create(EarthMapBaseMaterial, this);
			bHasEarthMap = true;
		}
	}
	if (!bHasEarthMap)
	{
		UE_LOG(LogLsn, Display, TEXT("The Earth is drawn without its map for %s: %s"), *Package.SiteId, TableError.IsEmpty() ? TEXT("the direction table carries no earth_view") : *TableError);
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
	SetTimePosition(TimePosition);
	return true;
}

void ALsnSiteScene::ApplyMesh(UProceduralMeshComponent* Component, const FLsnMeshData& Mesh, UMaterialInterface* Material)
{
	Component->ClearAllMeshSections();
	// The engine stores a vertex normal in 8 bits per axis. Under a Sun a few degrees above the
	// ground that shows as steps of brightness along the contours, so the normal travels a second
	// time in two texture coordinates (16 bits each): x and y, then the sign of z and a mark that
	// says the pair is filled. The surface material reads it from there.
	TArray<FVector2D> NormalXY, NormalSign;
	NormalXY.Reserve(Mesh.Normals.Num());
	NormalSign.Reserve(Mesh.Normals.Num());
	for (const FVector& Normal : Mesh.Normals)
	{
		NormalXY.Add(FVector2D(Normal.X, Normal.Y));
		NormalSign.Add(FVector2D(Normal.Z < 0.0 ? -1.0 : 1.0, 1.0));
	}
	Component->CreateMeshSection(0, Mesh.Positions, Mesh.Triangles, Mesh.Normals, Mesh.UV0, NormalXY, NormalSign, TArray<FVector2D>(), Mesh.Colors, TArray<FProcMeshTangent>(), false);
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
	// Without the elevation data of the site the ground is a sheet that reaches up to the package
	// horizon: it stands for no relief and must not throw shadows of its own folds.
	Terrain->SetCastShadow(bHasRealTerrain);
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
	EnsureUnitSphere(EarthDisc, bHasEarthMap ? FColor::White : FColor(86, 118, 178, 255), bHasEarthMap ? EarthMapMaterial.Get() : EarthMaterial.Get());
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
	bHasLander = false;
	ScaleObjects->ClearAllMeshSections();
	Mast->ClearAllMeshSections();
	if (bHasRealTerrain)
	{
		// Where the objects stand: azimuth and distance from the site, turn about the vertical,
		// size factor. Chosen for the look; the lander is far enough to stay small in the view.
		struct FPlaced { const TCHAR* Model; double AzimuthDeg; double DistanceM; double YawDeg; double Scale; };
		static const FPlaced Placed[] = {
			{ TEXT("lander"), 150.0, 38.0, 20.0, 1.0 },
			{ TEXT("boulder_1"), 118.0, 15.0, 0.0, 1.0 }, { TEXT("boulder_2"), 133.0, 10.0, 70.0, 1.0 }, { TEXT("boulder_3"), 100.0, 27.0, 140.0, 1.0 },
			{ TEXT("boulder_2"), 147.0, 19.0, 200.0, 1.3 }, { TEXT("boulder_1"), 300.0, 16.0, 250.0, 1.0 }, { TEXT("boulder_3"), 215.0, 31.0, 30.0, 1.0 },
			{ TEXT("boulder_2"), 20.0, 13.0, 110.0, 1.0 }, { TEXT("boulder_1"), 70.0, 21.0, 300.0, 0.8 },
		};
		FLsnMeshData All, Rocks;
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
				if (FCString::Strcmp(Item.Model, TEXT("lander")) == 0)
				{
					bHasLander = true;
					LanderRelative = Ground;
				}
				// Boulders are of the ground's own material and are shaded like it; the lander is not.
				LsnProps::Append(*Model, FVector(Item.Scale), Item.YawDeg, Ground, FString(Item.Model).StartsWith(TEXT("boulder")) ? Rocks : All);
			}
		}
		if (All.Triangles.Num() > 0)
		{
			ScaleObjects->SetRelativeLocation(FVector::ZeroVector);
			ApplyMesh(ScaleObjects, All, ObjectMaterial);
			if (Rocks.Triangles.Num() > 0)
			{
				ScaleObjects->CreateMeshSection(1, Rocks.Positions, Rocks.Triangles, Rocks.Normals, Rocks.UV0, Rocks.Colors, TArray<FProcMeshTangent>(), false);
				ScaleObjects->SetMaterial(1, RockMaterial);
			}
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
		// Nothing of a package shown before may stay: no highlight, no stars.
		SunObstacle->SetVisibility(false);
		EarthObstacle->SetVisibility(false);
		Stars->SetVisibility(false);
		UpdateLook();
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
			if (RockMaterial) { RockMaterial->SetVectorParameterValue(TEXT("SunDirection"), FLinearColor(ToSun.X, ToSun.Y, ToSun.Z, 0.0f)); }
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
	FLsnEarthAxes EarthAxes;
	if (bHasEarthMap && EarthMapMaterial && LsnEarth::AxesAt(DirectionTable, Package.EtOfPosition(TimePosition), EarthAxes))
	{
		// The Earth's axes in the axes of the scene; the material finds latitude and longitude from them.
		const FVector Pole = Frame.BodyDirToUnreal(EarthAxes.Pole), X = Frame.BodyDirToUnreal(EarthAxes.X), Y = Frame.BodyDirToUnreal(EarthAxes.Y);
		EarthMapMaterial->SetVectorParameterValue(TEXT("EarthPole"), FLinearColor(Pole.X, Pole.Y, Pole.Z, 0.0f));
		EarthMapMaterial->SetVectorParameterValue(TEXT("EarthX"), FLinearColor(X.X, X.Y, X.Z, 0.0f));
		EarthMapMaterial->SetVectorParameterValue(TEXT("EarthY"), FLinearColor(Y.X, Y.Y, Y.Z, 0.0f));
	}
	if (bHasSky)
	{
		// The sky turns with the Moon: the orientation exported for this package, at this instant.
		FQuat Turn;
		const bool bInRange = Sky.MeshRotationAt(Package.EtOfPosition(TimePosition), Turn);
		Stars->SetVisibility(bInRange);
		if (bInRange)
		{
			Stars->SetWorldLocationAndRotation(GetEyeUnreal(), Turn);
		}
	}
	UpdateLook();
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
