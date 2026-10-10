#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <string.h>

// Offline Bell 202 receiver, 48000 samples/s. No Arduino dependency.
class AfskDecoder {
 public:
  using FrameFn = void (*)(const uint8_t*, size_t, size_t);
  using YieldFn = void (*)();
  void reset() { seenCount = 0; }

  // PCM may be interleaved. scratch has count floats. Reuse it for each slot.
  void decode(const int16_t* pcm, size_t count, size_t stride,
              float* scratch, FrameFn onFrame, YieldFn idle = nullptr) {
    if (count < 80) return;
    const size_t before = seenCount;
    float cs[2][40], sn[2][40];
    for (int f = 0; f < 2; ++f) {
      for (int k = 0; k < 40; ++k) {
        float a = 6.28318530718f * (f ? 2200.f : 1200.f) * k / 48000.f;
        cs[f][k] = cosf(a); sn[f][k] = sinf(a);
      }
    }
    // Each value describes the 40-sample window beginning at i.
    // Remove its DC before comparing noncoherent tone correlation energies.
    for (size_t i = 0; i + 40 <= count; ++i) {
      float mean = 0;
      for (int k = 0; k < 40; ++k) mean += pcm[(i+k)*stride];
      mean /= 40;
      float re[2] = {}, im[2] = {};
      for (int k = 0; k < 40; ++k) {
        float x = pcm[(i+k)*stride] - mean;
        for (int f = 0; f < 2; ++f) {
          re[f] += x*cs[f][k]; im[f] += x*sn[f][k];
        }
      }
      scratch[i] = re[0]*re[0] + im[0]*im[0] - re[1]*re[1] - im[1]*im[1];
      if (idle && (i & 2047) == 0) idle();
    }
    // Batch recording permits a small clock/phase search instead of a PLL.
    // Start at nominal baud. Then cover +/- 4 baud in 1-baud steps.
    const int offsets[] = {0,-1,1,-2,2,-3,3,-4,4};
    for (int off : offsets) {
      const double step = 48000.0 / (1200 + off);
      for (int phase = 0; phase < 40; phase += 4) {
        resetHdlc();
        bool previous = scratch[phase] >= 0;
        for (double t = phase + step; t + 40 <= count; t += step) {
          size_t at = (size_t)(t + 0.5);
          if (at + 40 > count) break;
          bool tone = scratch[at] >= 0;
          pushBit(tone == previous, at, onFrame); // NRZI: transition = zero
          previous = tone;
        }
        if (idle) idle();
      }
    }
    if (seenCount == before) decodeShort(pcm,count,stride,scratch,onFrame,idle);
  }

  static uint16_t crc(const uint8_t* p, size_t n) {
    uint16_t c = 0xffff;
    while (n--) {
      c ^= *p++;
      for (int k = 0; k < 8; ++k) c = (c >> 1) ^ ((c & 1) ? 0x8408 : 0);
    }
    return c; // AX.25 including the received FCS must leave 0xf0b8.
  }

