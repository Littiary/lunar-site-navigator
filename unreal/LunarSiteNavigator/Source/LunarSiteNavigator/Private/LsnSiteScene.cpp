#include "LsnSiteScene.h"

#include "Components/DirectionalLightComponent.h"
#include "Components/PostProcessComponent.h"
#include "LsnTerrain.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"

namespace
{
	// Drawing choices of the scene. None of them is a result and none is shown as a number.
	constexpr double DiscDistanceCm = 5.0e8;  // discs are drawn 5000 km away, beyond all terrain, with their true angular size
	constexpr float SunLightLux = 10.0f;      // paired with the fixed exposure below; not a photometric claim
	constexpr float ExposureBias = 1.0f;
	const FLinearColor SunColor(60.0f, 58.0f, 54.0f);
	const FLinearColor EarthColor(0.5f, 0.9f, 2.0f);

	void SetSection(UProceduralMeshComponent* Component, const FLsnMeshData& Mesh, UMaterialInterface* Material)
	{
		Component->ClearAllMeshSections();
		Component->CreateMeshSection_LinearColor(0, Mesh.Vertices, Mesh.Triangles, Mesh.Normals, Mesh.UV0, TArray<FLinearColor>(), TArray<FProcMeshTangent>(), false);
		if (Material != nullptr)
		{
			Component->SetMaterial(0, Material);
		}
	}

	UMaterialInterface* LoadMaterial(const TCHAR* ProjectPath, const TCHAR* EngineFallback)
	{
		UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr, ProjectPath, nullptr, LOAD_NoWarn | LOAD_Quiet);
		return Material != nullptr ? Material : LoadObject<UMaterialInterface>(nullptr, EngineFallback);
	}
}

ALsnSiteScene::ALsnSiteScene()
{
	PrimaryActorTick.bCanEverTick = false;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));

	auto MakeMesh = [this](const TCHAR* Name, bool bCastShadow)
	{
		UProceduralMeshComponent* Mesh = CreateDefaultSubobject<UProceduralMeshComponent>(Name);
		Mesh->SetupAttachment(RootComponent);
		Mesh->SetCastShadow(bCastShadow);
		Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		return Mesh;
	};
	PatchMesh = MakeMesh(TEXT("PatchMesh"), true);
	SphereMesh = MakeMesh(TEXT("SphereMesh"), true);
	SunDisc = MakeMesh(TEXT("SunDisc"), false);
	EarthDisc = MakeMesh(TEXT("EarthDisc"), false);

	// Airless body: one directional light, no sky light, no atmosphere, no fog.
	SunLight = CreateDefaultSubobject<UDirectionalLightComponent>(TEXT("SunLight"));
	SunLight->SetupAttachment(RootComponent);
	SunLight->SetMobility(EComponentMobility::Movable);
	SunLight->SetIntensity(SunLightLux);
	SunLight->SetCastShadows(true);
	SunLight->bUseTemperature = false;
	SunLight->SetAtmosphereSunLight(false);

	PostProcess = CreateDefaultSubobject<UPostProcessComponent>(TEXT("PostProcess"));
	PostProcess->SetupAttachment(RootComponent);
	PostProcess->bUnbound = true;
	PostProcess->Settings.bOverride_AutoExposureMethod = true;
	PostProcess->Settings.AutoExposureMethod = AEM_Manual;
	PostProcess->Settings.bOverride_AutoExposureBias = true;
	PostProcess->Settings.AutoExposureBias = ExposureBias;
	PostProcess->Settings.bOverride_AutoExposureApplyPhysicalCameraExposure = true;
	PostProcess->Settings.AutoExposureApplyPhysicalCameraExposure = false;
}

