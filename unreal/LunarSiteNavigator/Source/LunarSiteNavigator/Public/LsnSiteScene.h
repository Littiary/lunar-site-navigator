#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "LsnPackage.h"
#include "LsnSiteScene.generated.h"

class UDirectionalLightComponent;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UPostProcessComponent;
class UProceduralMeshComponent;

/**
 * The view scene of one site package: stand-in terrain patch, reference sphere, Sun light,
 * Sun and Earth discs. Everything it shows is read from the package; it computes no
 * direction, time or visibility of its own.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnSiteScene : public AActor
{
	GENERATED_BODY()

public:
	ALsnSiteScene();

	bool LoadPackage(const FString& PackageDir, FString& OutError);
	bool IsLoaded() const { return bLoaded; }
	const FLsnSitePackage& GetPackage() const { return Package; }

	void SetTimeIndex(int32 Index);
	void SetHeightIndex(int32 Index);
	int32 GetTimeIndex() const { return TimeIndex; }
	int32 GetHeightIndex() const { return HeightIndex; }

	/** Sun or Earth at the current time and height, as read from the package. False if absent. */
	bool GetBody(const TCHAR* Body, FLsnBodySky& Out) const;

private:
	void RebuildTerrain();
	void ApplySky();
	void PlaceDisc(UProceduralMeshComponent* Disc, const TCHAR* Body) const;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> PatchMesh;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> SphereMesh;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> SunDisc;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> EarthDisc;

	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> SunLight;

	UPROPERTY()
	TObjectPtr<UPostProcessComponent> PostProcess;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> SurfaceMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> SunMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInstanceDynamic> EarthMaterial;

	FLsnSitePackage Package;
	bool bLoaded = false;
	int32 TimeIndex = 0;
	int32 HeightIndex = 0;
};
