#pragma once

#include <stddef.h>
#include <stdint.h>

// Stop-and-wait, half-duplex framing above the official fixed-length ggwave codec.
// Both ends must use this protocol version; it is intentionally independent of AX.25.
class GgWaveChatLink {
public:
  static constexpr size_t kFrameBytes = 64;
  static constexpr size_t kHeaderBytes = 10;
  static constexpr size_t kFragmentBytes = kFrameBytes - kHeaderBytes;
  static constexpr size_t kMaxTextBytes = 1120; // 280 four-byte Unicode code points
  static constexpr size_t kMaxCharacters = 280;
  static constexpr uint8_t kMaxFragments = (kMaxTextBytes + kFragmentBytes - 1) / kFragmentBytes;
  enum class Event : uint8_t { None, AckReceived, FragmentReceived, Delivered, Received, Duplicate, Invalid };

  void reset();
  void setIdSeed(uint16_t seed) { sendId_ = seed; }
  bool queue(const uint8_t* text, size_t length, uint32_t now);
  bool poll(uint32_t now, uint8_t frame[kFrameBytes]);
  void txComplete(uint32_t now);
  void txFailed(uint32_t now);
  Event accept(const uint8_t frame[kFrameBytes], uint32_t now,
               uint8_t* completeText, size_t& completeLength);
  bool busy() const { return sendActive_; }
  bool takeFailure() { const bool result = failed_; failed_ = false; return result; }
  uint8_t sentFragments() const { return sendIndex_; }
  uint8_t totalFragments() const { return sendCount_; }
  uint8_t retries() const { return retries_; }
  uint8_t receivedFragments() const { return receiveNext_; }
  uint8_t expectedFragments() const { return receiveCount_; }
  uint16_t sendId() const { return sendId_; }

private:
  static bool validUtf8(const uint8_t* text, size_t length, size_t& characters);
  static uint8_t checksum(const uint8_t* data, size_t length);
  static bool decode(const uint8_t frame[kFrameBytes], uint8_t& type,
                     uint16_t& id, uint8_t& index, uint8_t& count, uint8_t& length);
  static void encode(uint8_t frame[kFrameBytes], uint8_t type, uint16_t id,
                     uint8_t index, uint8_t count, const uint8_t* data, uint8_t length);
  void resetReceive();

  uint8_t sendText_[kMaxTextBytes] = {};
  size_t sendLength_ = 0;
  uint16_t sendId_ = 0;
  uint8_t sendIndex_ = 0;
  uint8_t sendCount_ = 0;
  uint8_t retries_ = 0;
  bool sendActive_ = false;
  bool failed_ = false;
  bool awaitingAck_ = false;
  uint32_t sendAt_ = 0;
  uint32_t ackDeadline_ = 0;
  uint8_t lastTxType_ = 0;

  uint8_t receiveText_[kMaxTextBytes] = {};
  size_t receiveLength_ = 0;
  uint16_t receiveId_ = 0;
  uint8_t receiveNext_ = 0;
  uint8_t receiveCount_ = 0;
  bool receiveActive_ = false;
  uint32_t receiveAt_ = 0;
  uint16_t deliveredId_ = 0;
  uint32_t deliveredAt_ = 0;
  bool haveDelivered_ = false;
  bool ackPending_ = false;
  uint16_t ackId_ = 0;
  uint8_t ackIndex_ = 0;
  uint8_t ackCount_ = 0;
  uint32_t ackAt_ = 0;
};
