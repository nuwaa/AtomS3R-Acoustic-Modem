#pragma once

#include <stddef.h>
#include <stdint.h>

enum class Bell103Role : uint8_t { Originate, Answer };

// Experimental 300-baud, 8N1, half-duplex Bell 103 data path. This is
// separate from AX.25; its small B103/CRC frame is not an AX.25 frame.
class Bell103FskTx {
 public:
  static constexpr uint32_t SAMPLE_RATE=48000, SYMBOL_SAMPLES=160;
  static constexpr size_t MAX_PAYLOAD=80;
  static constexpr size_t MAX_BITS=30*10+10+(4+1+1+MAX_PAYLOAD+2)*10+10;
  Bell103FskTx();
  bool begin(const uint8_t* payload,size_t length,Bell103Role role);
  size_t render(int32_t* stereo,size_t frames);
  bool finished() const { return sample_>=bitCount_*SYMBOL_SAMPLES; }
  size_t bits() const { return bitCount_; }
 private:
  float table_[1024];
  uint8_t bits_[MAX_BITS];
  size_t bitCount_=0;
  uint32_t sample_=0;
  float phase_=0;
  Bell103Role role_=Bell103Role::Originate;
  void appendByte(uint8_t byte);
  float sine(float phase) const;
};

class Bell103FskRx {
 public:
  static constexpr size_t MAX_PAYLOAD=Bell103FskTx::MAX_PAYLOAD;
  // Decodes one short burst from 48 kHz signed mono PCM. Returns only data
  // passing sync, framing, length, and CRC checks; no guessed text escapes.
  bool decode(const int16_t* pcm,size_t samples,Bell103Role localRole,
              uint8_t* payload,size_t capacity,size_t& length);
 private:
  static constexpr size_t MAX_SYMBOLS=1800;
  uint8_t bits_[MAX_SYMBOLS];
  uint8_t bytes_[MAX_SYMBOLS/10+1];
  float markCos_[40],markSin_[40],spaceCos_[40],spaceSin_[40];
  void tune(Bell103Role localRole);
  bool decodeOffset(const int16_t* pcm,size_t samples,size_t offset,
                    uint8_t* payload,size_t capacity,size_t& length);
};
