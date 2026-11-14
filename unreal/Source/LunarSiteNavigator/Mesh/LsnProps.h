#pragma once

#include "CoreMinimal.h"
#include "Mesh/LsnMesh.h"

/**
 * Scale objects: a generic lander, a mast and boulders, made in Blender by
 * Scripts/blender/make_scale_objects.py and stored as OBJ files in Content/LsnModels.
 *
 * They give a sense of size and nothing else. They belong to no package, no number on
 * screen refers to them, and they are separate from the terrain mesh, so the horizon
 * comparison never sees them.
 */
namespace LsnProps
{
	/** Folder of the OBJ files: <project>/Content/LsnModels. */
	LUNARSITENAVIGATOR_API FString ModelDirectory();

	/**
	 * Reads an OBJ file (metres, Z up, triangles, "usemtl" groups) into a mesh in Unreal
	 * centimetres with its origin kept. Blender's axes are right-handed and Unreal's are
	 * not: Y is mirrored. Every face corner becomes its own vertex, so flat faces stay flat.
	 */
	LUNARSITENAVIGATOR_API bool LoadObj(const FString& File, FLsnMeshData& OutMesh, FString& OutError);

	/** Grey value of a material name of the models; a display choice. */
	LUNARSITENAVIGATOR_API FColor MaterialColor(const FString& MaterialName);

	/** Adds a mesh to another: scaled, then turned about the vertical by YawDeg, then moved. */
	LUNARSITENAVIGATOR_API void Append(const FLsnMeshData& Source, const FVector& Scale, double YawDeg, const FVector& Location, FLsnMeshData& InOutMesh);

	/**
	 * The mast for an observer height: base on the ground, a pole up to the height, the head
	 * at the height. Below 1 m there is only the head on the ground. Origin on the ground.
	 */
	LUNARSITENAVIGATOR_API bool BuildMast(double ObserverHeightM, FLsnMeshData& OutMesh, FString& OutError);
}
