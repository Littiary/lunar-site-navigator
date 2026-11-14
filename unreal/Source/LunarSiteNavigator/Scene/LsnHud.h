#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Package/LsnPackage.h"
#include "LsnHud.generated.h"

class ALsnSiteScene;

/** One line of the text read-out. */
struct FLsnHudLine
{
	FString Text;
	FLinearColor Color = FLinearColor::White;
	float Size = 1.0f;
};

/**
 * What the HUD says, kept apart from the drawing so that it can be tested.
 * Every number is a field of the package (or a difference of two of its
 * times), printed with the validation status of its method card.
 */
namespace LsnHudText
{
	/** "2 d 03 h 12 min", "3 h 05 min", "4 min 10 s". */
	LUNARSITENAVIGATOR_API FString FormatDuration(double Seconds);

	/** UTC label of a position on the time axis; empty when the contract does not allow labelling (leap second in range). */
	LUNARSITENAVIGATOR_API FString UtcLabelOfPosition(const FLsnSitePackage& Package, double SamplePosition);

	/**
	 * The countdown sentence of a body, for example "SUN sets in 2 d 03 h" or
	 * "EARTH not visible - rises in at least 5 d 02 h (no rise in the computed range)".
	 * Empty when the package has no window for it.
	 */
	LUNARSITENAVIGATOR_API FString CountdownSentence(const TCHAR* BodyLabel, const FLsnCountdown& Countdown);

	/** The text read-out, top to bottom. The first line is the synthetic marker if and only if the package is synthetic. */
	LUNARSITENAVIGATOR_API void BuildStatusLines(const FLsnSitePackage& Package, int32 HeightIndex, double TimePosition, TArray<FLsnHudLine>& OutLines,
		const FString& GroundNote = FString());

	/** The marker a synthetic package must carry on screen (SPEC 3.3). */
	inline const TCHAR* SyntheticMarker() { return TEXT("SYNTHETIC DATA"); }
}

/** Where the two time strips are on screen, in pixels. Shared by the HUD (drawing) and the pawn (dragging). */
struct LUNARSITENAVIGATOR_API FLsnTimeStripLayout
{
	FBox2D WholeRange;
	FBox2D Zoom;
	/** Half width of the zoom strip in samples. */
	double ZoomHalfWidthSamples = 0.0;

	static FLsnTimeStripLayout Make(float SizeX, float SizeY, const FLsnSitePackage& Package);

	/** Time position under a screen point, or false if the point is on neither strip. */
	bool PositionAt(const FVector2D& Point, const FLsnSitePackage& Package, double CurrentPosition, double& OutPosition) const;
};

/**
 * Text overlay, countdown panel and time strips. A synthetic package is
 * marked as such at all times, as the contract requires.
 */
UCLASS()
class LUNARSITENAVIGATOR_API ALsnHud : public AHUD
{
	GENERATED_BODY()

public:
	virtual void DrawHUD() override;

private:
	void DrawStrip(const FBox2D& Box, const FLsnSitePackage& Package, int32 HeightIndex, double FromPosition, double ToPosition, double CurrentPosition, float Scale);
};
