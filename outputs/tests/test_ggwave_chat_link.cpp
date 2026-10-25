#include "../AtomS3R_AfskRx/GgWaveChatLink.h"

#include <assert.h>
#include <string.h>

int main() {
  uint8_t text[] = "first\r\nsecond\rthird\nfourth";
  const char expected[] = "first\nsecond\nthird\nfourth";
  const size_t length = GgWaveChatLink::normalizeNewlines(text, sizeof(text) - 1);
  assert(length == sizeof(expected) - 1);
  assert(!memcmp(text, expected, length));

  size_t characters = 0;
  assert(!GgWaveChatLink::validUtf8(text, length, characters));
  assert(GgWaveChatLink::validUtf8(text, length, characters, true));
  assert(characters == length);

  GgWaveChatLink sender;
  assert(!sender.queue(text, length, 1000));  // ATOM chat commands stay single-line.

  const uint8_t japanese[] = {
    0xe4,0xb8,0x80,0xe8,0xa1,0x8c,0xe7,0x9b,0xae,'\n',
    0xe4,0xba,0x8c,0xe8,0xa1,0x8c,0xe7,0x9b,0xae
  };
  assert(GgWaveChatLink::validUtf8(japanese, sizeof(japanese), characters, true));
  assert(characters == 7);
}
