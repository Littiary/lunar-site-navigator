#include "Scene/LsnUi.h"

#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Fonts/FontMeasure.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Styling/CoreStyle.h"
#include "Styling/SlateBrush.h"
#include "Styling/SlateTypes.h"
#include "Widgets/Layout/SBackgroundBlur.h"
#include "Widgets/SCanvas.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SOverlay.h"

namespace
{
	/** Slate font sizes are points at 96 dpi; the interface thinks in pixels. */
	FSlateFontInfo FontOf(float SizePx, bool bMedium)
	{
		return FCoreStyle::GetDefaultFontStyle(bMedium ? "Bold" : "Regular", FMath::Max(SizePx * 72.0f / 96.0f, 1.0f));
	}

	/** Paints the list of the last complete frame. */
	class SLsnUiPainter : public SLeafWidget
	{
	public:
		SLATE_BEGIN_ARGS(SLsnUiPainter) {}
		SLATE_END_ARGS()

		void Construct(const FArguments&) { SetVisibility(EVisibility::HitTestInvisible); }

		virtual FVector2D ComputeDesiredSize(float) const override { return FVector2D(16.0f, 16.0f); }

		virtual int32 OnPaint(const FPaintArgs&, const FGeometry& Geometry, const FSlateRect&, FSlateWindowElementList& Out, int32 Layer, const FWidgetStyle&, bool) const override
		{
			const TArray<FLsnUiItem>& Items = FLsnUi::Get().Shown();
			// Pixels of the window to the units of this widget.
			const float ToLocal = 1.0f / FMath::Max(Geometry.Scale, 1e-3f);
			Brushes.Reset(Items.Num());
			for (const FLsnUiItem& Item : Items)
			{
				// What belongs to one half of the window is clipped to it.
				if (Item.bClip)
				{
					const FVector2D Min = Geometry.LocalToAbsolute(Item.Clip.Min * ToLocal), Max = Geometry.LocalToAbsolute(Item.Clip.Max * ToLocal);
					Out.PushClip(FSlateClippingZone(FSlateRect(Min.X, Min.Y, Max.X, Max.Y)));
				}
				PaintItem(Item, Geometry, Out, Layer, ToLocal);
				if (Item.bClip)
				{
					Out.PopClip();
				}
			}
			return Layer + 2;
		}

		void PaintItem(const FLsnUiItem& Item, const FGeometry& Geometry, FSlateWindowElementList& Out, int32 Layer, float ToLocal) const
		{
			{
				if (Item.Kind == FLsnUiItem::EKind::Box)
				{
					const FVector2D Size = (Item.Box.Max - Item.Box.Min) * ToLocal;
					if (Size.X <= 0.0 || Size.Y <= 0.0)
					{
						return;
					}
					FSlateBrush& Brush = Brushes.Emplace_GetRef(FSlateRoundedBoxBrush(FSlateColor(Item.Color), Item.Radius * ToLocal, FSlateColor(Item.Border), Item.BorderPx * ToLocal));
					FSlateDrawElement::MakeBox(Out, Layer, Geometry.ToPaintGeometry(FVector2f(Size), FSlateLayoutTransform(FVector2f(Item.Box.Min * ToLocal))), &Brush, ESlateDrawEffect::None, Item.Color);
				}
				else if (Item.Kind == FLsnUiItem::EKind::Text)
				{
					FSlateDrawElement::MakeText(Out, Layer + 1, Geometry.ToPaintGeometry(FVector2f(4000.0f, 200.0f), FSlateLayoutTransform(FVector2f(Item.Box.Min * ToLocal))), Item.Text, FontOf(Item.SizePx * ToLocal, Item.bMedium),
						ESlateDrawEffect::None, Item.Color);
				}
				else
				{
					TArray<FVector2f> Points = { FVector2f(Item.A * ToLocal), FVector2f(Item.B * ToLocal) };
					FSlateDrawElement::MakeLines(Out, Layer + 1, Geometry.ToPaintGeometry(), Points, ESlateDrawEffect::None, Item.Color, true, FMath::Max(Item.Thickness * ToLocal, 1.0f * ToLocal));
				}
			}
		}

