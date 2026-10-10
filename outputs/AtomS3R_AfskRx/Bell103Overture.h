#pragma once

#include <stddef.h>
#include <stdint.h>

// A dial-up sound performance, independent of the Bell 103 data modem.
// The V.21 tones in CI/CMJM/CJ/training are an audible approximation of a
// dial-up handshake; they do not signal readiness or carry Bell 103 data.
// Inspired by dbhq-uk/modem's MIT-licensed overture.rs:
// Copyright (c) 2026 DBHQ Ventures Ltd. See THIRD_PARTY.md.
class Bell103Overture {
 public:
  static constexpr uint32_t SAMPLE_RATE=48000;
  static constexpr uint32_t SYMBOL_SAMPLES=160; // 300 baud
  static constexpr uint32_t TOTAL_SAMPLES=
      2400+48000+7*9600+192000+6*10*160+144000+
      8*10*160+6*10*160+3600+30*10*160;

  Bell103Overture();
  void reset();
  size_t render(int32_t* stereo,size_t frames);
  bool finished() const { return position_>=TOTAL_SAMPLES; }
  uint32_t position() const { return position_; }

 private:
  static constexpr size_t TABLE_SIZE=1024;
  float table_[TABLE_SIZE];
  uint32_t position_=0;
  uint32_t noise_=0x2545f491;
  float phaseA_=0,phaseB_=0,phaseAm_=0,clickEnvelope_=1;
  float sine(float phase) const;
  float oscillator(float frequency,float& phase);
  float twoTone(float first,float second);
  float v21ByteStream(const char* bytes,size_t count,uint32_t sample);
  float sampleAt(uint32_t sample);
};
