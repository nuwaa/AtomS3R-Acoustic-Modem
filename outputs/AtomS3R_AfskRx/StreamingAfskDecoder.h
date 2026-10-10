#pragma once
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <string.h>
#include "ToneProjection24.h"

// Stateful Bell 202/HDLC receiver. process() accepts arbitrary chunk sizes.
// A bank of timing hypotheses avoids a large PCM buffer and keeps state across
// I2S reads; only CRC-valid AX.25 frames are delivered.
class StreamingAfskDecoder {
 public:
  using FrameFn = void (*)(const uint8_t*,size_t,uint64_t,void*);
  void reset() {
    sample_=0; ringPos_=0; ringUsed_=0; seenCount_=0; winningLane_=0;
    memset(ring_,0,sizeof(ring_));
    for(size_t j=0;j<4;++j)for(size_t k=0;k<window;++k)
      projection_[j][k]=(int16_t)(ToneProjection24::coefficients[j][k]*4096.f);
    for (size_t i=0;i<laneCount;++i) lanes_[i].reset(i);
  }
  StreamingAfskDecoder() { reset(); }
  size_t winningLane() const { return winningLane_; }

  void process(const int16_t* pcm,size_t count,size_t stride,FrameFn callback,void* context) {
    if (!pcm || !stride) return;
    for (size_t n=0;n<count;++n,++sample_) {
      ring_[ringPos_]=pcm[n*stride]; ringPos_=(ringPos_+1)%window;
      if (ringUsed_<window) { ++ringUsed_; continue; }
      if (sample_&3) continue;
      int32_t c[4]={};
      for (size_t k=0;k<window;++k) {
        int32_t x=ring_[(ringPos_+k)%window];
        for(size_t j=0;j<4;++j)c[j]+=projection_[j][k]*x;
      }
      int64_t mark=(int64_t)c[0]*c[0]+(int64_t)c[1]*c[1];
      int64_t space=(int64_t)c[2]*c[2]+(int64_t)c[3]*c[3];
      float discriminator=(float)((double)(mark-space)/(double)(mark+space+1));
      for (size_t i=0;i<laneCount;++i) {
        Lane& lane=lanes_[i];
        if ((double)sample_+0.5 < lane.next) continue;
        lane.next+=lane.step;
        bool tone=discriminator>=lane.threshold;
        bool bit=lane.haveTone ? tone==lane.tone : true;
        lane.tone=tone; lane.haveTone=true;
        push(lane,bit,callback,context);
      }
    }
  }

 private:
  static constexpr size_t window=24, phases=10, rates=1, thresholds=3;
  static constexpr size_t laneCount=phases*rates*thresholds;
  struct Lane {
    double next=0,step=40; float threshold=0; bool tone=false,haveTone=false,collecting=false;
    uint8_t shift=0,raw[350]; size_t used=0;
    void reset(size_t index) {
      static const int baud[rates]={1200};
      static const float level[thresholds]={0.f,-1.f/3.f,1.f/3.f};
      size_t p=index%phases,r=(index/phases)%rates,t=index/(phases*rates);
      next=window+p*4; step=48000.0/baud[r]; tone=false; haveTone=false;
      threshold=level[t]; collecting=false; shift=0; used=0;
    }
  } lanes_[laneCount];
  struct Seen { uint64_t at; uint32_t hash; } seen_[16];
  int16_t ring_[window],projection_[4][window];
  size_t ringPos_=0,ringUsed_=0,seenCount_=0,winningLane_=0;
  uint64_t sample_=0;

  static uint16_t crc(const uint8_t* p,size_t n) {
    uint16_t c=0xffff; while(n--) { c^=*p++; for(int k=0;k<8;++k)c=(c>>1)^((c&1)?0x8408:0); } return c;
  }
  void push(Lane& l,bool bit,FrameFn cb,void* ctx) {
    l.shift=(uint8_t)((l.shift>>1)|(bit?0x80:0));
    if (l.collecting) {
      if (l.used<sizeof(l.raw)*8) {
        if(bit)l.raw[l.used/8]|=(uint8_t)(1u<<(l.used%8));
        else l.raw[l.used/8]&=(uint8_t)~(1u<<(l.used%8));
        ++l.used;
      }
      else { l.collecting=false; l.used=0; }
    }
    if (l.shift==0x7e) {
      if (l.collecting && l.used>=8) finish(l,l.used-8,cb,ctx);
      l.collecting=true; l.used=0;
    } else if (l.shift==0xff) { l.collecting=false; l.used=0; }
  }
  void finish(Lane& l,size_t n,FrameFn cb,void* ctx) {
    uint8_t frame[350]={}; size_t bits=0; unsigned ones=0;
    for(size_t i=0;i<n;++i) {
      bool b=(l.raw[i/8]>>(i%8))&1;
      if(ones==5) { if(b)return; ones=0; continue; }
      ones=b?ones+1:0; if(bits>=sizeof(frame)*8)return;
      frame[bits/8]|=(uint8_t)(b<<(bits%8)); ++bits;
    }
    if(ones==5 || bits%8 || bits<17*8)return;
    size_t len=bits/8; if(crc(frame,len)!=0xf0b8)return;
    size_t addr=0; bool end=false;
    while(addr+7<=len-3 && addr<70) {
      for(size_t k=0;k<6;++k)if(frame[addr+k]&1)return;
      end=frame[addr+6]&1; addr+=7; if(end)break;
    }
    if(!end || addr<14)return;
    uint32_t hash=2166136261u; for(size_t k=0;k<len;++k)hash=(hash^frame[k])*16777619u;
    for(size_t k=0;k<seenCount_;++k) {
      uint64_t d=sample_>seen_[k].at?sample_-seen_[k].at:seen_[k].at-sample_;
      if(d<160 && hash==seen_[k].hash)return;
    }
    if(seenCount_<16)seen_[seenCount_++]={sample_,hash};
    else { memmove(seen_,seen_+1,sizeof(seen_)-sizeof(seen_[0])); seen_[15]={sample_,hash}; }
    winningLane_=(size_t)(&l-lanes_); cb(frame,len-2,sample_,ctx);
  }
};
