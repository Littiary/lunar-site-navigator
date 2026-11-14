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

/** How a button is drawn: one of the three main actions, a button of the grouped bar, or a control of the right view. */
enum class ELsnButtonStyle : uint8
{
	Main,
	Bar,
	RightView,
};

/** A button on screen: a named action of the observer (ALsnObserverPawn::DoAction). */
struct FLsnButton
{
	FName Action;
	FString Label;
	FBox2D Box;
	ELsnButtonStyle Style = ELsnButtonStyle::Bar;
	/** The labelled group of the bar the button belongs to. */
	FString Group;
};

/** The label of a group of the bar, where it is drawn. */
struct FLsnButtonGroupLabel
{
	FString Text;
	FVector2D Position = FVector2D::ZeroVector;
};

/**
 * The buttons of the planner, in pixels of the whole window. Shared by the HUDs (drawing:
 * each view draws the buttons that lie in it) and the pawn (clicking).
 *
 * Three main actions under the header on the left; a bar of two rows along the bottom, in
 * labelled groups (time, observer, site, plan, view, info); side by side, the right view's
 * own control in its header.
 */
struct LUNARSITENAVIGATOR_API FLsnToolbar
{
	TArray<FLsnButton> Buttons;
	TArray<FLsnButtonGroupLabel> GroupLabels;
	/** Upper edge of the bar, with its group labels. */
	float Top = 0.0f;
	/** Lower edge of the header (site name, time, state chips). */
	float HeaderBottom = 0.0f;

	static FLsnToolbar Make(float WindowSizeX, float SizeY, bool bComparing);
	/** Upper edge of the bar for a window height; the time strips are laid out above it. */
	static float BarTop(float SizeY);
	/** The action of the button under a point of the window; none outside the buttons. */
	FName ActionAt(const FVector2D& Point) const;
	/** Size of the HUD text for a view of that size (1 at 1280 x 720). */
	static float TextScale(float SizeX, float SizeY);
};

/** What a point of the site picker means. */
enum class ELsnPickerHit : uint8
{
	None,
	Show,       // show the site (left or only view) and close the picker
	PinLeft,    // keep the picker open and show the site on the left
	PinRight,   // show the site on the right, side by side
	LatField,
	LonField,
	Compute,
};

/** A row of the site picker: the header of a group (SiteIndex -1) or a site with its three boxes. */
struct FLsnPickerRow
{
	int32 SiteIndex = -1;
	FString Group;
	FBox2D Row, Show, PinLeft, PinRight;
};

/**
 * The site picker, in pixels of the whole window: the sites in the groups of the list (in
 * the order in which the groups first appear), two columns in one view and two per half
 * side by side, and below them the entry for custom coordinates. Shared by the HUDs
 * (drawing) and the pawn (clicking).
 */
struct LUNARSITENAVIGATOR_API FLsnSitePicker
{
	FBox2D Sheet;
	TArray<FLsnPickerRow> Rows;
	FBox2D LatField, LonField, Compute;
	/** Where the title, the label of the entry and its message are drawn. */
	FVector2D TitlePosition = FVector2D::ZeroVector, EntryLabelPosition = FVector2D::ZeroVector, MessagePosition = FVector2D::ZeroVector;

	static FLsnSitePicker Make(float WindowSizeX, float SizeY, bool bComparing, const TArray<FString>& GroupOfSite);
	ELsnPickerHit HitAt(const FVector2D& Point, int32& OutSiteIndex) const;
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
	void DrawToolbar(const FLsnToolbar& Toolbar, float ViewX0, const ALsnSiteScene& Scene, const class ALsnObserverPawn* Pawn, const class ALsnViewGameMode* GameMode, float Scale);
	/** Draws text made smaller where it is wider than MaxWidth; returns the width drawn. */
	float DrawFit(const FString& Text, const FLinearColor& Color, float X, float Y, float MaxWidth, float TextScale);
	void DrawHelp(float SizeX, float SizeY, float Scale);
	void DrawSitePicker(float WindowSizeX, float ViewX0, const class ALsnViewGameMode& GameMode, float Scale);
	void DrawStrip(const FBox2D& Box, const FLsnSitePackage& Package, int32 HeightIndex, double FromPosition, double ToPosition, double CurrentPosition, float Scale);
};