 private:
  // Fallback for an acoustically colored signal. Least-squares projection
  // separates non-orthogonal 1200/2200 Hz sinusoids in a 24-sample window.
  // Coefficients: pinv([cos1200,sin1200,cos2200,sin2200] with column means removed).
  // All candidates still pass the same HDLC and unmodified CRC check.
  void decodeShort(const int16_t* pcm, size_t count, size_t stride,
                   float* scratch, FrameFn onFrame, YieldFn idle) {
    static const float projection[4][24] = {
      {3.970515380e-01f, 2.316292354e-01f, 9.705112299e-02f, -2.846923752e-03f, -6.723841021e-02f, -9.819205180e-02f, -1.003198696e-01f, -8.022100495e-02f, -4.577140264e-02f, -5.321972398e-03f, 3.312496019e-02f, 6.268974223e-02f, 7.827343532e-02f, 7.704336247e-02f, 5.870455530e-02f, 2.553380541e-02f, -1.782672460e-02f, -6.479886766e-02f, -1.074842751e-01f, -1.374141534e-01f, -1.463687229e-01f, -1.271959037e-01f, -7.455831303e-02f, 1.445683851e-02f},
      {-8.111014427e-01f, -2.903691750e-01f, 8.969949799e-02f, 3.279922171e-01f, 4.346434909e-01f, 4.294672113e-01f, 3.396206001e-01f, 1.967093220e-01f, 3.358839661e-02f, -1.188629348e-01f, -2.347139823e-01f, -2.954476024e-01f, -2.917062887e-01f, -2.241701068e-01f, -1.034915255e-01f, 5.070726247e-02f, 2.116888634e-01f, 3.481484382e-01f, 4.272363459e-01f, 4.177957855e-01f, 2.935356817e-01f, 3.586255010e-02f, -3.638783017e-01f, -9.029543034e-01f},
      {-3.665578660e-01f, -8.758626745e-02f, 1.085999166e-01f, 2.222838124e-01f, 2.603045792e-01f, 2.350951792e-01f, 1.632751462e-01f, 6.392368797e-02f, -4.331583020e-02f, -1.401359249e-01f, -2.113061191e-01f, -2.461060065e-01f, -2.393278302e-01f, -1.917630541e-01f, -1.101314358e-01f, -6.458581056e-03f, 1.030450528e-01f, 1.995081672e-01f, 2.631954740e-01f, 2.754234263e-01f, 2.204298991e-01f, 8.703568405e-02f, -1.300479896e-01f, -4.293831201e-01f},
      {-2.511945586e-01f, -1.422545361e-01f, -4.594004830e-02f, 3.264149424e-02f, 9.002070733e-02f, 1.245780384e-01f, 1.366006681e-01f, 1.281817048e-01f, 1.029718736e-01f, 6.580602190e-02f, 2.223699368e-02f, -2.198306306e-02f, -6.142972572e-02f, -9.149694482e-02f, -1.088098196e-01f, -1.115246817e-01f, -9.949122779e-02f, -7.426309377e-02f, -3.895604450e-02f, 2.034200245e-03f, 4.343063449e-02f, 7.955639269e-02f, 1.048581311e-01f, 1.144268833e-01f}
    };
    for (size_t i=0;i+24<=count;++i) {
      float c[4]={};
      for (int k=0;k<24;++k) {
        float x=pcm[(i+k)*stride];
        for (int j=0;j<4;++j) c[j]+=projection[j][k]*x;
      }
      float mark=c[0]*c[0]+c[1]*c[1];
      float space=c[2]*c[2]+c[3]*c[3];
      scratch[i]=(mark-space)/(mark+space+1e-12f);
      if (idle && (i & 2047)==0) idle();
    }
    const float thresholds[]={0.f,-1.f/3.f,1.f/3.f,-.6f,.6f,-.8f,.8f};
    const int offsets[]={0,-1,1,-2,2,-3,3,-4,4};
    for (float threshold:thresholds) for (int off:offsets) {
      const double step=48000.0/(1200+off);
      for (int phase=0;phase<40;phase+=2) {
        resetHdlc();
        bool previous=scratch[phase]>=threshold;
        for (double t=phase+step;t+24<=count;t+=step) {
          size_t at=(size_t)(t+.5);
          if (at+24>count) break;
          bool tone=scratch[at]>=threshold;
          pushBit(tone==previous,at,onFrame);
          previous=tone;
        }
        if (idle) idle();
      }
    }
  }

  uint8_t raw[4096], frame[330];
  size_t used = 0;
  uint8_t shift = 0;
  bool collecting = false;
  struct Seen { size_t at; uint32_t hash; } seen[64];
  size_t seenCount = 0;
  void resetHdlc() { used=0; shift=0; collecting=false; }

  void pushBit(bool b, size_t at, FrameFn cb) {
    shift = (uint8_t)((shift >> 1) | (b ? 0x80 : 0));
    if (collecting) {
      if (used < sizeof(raw)) raw[used++] = b;
      else { collecting = false; used = 0; }
    }
    if (shift == 0x7e) {
      if (collecting && used >= 8) finish(used - 8, at, cb);
      collecting = true; used = 0;
    }
    if (shift == 0xff) { collecting = false; used = 0; }
  }

  void finish(size_t n, size_t at, FrameFn cb) {
    size_t bits = 0;
    unsigned ones = 0;
    memset(frame, 0, sizeof(frame));
    for (size_t i = 0; i < n; ++i) {
      bool b = raw[i];
      if (ones == 5) {
        if (b) return; // invalid stuffing / abort
        ones = 0; continue;
      }
      ones = b ? ones + 1 : 0;
      if (bits >= sizeof(frame)*8) return;
      frame[bits/8] |= (uint8_t)(b << (bits%8));
      ++bits;
    }
    if (ones == 5 || bits%8 || bits < 17*8) return;
    size_t len = bits/8;
    if (crc(frame, len) != 0xf0b8) return;
    // Minimum AX.25 address structure: 2..10 shifted callsign/SSID fields.
    size_t addr = 0;
    bool end = false;
    while (addr + 7 <= len - 3 && addr < 70) {
      for (size_t k=0; k<6; ++k) if (frame[addr+k] & 1) return;
      end = frame[addr+6] & 1;
      addr += 7;
      if (end) break;
    }
    if (!end || addr < 14) return;
    uint32_t hash = 2166136261u;
    for (size_t k=0; k<len; ++k) hash = (hash ^ frame[k])*16777619u;
    for (size_t k=0; k<seenCount; ++k) {
      size_t distance = at > seen[k].at ? at-seen[k].at : seen[k].at-at;
      if (distance < 80 && hash == seen[k].hash) return;
    }
    if (seenCount < 64) seen[seenCount++] = {at,hash};
    cb(frame, len-2, at); // omit flags, stuffed bits and two FCS bytes
  }
};