	private:
		/** Kept until the frame is drawn: an element points at its brush. */
		mutable TArray<FSlateBrush> Brushes;
	};

	constexpr int32 BlurPool = 24;

	/** The blurred box of a panel, by its place among the blurred boxes of the frame. */
	bool BlurBox(int32 Index, FBox2D& OutBox, float& OutRadius)
	{
		int32 Seen = 0;
		for (const FLsnUiItem& Item : FLsnUi::Get().Shown())
		{
			if (Item.Kind == FLsnUiItem::EKind::Box && Item.bBlur)
			{
				if (Seen == Index)
				{
					OutBox = Item.Box;
					OutRadius = Item.Radius;
					return true;
				}
				++Seen;
			}
		}
		return false;
	}
}

FLsnUi& FLsnUi::Get()
{
	static FLsnUi Instance;
	return Instance;
}

void FLsnUi::BeginView(uint64 Frame)
{
	if (Frame != BuildingFrame)
	{
		Complete = MoveTemp(Building);
		Building.Reset();
		BuildingFrame = Frame;
	}
}

float FLsnUi::SnapSize(float PxAt1080)
{
	return PxAt1080 >= 0.5f * (Display + Title) ? Display : PxAt1080 >= Title - 1.0f ? Title : PxAt1080 >= Body - 1.0f ? Body : Footnote;
}

FVector2D FLsnUi::Measure(const FString& Text, float SizePx, bool bMedium)
{
	if (!FSlateApplication::IsInitialized() || !FSlateApplication::Get().GetRenderer())
	{
		// Without a renderer (tests): a plain estimate.
		return FVector2D(0.52 * SizePx * Text.Len(), 1.2 * SizePx);
	}
	return FVector2D(FSlateApplication::Get().GetRenderer()->GetFontMeasureService()->Measure(Text, FontOf(SizePx, bMedium), 1.0f));
}

void FLsnUi::EnsureWidget(UWorld* World)
{
	UGameViewportClient* Client = World ? World->GetGameViewport() : nullptr;
	if (!Client || (Widget.IsValid() && Viewport.Get() == Client))
	{
		return;
	}
	RemoveWidget();
	TSharedRef<SCanvas> Blurs = SNew(SCanvas).Visibility(EVisibility::HitTestInvisible);
	for (int32 Index = 0; Index < BlurPool; ++Index)
	{
		// The canvas works in its own units: window pixels over the scale of the view.
		auto Scale = [Client]() { return Client ? FMath::Max(Client->GetDPIScale(), 1e-3f) : 1.0f; };
		Blurs->AddSlot()
			.Position(TAttribute<FVector2D>::CreateLambda([Index, Scale]() { FBox2D Box; float Radius; return BlurBox(Index, Box, Radius) ? Box.Min / Scale() : FVector2D(-10.0, -10.0); }))
			.Size(TAttribute<FVector2D>::CreateLambda([Index, Scale]() { FBox2D Box; float Radius; return BlurBox(Index, Box, Radius) ? (Box.Max - Box.Min) / Scale() : FVector2D::ZeroVector; }))
			[
				SNew(SBackgroundBlur)
				.BlurStrength(9.0f)
				.CornerRadius(TAttribute<FVector4>::CreateLambda([Index, Scale]() { FBox2D Box; float Radius = 0.0f; BlurBox(Index, Box, Radius); const float R = Radius / Scale(); return FVector4(R, R, R, R); }))
			];
	}
	TSharedRef<SOverlay> Root = SNew(SOverlay).Visibility(EVisibility::HitTestInvisible)
		+ SOverlay::Slot()[Blurs]
		+ SOverlay::Slot()[SNew(SLsnUiPainter)];
	Widget = Root;
	Viewport = Client;
	Client->AddViewportWidgetContent(Root, 10);
}

void FLsnUi::RemoveWidget()
{
	if (Widget.IsValid() && Viewport.IsValid())
	{
		Viewport->RemoveViewportWidgetContent(Widget.ToSharedRef());
	}
	Widget.Reset();
	Viewport.Reset();
	Building.Reset();
	Complete.Reset();
}
