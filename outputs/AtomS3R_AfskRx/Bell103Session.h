#pragma once

#include <stddef.h>
#include <stdint.h>

// Bell 103 session messages are carried inside the CRC-protected B103 FSK
// burst. They are deliberately separate from AX.25, USB and BootMode.
enum class Bell103Message : uint8_t { Hello=1, Ready=2, Confirm=3, Established=4, Bye=5 };
enum class Bell103SessionState : uint8_t {
  Idle, WaitReady, WaitConfirm, WaitEstablished, Connected
};

struct Bell103Control {
  Bell103Message message;
  uint32_t session;
};

class Bell103Session {
 public:
  static constexpr size_t CONTROL_BYTES=8;
  static constexpr uint32_t RETRY_MS=8000;
  static constexpr uint8_t MAX_ATTEMPTS=4;

  // Caller starts with HELLO; answerer enters Idle and listens for HELLO.
  void startCaller(uint32_t session,uint32_t now);
  void startAnswerer();
  void reset();
  Bell103SessionState state() const { return state_; }
  bool connected() const { return state_==Bell103SessionState::Connected; }
  bool caller() const { return caller_; }
  uint32_t session() const { return session_; }

  // action() returns the next control burst to transmit. The host must call
  // sent() only after the complete acoustic burst has left the speaker.
  bool action(uint32_t now,Bell103Control& outgoing);
  void sent(uint32_t now);
  void received(const Bell103Control& incoming,uint32_t now);

  static bool encode(const Bell103Control& control,uint8_t* out,size_t capacity);
  static bool decode(const uint8_t* bytes,size_t length,Bell103Control& out);
 private:
  Bell103SessionState state_=Bell103SessionState::Idle;
  bool caller_=false;
  uint32_t session_=0;
  uint32_t lastTx_=0;
  uint8_t attempts_=0;
  bool pending_=false;
  Bell103Message pendingMessage_=Bell103Message::Hello;
  void queue(Bell103Message message);
};
