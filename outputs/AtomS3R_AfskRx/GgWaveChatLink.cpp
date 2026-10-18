#include "GgWaveChatLink.h"

#include <string.h>

namespace {
constexpr uint8_t kData = 1;
constexpr uint8_t kAck = 2;
constexpr uint32_t kAckWaitMs = 5000;
constexpr uint32_t kTurnaroundMs = 450;
constexpr uint32_t kReceiveExpiryMs = 600000;
constexpr uint8_t kMaxRetries = 4;
}

void GgWaveChatLink::resetReceive() {
  receiveLength_ = 0;
  receiveId_ = 0;
  receiveNext_ = 0;
  receiveCount_ = 0;
  receiveActive_ = false;
  receiveAt_ = 0;
}

void GgWaveChatLink::reset() {
  sendLength_ = 0; sendIndex_ = sendCount_ = retries_ = 0;
  sendActive_ = awaitingAck_ = failed_ = false; sendAt_ = ackDeadline_ = 0;
  lastTxType_ = 0; ackPending_ = false; haveDelivered_ = false;
  resetReceive();
}

bool GgWaveChatLink::validUtf8(const uint8_t* text, size_t length, size_t& characters) {
  characters = 0;
  if (!text || !length || length > kMaxTextBytes) return false;
  for (size_t i = 0; i < length;) {
    uint8_t c = text[i];
    if (!c || c == '\r' || c == '\n') return false;
    if (c < 0x80) { ++i; ++characters; continue; }
    int extra = 0; uint32_t cp = 0;
    if (c >= 0xC2 && c <= 0xDF) { extra = 1; cp = c & 0x1F; }
    else if (c >= 0xE0 && c <= 0xEF) { extra = 2; cp = c & 0x0F; }
    else if (c >= 0xF0 && c <= 0xF4) { extra = 3; cp = c & 0x07; }
    else return false;
    if (i + extra >= length) return false;
    for (int j = 1; j <= extra; ++j) {
      if ((text[i+j] & 0xC0) != 0x80) return false;
      cp = (cp << 6) | (text[i+j] & 0x3F);
    }
    if ((extra == 1 && cp < 0x80) || (extra == 2 && cp < 0x800) ||
        (extra == 3 && cp < 0x10000) || (cp >= 0xD800 && cp <= 0xDFFF) ||
        cp > 0x10FFFF) return false;
    i += extra + 1;
    if (++characters > kMaxCharacters) return false;
  }
  return true;
}

uint8_t GgWaveChatLink::checksum(const uint8_t* data, size_t length) {
  uint8_t crc = 0;
  for (size_t i = 0; i < length; ++i) {
    crc ^= data[i];
    for (int j = 0; j < 8; ++j) crc = (crc & 0x80) ? (crc << 1) ^ 0x07 : crc << 1;
  }
  return crc;
}

void GgWaveChatLink::encode(uint8_t frame[kFrameBytes], uint8_t type, uint16_t id,
                            uint8_t index, uint8_t count, const uint8_t* data, uint8_t length) {
  memset(frame, 0, kFrameBytes);
  frame[0] = 'G'; frame[1] = 'W'; frame[2] = 1; frame[3] = type;
  frame[4] = id & 0xff; frame[5] = id >> 8;
  frame[6] = index; frame[7] = count; frame[8] = length;
  if (length) memcpy(frame + kHeaderBytes, data, length);
  frame[9] = checksum(frame, 9) ^ checksum(frame + kHeaderBytes, length);
}

bool GgWaveChatLink::decode(const uint8_t frame[kFrameBytes], uint8_t& type,
                            uint16_t& id, uint8_t& index, uint8_t& count, uint8_t& length) {
  if (frame[0] != 'G' || frame[1] != 'W' || frame[2] != 1) return false;
  type = frame[3]; id = frame[4] | (uint16_t(frame[5]) << 8);
  index = frame[6]; count = frame[7]; length = frame[8];
  if ((type != kData && type != kAck) || !count || count > kMaxFragments ||
      index >= count || length > kFragmentBytes ||
      (type == kAck && length) || (type == kData &&
       (!length || (index + 1 < count && length != kFragmentBytes)))) return false;
  if (frame[9] != (checksum(frame, 9) ^ checksum(frame + kHeaderBytes, length))) return false;
  for (size_t i = kHeaderBytes + length; i < kFrameBytes; ++i) if (frame[i]) return false;
  return true;
}

