#include "GgWaveMode.h"

#include <new>
#include <string.h>

GgWaveMode::~GgWaveMode() { stop(); }

GGWave::Parameters GgWaveMode::parameters(int operatingMode) {
  auto result = GGWave::getDefaultParameters();
  result.payloadLength = kPayloadBytes;
  result.sampleRateInp = 24000;
  result.sampleRateOut = 24000;
  result.sampleRate = 24000;
  result.samplesPerFrame = 512;
  result.sampleFormatInp = GGWAVE_SAMPLE_FORMAT_I16;
  result.sampleFormatOut = GGWAVE_SAMPLE_FORMAT_I16;
  result.operatingMode = operatingMode;
  return result;
}

void GgWaveMode::stop() {
  delete modem_;
  modem_ = nullptr;
  transmitting_ = false;
  txOffset_ = txSamples_ = 0;
  haveOdd_ = false;
  rxCount_ = 0;
}

bool GgWaveMode::beginRx() {
  stop();
  GGWave::setLogFile(nullptr);
  GGWave::Protocols::rx().only(GGWAVE_PROTOCOL_DT_FASTEST);
  GGWave::Protocols::tx().only(GGWAVE_PROTOCOL_DT_FASTEST);
  modem_ = new (std::nothrow) GGWave();
  if (!modem_ || !modem_->prepare(parameters(GGWAVE_OPERATING_MODE_RX))) {
    stop();
    return false;
  }
  return true;
}

bool GgWaveMode::beginTx(const uint8_t* utf8, size_t length) {
  if (!utf8 || !length || length > kPayloadBytes || !validUtf8(utf8, length)) return false;
  stop(); // RX FFT history cannot include our own speaker output.
  GGWave::Protocols::tx().only(GGWAVE_PROTOCOL_DT_FASTEST);
  modem_ = new (std::nothrow) GGWave();
  if (!modem_ || !modem_->prepare(parameters(GGWAVE_OPERATING_MODE_TX)) ||
      !modem_->init(static_cast<int>(length), reinterpret_cast<const char*>(utf8),
                    GGWAVE_PROTOCOL_DT_FASTEST, 10)) {
    stop();
    return false;
  }
  const uint32_t bytes = modem_->encode();
  if (!bytes || (bytes & 1) || !modem_->txWaveform()) {
    stop();
    return false;
  }
  txSamples_ = bytes / sizeof(int16_t);
  txOffset_ = 0;
  transmitting_ = true;
  return true;
}

size_t GgWaveMode::renderTx48(int32_t* stereo, size_t capacityFrames) {
  if (!transmitting_ || !stereo || capacityFrames < 2) return 0;
  const auto* samples = static_cast<const int16_t*>(modem_->txWaveform());
  const size_t sourceCount = (capacityFrames / 2 < txSamples_ - txOffset_)
      ? capacityFrames / 2 : txSamples_ - txOffset_;
  for (size_t i = 0; i < sourceCount; ++i) {
    const size_t pos = txOffset_ + i;
    const int32_t first = static_cast<int32_t>(samples[pos]) * 65536;
    const int32_t next = static_cast<int32_t>(samples[pos + (pos + 1 < txSamples_ ? 1 : 0)]);
    const int32_t midpoint = ((static_cast<int32_t>(samples[pos]) + next) / 2) * 65536;
    stereo[4*i] = stereo[4*i + 1] = first;
    stereo[4*i + 2] = stereo[4*i + 3] = midpoint;
  }
  txOffset_ += sourceCount;
  return sourceCount * 2;
}

bool GgWaveMode::validUtf8(const uint8_t* text, size_t length) {
  for (size_t i = 0; i < length;) {
    const uint8_t first = text[i];
    if (first == 0 || first == '\r' || first == '\n') return false;
    if (first < 0x80) { ++i; continue; }
    int extra = 0;
    uint32_t codepoint = 0;
    if (first >= 0xC2 && first <= 0xDF) { extra = 1; codepoint = first & 0x1F; }
    else if (first >= 0xE0 && first <= 0xEF) { extra = 2; codepoint = first & 0x0F; }
    else if (first >= 0xF0 && first <= 0xF4) { extra = 3; codepoint = first & 0x07; }
    else return false;
    if (i + extra >= length) return false;
    for (int j = 1; j <= extra; ++j) {
      if ((text[i+j] & 0xC0) != 0x80) return false;
      codepoint = (codepoint << 6) | (text[i+j] & 0x3F);
    }
    if ((extra == 1 && codepoint < 0x80) ||
        (extra == 2 && codepoint < 0x800) ||
        (extra == 3 && codepoint < 0x10000) ||
        (codepoint >= 0xD800 && codepoint <= 0xDFFF) || codepoint > 0x10FFFF) return false;
    i += extra + 1;
  }
  return true;
}

int GgWaveMode::feedRx48(const int32_t* stereo, size_t frames, uint8_t* text, size_t capacity) {
  if (!modem_ || transmitting_ || !stereo || !text || capacity < kPayloadBytes || frames > kMaxInputFrames) return -1;
  for (size_t i = 0; i < frames; ++i) {
    const int16_t sample = static_cast<int16_t>(stereo[2*i] >> 16);
    if (!haveOdd_) { oddSample_ = sample; haveOdd_ = true; }
    else {
      rxFrame_[rxCount_++] = static_cast<int16_t>((static_cast<int32_t>(oddSample_) + sample) / 2);
      haveOdd_ = false;
    }
  }
  if (rxCount_ < 512) return 0;
  rxCount_ = 0;
  if (!modem_->decode(rxFrame_, sizeof(rxFrame_))) return -1;
  uint8_t decodedBytes[kPayloadBytes] = {};
  GGWave::TxRxData decoded(decodedBytes, kPayloadBytes);
  const int length = modem_->rxTakeData(decoded);
  if (length <= 0) return 0;
  if (length != static_cast<int>(kPayloadBytes)) return -2;
  size_t used = 0;
  while (used < kPayloadBytes && decoded[used] != 0) ++used;
  if (!used || !validUtf8(decoded.data(), used)) return -2;
  for (size_t i = used; i < kPayloadBytes; ++i) if (decoded[i] != 0) return -2;
  memcpy(text, decoded.data(), used);
  return static_cast<int>(used);
}
