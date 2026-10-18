#pragma once

#include <stddef.h>
#include <stdint.h>
#include <ggwave/ggwave.h>

// Official ggwave codec with one active direction at a time. The caller owns
// ES8311/I2S and calls feedRx48() or renderTx48() in bounded blocks.
class GgWaveMode {
public:
  static constexpr size_t kPayloadBytes = 16;
  static constexpr size_t kMaxInputFrames = 256;

  ~GgWaveMode();
  bool beginRx();
  bool beginTx(const uint8_t* utf8, size_t length);
  void stop();
  bool transmitting() const { return transmitting_; }
  bool txFinished() const { return transmitting_ && txOffset_ >= txSamples_; }
  size_t renderTx48(int32_t* stereo, size_t capacityFrames);
  // Positive: validated UTF-8 byte count. 0: waiting. -1: audio/codec error.
  // -2: decoded data was not a valid UTF-8 text payload.
  int feedRx48(const int32_t* stereo, size_t frames, uint8_t* text, size_t capacity);
  int heapBytes() const { return modem_ ? modem_->heapSize() : 0; }

private:
  static GGWave::Parameters parameters(int operatingMode);
  static bool validUtf8(const uint8_t* text, size_t length);
  GGWave* modem_ = nullptr;
  bool transmitting_ = false;
  size_t txOffset_ = 0;
  size_t txSamples_ = 0;
  bool haveOdd_ = false;
  int16_t oddSample_ = 0;
  int16_t rxFrame_[512] = {};
  size_t rxCount_ = 0;
};
