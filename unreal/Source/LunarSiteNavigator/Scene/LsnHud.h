#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "Package/LsnPackage.h"
#include "Planner/LsnPlanner.h"
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

	/**
	 * What hides a body and what that obstacle costs (SPEC 5.5), as up to three sentences;
	 * none while the body is clear. Every number is a field of the package.
	 */
	LUNARSITENAVIGATOR_API void BlockerSentences(const TCHAR* BodyLabel, const FLsnSitePackage& Package, const FLsnBlocking& Blocking, TArray<FString>& OutLines);

	/** What a landing at the selected time means for the chosen requirement, from the landing windows of the package. */
	LUNARSITENAVIGATOR_API FString LandingSentence(const FLsnLandingCheck& Check);

	/** The range of a countdown for the stated horizon error: the package's earliest and latest time of the event. */
	LUNARSITENAVIGATOR_API FString CountdownBandSentence(const FLsnSitePackage& Package, double EtS, const FLsnEvent& Event);

	/** The text read-out, top to bottom. The first line is the synthetic marker if and only if the package is synthetic. */
	LUNARSITENAVIGATOR_API void BuildStatusLines(const FLsnSitePackage& Package, int32 HeightIndex, double TimePosition, TArray<FLsnHudLine>& OutLines,
		const FString& GroundNote = FString());

	/** The marker a synthetic package must carry on screen (SPEC 3.3). */
	inline const TCHAR* SyntheticMarker() { return TEXT("SYNTHETIC DATA"); }
}

/** A button on screen: a named action of the observer (ALsnObserverPawn::DoAction). */
struct FLsnButton
{
	FName Action;
	FString Label;
	FBox2D Box;
};

/**
 * The buttons along the bottom of the left (or only) view, in pixels of that view. Shared by
 * the HUD (drawing) and the pawn (clicking). Two rows on a wide view, four on a narrow one.
 */
struct LUNARSITENAVIGATOR_API FLsnToolbar
{
	TArray<FLsnButton> Buttons;
	/** Upper edge of the buttons. */
	float Top = 0.0f;

	static FLsnToolbar Make(float SizeX, float SizeY);
	/** The action of the button under a screen point; none outside the buttons. */
	FName ActionAt(const FVector2D& Point) const;
	/** Size of the HUD text for a view of that size (1 at 1280 x 720). */
	static float TextScale(float SizeX, float SizeY);
};

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
	/** Draws text that continues on further lines when wider than MaxWidth; returns the Y below it. */
	float DrawWrapped(const FString& Text, const FLinearColor& Color, float X, float Y, float MaxWidth, float TextScale);
	void DrawCalendar(const FBox2D& Box, const TArray<const ALsnSiteScene*>& Rows, int32 RequirementIndex, float Scale);
	float DrawUncertainty(const ALsnSiteScene& Scene, float X, float Y, float Width, float Scale);
	float DrawTrade(const ALsnSiteScene& Scene, const class ALsnViewGameMode& GameMode, float X, float Y, float Width, float Scale);
	void DrawPanorama(const FLsnPanorama& Panorama, const ALsnSiteScene& Scene, const class ALsnObserverPawn* Pawn, float Scale);
	void DrawToolbar(const FLsnToolbar& Toolbar, const ALsnSiteScene& Scene, const class ALsnObserverPawn* Pawn, const class ALsnViewGameMode* GameMode, float Scale);
	void DrawHelp(float SizeX, float SizeY, float Scale);
	void DrawStrip(const FBox2D& Box, const FLsnSitePackage& Package, int32 HeightIndex, double FromPosition, double ToPosition, double CurrentPosition, float Scale);
};
