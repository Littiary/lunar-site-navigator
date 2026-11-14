#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Frame/LsnSiteFrame.h"
#include "Mesh/LsnMesh.h"
#include "Package/LsnPackage.h"
#include "LsnSiteScene.generated.h"

class UDirectionalLightComponent;
class UMaterialInterface;
class UProceduralMeshComponent;

/**
 * The view scene of one site package.
 *
 * Everything that depends on time (the Sun's direction and angular size, the
 * Earth's direction and angular size) is read from the package's timeline
 * series at the selected sample. Nothing here computes an ephemeris, a rise or
 * set time, or a visibility.
 *
 * World layout: the site's ground point is the world origin; +X north,
 * +Y east, +Z up (see FLsnSiteFrame).
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnSiteScene : public AActor
{
	GENERATED_BODY()

public:
	ALsnSiteScene();

	/**
	 * Distances at which the discs are drawn. They are drawing aids, not
	 * physical distances: only the direction and the angular radius of a disc
	 * come from the package, and the disc radius is scaled to match. The Earth
	 * is kept nearer than the Sun so that it would cover it.
	 */
	static constexpr double SunProxyDistanceM = 1.0e9;
	static constexpr double EarthProxyDistanceM = 3.0e8;

	/** Loads a site package directory and builds the scene. On failure the scene is left empty. */
	bool LoadPackageDirectory(const FString& PackageDirectory, FString& OutError);

	/** Shows the package as it is seen from one of its observer heights. */
	bool SetHeightIndex(int32 NewHeightIndex);

	/** Moves the Sun, the Earth and the light to a timeline sample of the package. */
	bool SetTimeIndex(int32 NewTimeIndex);

	void SetHorizonLineVisible(bool bVisible);
	bool IsHorizonLineVisible() const;

	bool HasPackage() const { return bHasPackage; }
	const FLsnSitePackage& GetPackage() const { return Package; }
	const FLsnSiteFrame& GetFrame() const { return Frame; }
	int32 GetHeightIndex() const { return HeightIndex; }
	int32 GetTimeIndex() const { return TimeIndex; }
	int32 GetSkippedHorizonSamples() const { return SkippedHorizonSamples; }

	/** Eye of the observer for the selected height, world centimetres. */
	FVector GetEyeUnreal() const;

	/** Unit direction from the eye towards the Sun as the scene's light has it (opposite of the light's travel direction). */
	FVector GetSunDirectionFromLight() const;

	UDirectionalLightComponent* GetSunLight() const { return SunLight; }
	UProceduralMeshComponent* GetSunDisc() const { return SunDisc; }
	UProceduralMeshComponent* GetEarthDisc() const { return EarthDisc; }
	UProceduralMeshComponent* GetTerrainComponent() const { return Terrain; }
	UProceduralMeshComponent* GetMoonSphereComponent() const { return MoonSphere; }

	/** The meshes as handed to the components, positions rounded to 32-bit floats. */
	const FLsnMeshData& GetTerrainMeshData() const { return TerrainData; }
	const FLsnMeshData& GetMoonSphereMeshData() const { return MoonSphereData; }

private:
	void RebuildGeometry();
	void PlaceDisc(UProceduralMeshComponent* Disc, const FLsnBodySeries* Series, double ProxyDistanceM);
	void ApplyMesh(UProceduralMeshComponent* Component, const FLsnMeshData& Mesh, UMaterialInterface* Material);
	void EnsureUnitSphere(UProceduralMeshComponent* Component, const FColor& Color, UMaterialInterface* Material);

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> Terrain;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> MoonSphere;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> HorizonLine;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> SunDisc;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> EarthDisc;

	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> SunLight;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> SurfaceMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> EmissiveMaterial;

	FLsnSitePackage Package;
	FLsnSiteFrame Frame;
	FLsnMeshData TerrainData;
	FLsnMeshData MoonSphereData;
	bool bHasPackage = false;
	int32 HeightIndex = 0;
	int32 TimeIndex = 0;
	int32 SkippedHorizonSamples = 0;
};
