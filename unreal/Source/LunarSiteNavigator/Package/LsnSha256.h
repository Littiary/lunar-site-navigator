#pragma once

#include "CoreMinimal.h"

/** SHA-256 (FIPS 180-4), for the digests of the array files of a package (SPEC 3.1). */
namespace LsnSha256
{
	/** The digest of a block of bytes, as 64 lower-case hex characters. */
	LUNARSITENAVIGATOR_API FString HexOf(const uint8* Data, int64 Size);
}
