#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Frame/LsnSiteFrame.h"
#include "Mesh/LsnMesh.h"
#include "Package/LsnPackage.h"
#include "Terrain/LsnTerrainGrid.h"
#include "LsnSiteScene.generated.h"

class UDirectionalLightComponent;
class UMaterialInterface;
class UProceduralMeshComponent;

/** Direction and angular size of a body at a position on the package's time axis. */
struct FLsnBodyAtTime
{
	bool bValid = false;
	double AzimuthDeg = 0.0;
	double ElevationDeg = 0.0;
	bool bHasAngularRadius = false;
	double AngularRadiusDeg = 0.0;
};

/**
 * The view scene of one site package.
 *
 * Everything that depends on time (the Sun's direction and angular size, the
 * Earth's direction and angular size) is read from the package's timeline
 * series at the selected sample. Nothing here computes an ephemeris, a rise or
 * set time, or a visibility.
 *
 * World layout: the site's ground point is the actor's location (the world origin
 * for a single scene); +X north, +Y east, +Z up (see FLsnSiteFrame).
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

	/**
	 * The same for a position between samples (0 .. Count - 1). A whole position shows the
	 * package values unchanged; between two samples the series are interpolated linearly
	 * over that one step, for a smooth display only.
	 */
	bool SetTimePosition(double NewTimePosition);
	double GetTimePosition() const { return TimePosition; }

	/** What the scene shows for "SUN" or "EARTH" at a time position. False if the package has no value there. */
	bool SampleBody(const TCHAR* Body, double SamplePosition, FLsnBodyAtTime& Out) const;

	void SetHorizonLineVisible(bool bVisible);
	void SetFillLightVisible(bool bVisible);

	/**
	 * "Show the obstacle": while a body is hidden or partly hidden at the selected sample,
	 * the run of the obstacle the package names for it is highlighted (SPEC 5.5).
	 */
	void SetObstacleViewEnabled(bool bEnabled);
	bool IsObstacleViewEnabled() const { return bObstacleViewEnabled; }
	/** The highlight of "SUN" or "EARTH". */
	UProceduralMeshComponent* GetObstacleHighlight(const TCHAR* Body) const;
	bool IsFillLightVisible() const;
	bool IsHorizonLineVisible() const;

	bool HasPackage() const { return bHasPackage; }
	const FLsnSitePackage& GetPackage() const { return Package; }
	const FLsnSiteFrame& GetFrame() const { return Frame; }
	int32 GetHeightIndex() const { return HeightIndex; }
	int32 GetTimeIndex() const { return TimeIndex; }
	int32 GetSkippedHorizonSamples() const { return SkippedHorizonSamples; }

	/** True if the ground is drawn from real elevation samples; false for the placeholder surface. */
	bool HasRealTerrain() const { return bHasRealTerrain; }
	const FLsnTerrainGrid& GetTerrainGrid() const { return TerrainGrid; }
	int32 GetUnknownTerrainSamples() const { return UnknownTerrainSamples; }

	/** What the ground between the site and the horizon line is, for the read-out. */
	FString GetGroundNote() const;

	/** Eye of the observer for the selected height, world centimetres. */
	FVector GetEyeUnreal() const;

	/** Unit direction from the eye towards the Sun as the scene's light has it (opposite of the light's travel direction). */
	FVector GetSunDirectionFromLight() const;

	UDirectionalLightComponent* GetSunLight() const { return SunLight; }
	UDirectionalLightComponent* GetFillLight() const { return FillLight; }

	/**
	 * Which of two scenes shown side by side this is (0 or 1). Each slot lights and is
	 * lit on its own lighting channel, so the Sun of one site never lights the other.
	 */
	void SetSceneSlot(int32 Slot);
	int32 GetSceneSlot() const { return SceneSlot; }
	UProceduralMeshComponent* GetSunDisc() const { return SunDisc; }
	UProceduralMeshComponent* GetEarthDisc() const { return EarthDisc; }
	UProceduralMeshComponent* GetTerrainComponent() const { return Terrain; }
	UProceduralMeshComponent* GetMoonSphereComponent() const { return MoonSphere; }

	/** The meshes as handed to the components, positions rounded to 32-bit floats. */
	const FLsnMeshData& GetTerrainMeshData() const { return TerrainData; }
	const FLsnMeshData& GetMoonSphereMeshData() const { return MoonSphereData; }

private:
	void RebuildGeometry();
	void PlaceDisc(UProceduralMeshComponent* Disc, const FLsnBodyAtTime& Body, double ProxyDistanceM);
	void UpdateObstacleHighlight(const TCHAR* Body, UProceduralMeshComponent* Highlight, int32& InOutShownObstacleId, const FColor& Color);
	void ApplyMesh(UProceduralMeshComponent* Component, const FLsnMeshData& Mesh, UMaterialInterface* Material);
	void EnsureUnitSphere(UProceduralMeshComponent* Component, const FColor& Color, UMaterialInterface* Material);

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> Terrain;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> MoonSphere;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> HorizonLine;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> SunObstacle;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> EarthObstacle;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> SunDisc;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> EarthDisc;

	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> SunLight;

	/**
	 * A very weak light from the zenith without shadows, so that terrain the Sun does not
	 * reach is still told apart from the sky. It is a display aid: it stands for no
	 * computed quantity (no earthshine, no reflected light) and comes from no package field.
	 */
	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> FillLight;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> SurfaceMaterial;

	/** The regolith surface of this scene; its "SunDirection" follows the package. */
	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> RegolithMaterial;

	/** The Earth's disc: the same material with the plain cosine law. */
	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> EarthMaterial;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> EmissiveMaterial;

	FLsnSitePackage Package;
	FLsnSiteFrame Frame;
	FLsnMeshData TerrainData;
	FLsnMeshData MoonSphereData;
	bool bHasPackage = false;
	int32 HeightIndex = 0;
	int32 TimeIndex = 0;
	double TimePosition = 0.0;
	int32 SkippedHorizonSamples = 0;
	FLsnTerrainGrid TerrainGrid;
	bool bHasRealTerrain = false;
	int32 SceneSlot = 0;
	bool bObstacleViewEnabled = true;
	/** Obstacle whose band each highlight currently holds; -1 for none. */
	int32 ShownSunObstacleId = -1;
	int32 ShownEarthObstacleId = -1;
	int32 UnknownTerrainSamples = 0;
};
