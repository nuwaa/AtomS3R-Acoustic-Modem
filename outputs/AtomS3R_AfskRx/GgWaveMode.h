#pragma once

#include <stddef.h>
#include <stdint.h>
#include <ggwave/ggwave.h>

// Official ggwave codec with one active direction at a time. The caller owns
// ES8311/I2S and calls feedRx48() or renderTx48() in bounded blocks.
class GgWaveMode {
public:
  static constexpr size_t kPayloadBytes = 64;
  static constexpr size_t kMaxInputFrames = 256;

  ~GgWaveMode();
  bool beginRx();
  bool beginTx(const uint8_t* frame, size_t length, int volume);
  void stop();
  bool transmitting() const { return transmitting_; }
  uint32_t txDurationMs() const { return static_cast<uint32_t>(txSamples_ * 1000 / 24000); }
  bool txFinished() const { return transmitting_ && txOffset_ >= txSamples_; }
  size_t renderTx48(int32_t* stereo, size_t capacityFrames);
  // Positive: raw frame byte count. 0: waiting. -1: audio/codec error.
  int feedRx48(const int32_t* stereo, size_t frames, uint8_t* data, size_t capacity);
  int heapBytes() const { return modem_ ? modem_->heapSize() : 0; }

private:
  static GGWave::Parameters parameters(int operatingMode);
  GGWave* modem_ = nullptr;
  bool transmitting_ = false;
  size_t txOffset_ = 0;
  size_t txSamples_ = 0;
  bool haveOdd_ = false;
  int16_t oddSample_ = 0;
  int16_t rxFrame_[512] = {};
  size_t rxCount_ = 0;
};