bool GgWaveChatLink::queue(const uint8_t* text, size_t length, uint32_t now) {
  size_t characters = 0;
  if (sendActive_ || !validUtf8(text, length, characters)) return false;
  memcpy(sendText_, text, length);
  sendLength_ = length; sendIndex_ = retries_ = 0;
  sendCount_ = (length + kFragmentBytes - 1) / kFragmentBytes;
  ++sendId_; if (!sendId_) ++sendId_;
  sendActive_ = true; awaitingAck_ = failed_ = false; sendAt_ = now;
  return true;
}

bool GgWaveChatLink::poll(uint32_t now, uint8_t frame[kFrameBytes]) {
  if (lastTxType_) return false;
  if (ackPending_ && int32_t(now - ackAt_) >= 0) {
    encode(frame, kAck, ackId_, ackIndex_, ackCount_, nullptr, 0);
    ackPending_ = false; lastTxType_ = kAck;
    return true;
  }
  if (!sendActive_) return false;
  if (awaitingAck_) {
    if (int32_t(now - ackDeadline_) < 0) return false;
    awaitingAck_ = false;
    if (++retries_ > kMaxRetries) { sendActive_ = false; failed_ = true; return false; }
    sendAt_ = now;
  }
  if (int32_t(now - sendAt_) < 0 || ackPending_) return false;
  const size_t offset = size_t(sendIndex_) * kFragmentBytes;
  const uint8_t length = sendLength_ - offset < kFragmentBytes ? sendLength_ - offset : kFragmentBytes;
  encode(frame, kData, sendId_, sendIndex_, sendCount_, sendText_ + offset, length);
  lastTxType_ = kData;
  return true;
}

void GgWaveChatLink::txComplete(uint32_t now) {
  if (lastTxType_ == kData && sendActive_) {
    awaitingAck_ = true; ackDeadline_ = now + kAckWaitMs;
  }
  lastTxType_ = 0;
}

void GgWaveChatLink::txFailed(uint32_t now) {
  if (lastTxType_ == kData && sendActive_) {
    if (++retries_ > kMaxRetries) { sendActive_ = false; failed_ = true; }
    else { awaitingAck_ = false; sendAt_ = now + kTurnaroundMs; }
  }
  lastTxType_ = 0;
}

GgWaveChatLink::Event GgWaveChatLink::accept(const uint8_t frame[kFrameBytes], uint32_t now,
                                              uint8_t* completeText, size_t& completeLength) {
  completeLength = 0;
  uint8_t type, index, count, length; uint16_t id;
  if (!decode(frame, type, id, index, count, length)) return Event::Invalid;
  if (type == kAck) {
    if (!sendActive_ || !awaitingAck_ || id != sendId_ || index != sendIndex_ || count != sendCount_) return Event::None;
    awaitingAck_ = false; retries_ = 0;
    if (++sendIndex_ == sendCount_) { sendActive_ = false; return Event::Delivered; }
    sendAt_ = now + kTurnaroundMs;
    return Event::AckReceived;
  }
  if (receiveActive_ && uint32_t(now - receiveAt_) > kReceiveExpiryMs) resetReceive();
  if (haveDelivered_ && id == deliveredId_ && uint32_t(now - deliveredAt_) < kReceiveExpiryMs) {
    ackPending_ = true; ackId_ = id; ackIndex_ = index; ackCount_ = count;
    ackAt_ = now + kTurnaroundMs;
    return Event::Duplicate;
  }
  if (index == 0 && (!receiveActive_ || id != receiveId_)) {
    resetReceive(); receiveActive_ = true; receiveId_ = id; receiveCount_ = count;
  }
  if (!receiveActive_ || receiveId_ != id || receiveCount_ != count || index > receiveNext_) return Event::None;
  if (index == receiveNext_) {
    if (receiveLength_ + length > kMaxTextBytes) { resetReceive(); return Event::Invalid; }
    memcpy(receiveText_ + receiveLength_, frame + kHeaderBytes, length);
    receiveLength_ += length; ++receiveNext_;
  }
  receiveAt_ = now;
  ackPending_ = true; ackId_ = id; ackIndex_ = index; ackCount_ = count;
  ackAt_ = now + kTurnaroundMs;
  if (receiveNext_ != count) return Event::FragmentReceived;
  size_t characters = 0;
  if (!validUtf8(receiveText_, receiveLength_, characters)) {
    ackPending_ = false; resetReceive(); return Event::Invalid;
  }
  memcpy(completeText, receiveText_, receiveLength_);
  completeLength = receiveLength_;
  deliveredId_ = id; deliveredAt_ = now; haveDelivered_ = true;
  resetReceive();
  return Event::Received;
}