bool ALsnSiteScene::LoadPackage(const FString& PackageDir, FString& OutError)
{
	bLoaded = false;
	if (!Package.Load(PackageDir, OutError))
	{
		return false;
	}
	HeightIndex = Package.DefaultHeightIndex;
	TimeIndex = 0;

	SurfaceMaterial = LoadMaterial(TEXT("/Game/Lsn/M_LsnSurface.M_LsnSurface"), TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	UMaterialInterface* Emissive = LoadMaterial(TEXT("/Game/Lsn/M_LsnEmissive.M_LsnEmissive"), TEXT("/Engine/EngineMaterials/EmissiveMeshMaterial.EmissiveMeshMaterial"));
	SunMaterial = UMaterialInstanceDynamic::Create(Emissive, this);
	SunMaterial->SetVectorParameterValue(TEXT("Color"), SunColor);
	EarthMaterial = UMaterialInstanceDynamic::Create(Emissive, this);
	EarthMaterial->SetVectorParameterValue(TEXT("Color"), EarthColor);

	FLsnMeshData Disc;
	LsnTerrain::BuildDisc(96, Disc);
	SetSection(SunDisc, Disc, SunMaterial);
	SetSection(EarthDisc, Disc, EarthMaterial);

	FLsnMeshData Sphere;
	FVector Centre;
	LsnTerrain::BuildReferenceSphere(Package, Sphere, Centre);
	SphereMesh->SetWorldLocation(Centre);
	SetSection(SphereMesh, Sphere, SurfaceMaterial);

	bLoaded = true;
	RebuildTerrain();
	ApplySky();
	return true;
}

void ALsnSiteScene::SetTimeIndex(int32 Index)
{
	if (bLoaded && Package.bHasTimeline)
	{
		TimeIndex = FMath::Clamp(Index, 0, Package.Time.Count - 1);
		ApplySky();
	}
}

void ALsnSiteScene::SetHeightIndex(int32 Index)
{
	if (bLoaded)
	{
		const int32 Clamped = FMath::Clamp(Index, 0, Package.NumHeights() - 1);
		if (Clamped != HeightIndex)
		{
			HeightIndex = Clamped;
			RebuildTerrain();  // the obstacle points belong to an observer height
			ApplySky();
		}
	}
}

bool ALsnSiteScene::GetBody(const TCHAR* Body, FLsnBodySky& Out) const
{
	return bLoaded && Package.GetBodySky(Body, TimeIndex, HeightIndex, Out);
}

void ALsnSiteScene::RebuildTerrain()
{
	FLsnMeshData Patch;
	if (LsnTerrain::BuildHorizonPatch(Package, HeightIndex, Patch))
	{
		SetSection(PatchMesh, Patch, SurfaceMaterial);
	}
	else
	{
		PatchMesh->ClearAllMeshSections();
	}
}

void ALsnSiteScene::PlaceDisc(UProceduralMeshComponent* Disc, const TCHAR* Body) const
{
	FLsnBodySky Sky;
	// Without an angular radius in the package the disc is hidden rather than drawn with a guessed size.
	const bool bVisible = GetBody(Body, Sky) && Sky.bHasAngularRadius;
	Disc->SetVisibility(bVisible);
	if (bVisible)
	{
		const double Radius = DiscDistanceCm * FMath::Tan(FMath::DegreesToRadians(Sky.AngularRadiusDeg));
		Disc->SetWorldLocationAndRotation(Package.ObserverWorldCm(HeightIndex) + Sky.WorldDir * DiscDistanceCm, LsnFrame::AzElToRotator(Sky.AzimuthDeg, Sky.ElevationDeg));
		Disc->SetWorldScale3D(FVector(Radius));
	}
}

void ALsnSiteScene::ApplySky()
{
	FLsnBodySky Sun;
	if (GetBody(TEXT("SUN"), Sun))
	{
		// The light travels opposite to the direction towards the Sun.
		SunLight->SetWorldRotation(LsnFrame::AzElToRotator(Sun.AzimuthDeg + 180.0, -Sun.ElevationDeg));
		if (Sun.bHasAngularRadius)
		{
			SunLight->SetLightSourceAngle(static_cast<float>(2.0 * Sun.AngularRadiusDeg));
		}
	}
	else
	{
		// No timeline in the package: a neutral light from the zenith so the terrain can be seen.
		// The HUD says that this is not the Sun.
		SunLight->SetWorldRotation(FRotator(-90.0, 0.0, 0.0));
	}
	PlaceDisc(SunDisc, TEXT("SUN"));
	PlaceDisc(EarthDisc, TEXT("EARTH"));
}
