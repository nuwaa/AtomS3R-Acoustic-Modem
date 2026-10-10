#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include "Ax25Frame.h"

class AfskTransmitter {
 public:
  using SampleSink = bool (*)(const int32_t* stereo, size_t frames, void* context);
  static constexpr uint32_t sampleRate=48000;
  static constexpr uint32_t baud=1200;
  static constexpr size_t samplesPerBit=sampleRate/baud;

  bool transmit(const uint8_t* frame,size_t length,SampleSink sink,void* context,
                unsigned preambleFlags=40,unsigned tailFlags=4) {
    if (!frame || !length || length>256 || !sink) return false;
    reset(sink,context);
    for (unsigned k=0;k<preambleFlags;++k) if (!sendByte(0x7e,false)) return false;
    unsigned ones=0;
    for (size_t i=0;i<length+2;++i) {
      uint8_t byte;
      if (i<length) byte=frame[i];
      else {
        uint16_t fcs=Ax25Frame::crc(frame,length)^0xffff;
        byte=(uint8_t)(i==length?fcs:fcs>>8);
      }
      for (int bit=0;bit<8;++bit) {
        bool value=(byte>>bit)&1;
        if (!sendBit(value)) return false;
        ones=value?ones+1:0;
        if (ones==5) {
          if (!sendBit(false)) return false;
          ones=0;
        }
      }
    }
    for (unsigned k=0;k<tailFlags;++k) if (!sendByte(0x7e,false)) return false;
    if (!flush()) return false;
    return true;
  }

 private:
  SampleSink sink_=nullptr;
  void* context_=nullptr;
  int32_t buffer_[256*2];
  size_t used_=0;
  bool tone_=false;
  double phase_=0;

  void reset(SampleSink sink,void* context) {
    sink_=sink; context_=context; used_=0; tone_=false; phase_=0;
  }
  bool flush() {
    if (!used_) return true;
    bool ok=sink_(buffer_,used_,context_);
    used_=0;
    return ok;
  }
  bool sendByte(uint8_t byte,bool stuffing) {
    unsigned ones=0;
    for (int bit=0;bit<8;++bit) {
      bool value=(byte>>bit)&1;
      if (!sendBit(value)) return false;
      if (stuffing && (ones=value?ones+1:0)==5) {
        if (!sendBit(false)) return false;
        ones=0;
      }
    }
    return true;
  }
  bool sendBit(bool value) {
    if (!value) tone_=!tone_; // NRZI: zero changes tone.
    const double frequency=tone_?2200.0:1200.0;
    const double step=6.283185307179586*frequency/sampleRate;
    for (size_t k=0;k<samplesPerBit;++k) {
      int32_t sample=(int32_t)(sin(phase_)*536870912.0); // 25% of signed 32-bit range.
      phase_+=step;
      if (phase_>=6.283185307179586) phase_-=6.283185307179586;
      buffer_[used_*2]=sample;
      buffer_[used_*2+1]=sample;
      if (++used_==256 && !flush()) return false;
    }
    return true;
  }
};
