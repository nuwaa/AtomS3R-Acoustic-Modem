#pragma once

#include <stdint.h>
#include <string.h>

// The air interface is independent of the USB boot protocol (Normal/SLIP/PPP).
enum class AcousticMode : uint8_t { Ax25, Bell103 };

inline const char* acousticModeName(AcousticMode mode) {
  return mode == AcousticMode::Bell103 ? "bell103" : "ax25";
}

inline bool parseAcousticMode(const char* text, AcousticMode& mode) {
  if (!text) return false;
  if (!strcmp(text, "ax25")) { mode = AcousticMode::Ax25; return true; }
  if (!strcmp(text, "bell103")) { mode = AcousticMode::Bell103; return true; }
  return false;
}
