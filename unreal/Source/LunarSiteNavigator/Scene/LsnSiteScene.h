#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Frame/LsnSiteFrame.h"
#include "Mesh/LsnMesh.h"
#include "Package/LsnPackage.h"
#include "Package/LsnTerrainPatches.h"
#include "Sky/LsnSky.h"
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
	/** The ground is drawn from the terrain patches of the package (no terrain cache for the site). */
	bool HasPatchTerrain() const { return bHasPatchTerrain; }
	/** The ground has relief of its own (terrain cache or patches of the package), so that it can be shown from the side and from above. */
	bool HasDrawnRelief() const { return bHasRealTerrain || bHasPatchTerrain; }
	const FLsnTerrainGrid& GetTerrainGrid() const { return TerrainGrid; }
	int32 GetUnknownTerrainSamples() const { return UnknownTerrainSamples; }

	/**
	 * Scale objects: a generic lander and boulders near the site, and the mast that carries
	 * the observer. They are drawn for a sense of size only; they are in no package and are
	 * not part of the terrain mesh. Shown only on real elevation data.
	 */
	void SetScaleObjectsVisible(bool bVisible);
	bool AreScaleObjectsVisible() const { return bScaleObjectsVisible; }
	/** No boulder is drawn nearer to the camera than this: an unlit boulder close to the lens is a black blob. */
	static constexpr double BoulderClearanceM = 15.0;
	/** Tells the scene where the camera stands; boulders nearer than the clearance are left out. */
	void KeepBouldersClearOf(const FVector& CameraUnreal);
	/** Where the boulders that are drawn stand (their points on the ground), in Unreal axes. */
	const TArray<FVector>& GetDrawnBoulders() const { return DrawnBoulders; }
	/** The mast stands where the observer is: it is shown only to a camera that is not the observer. */
	void SetMastVisible(bool bVisible);
	/** A point of the drawn ground at an azimuth and distance from the site, relative to the actor; false without elevation data there. */
	bool GroundPointUnreal(double AzimuthDeg, double DistanceM, FVector& OutPoint) const;

	/**
	 * Share of the drawn ground within the start distance of the package's horizon search
	 * that lies in its own shadow at the selected sample (see LsnMesh::NearGroundFacingAwayShare);
	 * 0 without elevation samples or while the package gives the Sun as hidden.
	 */
	double GetNearGroundShadeShare() const { return NearGroundShadeShare; }
	/** Where the lander stands on the ground, world centimetres; false if there is none (no elevation samples). */
	bool GetLanderUnreal(FVector& OutLocation) const { OutLocation = GetActorLocation() + LanderRelative; return bHasLander; }
	/** Applies the display choices (lsn.Look.*) again; called every frame so that they can be tried while the scene runs. */
	void RefreshLook() { UpdateLook(); }

	/** The fill light on whatever the Sun does: for overview stills, labelled as a viewing aid. */
	bool IsFillForced() const { return bForceFill; }

	/** True if the Earth is drawn with its map, turned as the direction table says. */
	bool HasEarthMap() const { return bHasEarthMap; }

	/** True if the star field is drawn: the star list and the sky orientation exported for this package are there. */
	bool HasStars() const { return bHasSky; }
	UProceduralMeshComponent* GetStarsComponent() const { return Stars; }
	/** Share of the Sun's disc the package gives as visible at the selected sample and height; 0 without a value. */
	double GetSunVisibleFraction() const;
	/** The share of the Earth's disc visible at the selected sample, as the package gives it. */
	double GetEarthVisibleFraction() const;
	/** True while the earthshine light is on. */
	bool IsEarthshineOn() const;

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
	TObjectPtr<UProceduralMeshComponent> ScaleObjects;

	/** The star field: decoration, drawn where the catalogue and the Moon's orientation put it. */
	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> Stars;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> StarBaseMaterial;

	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> StarMaterial;

	UPROPERTY()
	TObjectPtr<UProceduralMeshComponent> Mast;

	/** The boulders: shaded like the ground, without its fine detail. */
	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> RockMaterial;

	/** The plain cosine law for the scale objects. */
	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> ObjectMaterial;

	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> SunLight;

	/**
	 * A very weak light from the zenith without shadows, so that the terrain stays readable
	 * while the Sun is down. It is a display aid: it stands for no computed quantity (no
	 * earthshine, no reflected light) and comes from no package field. It is on only while
	 * the package gives the Sun as wholly hidden at the selected sample, and only if the
	 * user has not switched it off: with the Sun up, shadows are black.
	 */
	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> FillLight;
	/** Light from the Earth while the package gives the Sun as hidden and the Earth as visible. */
	UPROPERTY()
	TObjectPtr<UDirectionalLightComponent> EarthLight;

	UPROPERTY()
	TObjectPtr<UMaterialInterface> SurfaceMaterial;

	/** The regolith surface of this scene; its "SunDirection" follows the package. */
	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> RegolithMaterial;

	/**
	 * The Earth with its map (since contract 0.8): NASA Blue Marble, turned by the earth_view
	 * of the direction table. Used only when the table of the package carries earth_view;
	 * otherwise the plain sphere below is drawn.
	 */
	UPROPERTY()
	TObjectPtr<UMaterialInterface> EarthMapBaseMaterial;

	UPROPERTY()
	TObjectPtr<class UMaterialInstanceDynamic> EarthMapMaterial;

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
	bool bHasPatchTerrain = false;
	/** Ground points of all boulders of the list, those that are drawn, and the camera they keep clear of. */
	TArray<FVector> BoulderGround, DrawnBoulders;
	FVector BoulderCamera = FVector::ZeroVector;
	bool bHasBoulderCamera = false;
	/** How far the patches stand above the package horizon for the observer height in use, beyond the start of the horizon search; degrees. */
	double PatchExcessDeg = 0.0;
	TArray<FLsnTerrainPatch> TerrainPatches;
	int32 SceneSlot = 0;
	bool bObstacleViewEnabled = true;
	bool bFillLightWanted = true;
	bool bForceFill = false;
	double NearGroundShadeShare = 0.0;
	bool bHasLander = false;
	FVector LanderRelative = FVector::ZeroVector;
	bool bHasSky = false;
	/** The direction table of the package, kept for the orientation of the Earth. */
	FLsnDirectionTable DirectionTable;
	bool bHasEarthMap = false;
	FLsnSkyOrientation Sky;
	void UpdateLook();
	bool bScaleObjectsVisible = true;
	bool bMastVisible = false;
	bool bHasScaleObjects = false;
	void RebuildScaleObjects();
	/** Obstacle whose band each highlight currently holds; -1 for none. */
	int32 ShownSunObstacleId = -1;
	int32 ShownEarthObstacleId = -1;
	int32 UnknownTerrainSamples = 0;
};
