#pragma once

#include <stddef.h>
#include <stdint.h>

enum class Bell103DataKind : uint8_t { Data=1, Ack=2 };

// Stop-and-wait half-duplex data link within an established Bell 103 session.
// The outer B103 burst supplies CRC; this header binds DATA/ACK to a session.
class Bell103DataLink {
 public:
  static constexpr size_t HEADER_BYTES=10;
  static constexpr size_t MAX_TEXT=70; // 80-byte FSK burst minus header
  // A receive window can last nine seconds. Leave time for the peer to
  // finish that window and send its ACK before retransmitting.
  static constexpr uint32_t RETRY_MS=18000;
  static constexpr uint8_t MAX_ATTEMPTS=6;
  void begin(uint32_t session);
  void reset();
  bool queue(const uint8_t* text,size_t length);
  bool next(uint32_t now,uint8_t* burst,size_t capacity,size_t& length,Bell103DataKind& kind);
  void sent(Bell103DataKind kind,uint32_t now);
  // Returns true only for a new in-order DATA delivery. Duplicates are ACKed
  // again without being delivered twice.
  bool received(const uint8_t* burst,size_t length,uint8_t* text,size_t capacity,size_t& textLength);
  bool awaitingAck() const {return awaitingAck_;}
  bool failed() const {return failed_;}
  uint16_t pendingSequence() const {return txSequence_;}
 private:
  uint32_t session_=0;
  uint16_t txSequence_=1,rxSequence_=1,ackSequence_=0;
  uint8_t text_[MAX_TEXT];size_t textLength_=0;
  bool awaitingAck_=false,pendingData_=false,failed_=false;
  uint8_t pendingAcks_=0;
  uint8_t attempts_=0;uint32_t lastSent_=0;
  static void header(uint8_t* out,Bell103DataKind kind,uint32_t session,uint16_t sequence);
};
