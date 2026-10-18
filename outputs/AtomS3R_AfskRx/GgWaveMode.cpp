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

bool GgWaveMode::beginTx(const uint8_t* frame, size_t length, int volume) {
  if (!frame || length != kPayloadBytes || volume < 20 || volume > 95) return false;
  stop(); // RX FFT history cannot include our own speaker output.
  GGWave::Protocols::tx().only(GGWAVE_PROTOCOL_DT_FASTEST);
  modem_ = new (std::nothrow) GGWave();
  if (!modem_ || !modem_->prepare(parameters(GGWAVE_OPERATING_MODE_TX)) ||
      !modem_->init(static_cast<int>(length), reinterpret_cast<const char*>(frame),
                    GGWAVE_PROTOCOL_DT_FASTEST, volume)) {
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

int GgWaveMode::feedRx48(const int32_t* stereo, size_t frames, uint8_t* data, size_t capacity) {
  if (!modem_ || transmitting_ || !stereo || !data || capacity < kPayloadBytes || frames > kMaxInputFrames) return -1;
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
  memcpy(data, decoded.data(), kPayloadBytes);
  return static_cast<int>(kPayloadBytes);
}
