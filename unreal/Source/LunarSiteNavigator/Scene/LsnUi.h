#pragma once

#include "CoreMinimal.h"

class UWorld;
class UGameViewportClient;
class SWidget;

/** One thing the interface draws: a panel or box, a run of text, or a line. In pixels of the whole window. */
struct FLsnUiItem
{
	enum class EKind : uint8 { Box, Text, Line };
	EKind Kind = EKind::Box;
	FBox2D Box = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);
	FLinearColor Color = FLinearColor::White;
	FLinearColor Border = FLinearColor::Transparent;
	float Radius = 0.0f;
	float BorderPx = 0.0f;
	/** The picture behind the box is blurred (panels). */
	bool bBlur = false;
	FString Text;
	float SizePx = 18.0f;
	bool bMedium = false;
	FVector2D A = FVector2D::ZeroVector, B = FVector2D::ZeroVector;
	float Thickness = 1.0f;
	/** Drawn only inside this box (window pixels): what belongs to one half of the window stays in it. */
	bool bClip = false;
	FBox2D Clip = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);
};

/**
 * The design system of the interface and the list of what one frame draws.
 *
 * The HUD of each view says what is on screen (boxes, text, lines); a Slate widget over
 * the game view paints the list of the last complete frame with rounded panels, hairline
 * borders, background blur and the type of the design system. The interface draws
 * nothing else and computes nothing: every text comes from the HUD, which reads packages.
 */
class LUNARSITENAVIGATOR_API FLsnUi
{
public:
	/** The four type sizes at a window height of 1080, in pixels: footnote, body, title, display. */
	static constexpr float Footnote = 14.0f;
	static constexpr float Body = 18.0f;
	static constexpr float Title = 24.0f;
	static constexpr float Display = 40.0f;
	/** Spacing grid, safe margin, corner radius of panels: pixels at a window height of 1080. */
	static constexpr float Grid = 8.0f;
	static constexpr float SafeMargin = 48.0f;
	static constexpr float PanelRadius = 8.0f;

	/** State colours: amber = Sun, blue = Earth, green = requirement met, red = not met. */
	static FLinearColor Amber() { return FLinearColor(1.0f, 0.72f, 0.20f); }
	static FLinearColor Blue() { return FLinearColor(0.36f, 0.66f, 1.0f); }
	static FLinearColor Green() { return FLinearColor(0.42f, 0.90f, 0.52f); }
	static FLinearColor Red() { return FLinearColor(1.0f, 0.36f, 0.30f); }
	static FLinearColor Ink() { return FLinearColor(0.93f, 0.94f, 0.96f); }
	static FLinearColor InkDim() { return FLinearColor(0.62f, 0.65f, 0.70f); }
	static FLinearColor PanelFill() { return FLinearColor(0.035f, 0.040f, 0.050f, 0.75f); }
	static FLinearColor Hairline() { return FLinearColor(1.0f, 1.0f, 1.0f, 0.16f); }

	static FLsnUi& Get();

	/** Called by a HUD before it draws: a new frame begins when the frame number changes. */
	void BeginView(uint64 Frame);
	void Add(const FLsnUiItem& Item)
	{
		FLsnUiItem& Added = Building.Add_GetRef(Item);
		if (bClipping)
		{
			Added.bClip = true;
			Added.Clip = ClipBox;
		}
	}
	/** Everything added until EndClip is drawn only inside the box (window pixels). */
	void BeginClip(const FBox2D& Box) { bClipping = true; ClipBox = Box; }
	void EndClip() { bClipping = false; }
	const TArray<FLsnUiItem>& Shown() const { return Complete; }

	/** One of the four sizes for a size asked in pixels at a window height of 1080: the nearest that is not larger, never below the footnote. */
	static float SnapSize(float PxAt1080);
	/** Width and height of a run of text at a size in window pixels. */
	static FVector2D Measure(const FString& Text, float SizePx, bool bMedium = false);

	/** Puts the painting widget over the game view of the world (once); removes it when asked. */
	void EnsureWidget(UWorld* World);
	void RemoveWidget();

private:
	TArray<FLsnUiItem> Building, Complete;
	bool bClipping = false;
	FBox2D ClipBox = FBox2D(FVector2D::ZeroVector, FVector2D::ZeroVector);
	uint64 BuildingFrame = 0;
	TSharedPtr<SWidget> Widget;
	TWeakObjectPtr<UGameViewportClient> Viewport;
};
