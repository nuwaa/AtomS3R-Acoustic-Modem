#include "../AtomS3R_AfskRx/AcousticMode.h"

#include <assert.h>
#include <string.h>

int main() {
  AcousticMode mode = AcousticMode::Ax25;
  assert(!strcmp(acousticModeName(mode), "ax25"));
  assert(parseAcousticMode("bell103", mode));
  assert(mode == AcousticMode::Bell103);
  assert(!strcmp(acousticModeName(mode), "bell103"));
  assert(!parseAcousticMode("bell202", mode));
  assert(mode == AcousticMode::Bell103);
  assert(!parseAcousticMode(nullptr, mode));
  assert(parseAcousticMode("ax25", mode));
  assert(mode == AcousticMode::Ax25);
}
