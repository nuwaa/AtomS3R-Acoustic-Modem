#include "Bell103Overture.h"
#include <math.h>

namespace {
constexpr float PI2=6.2831853071795864769f;
constexpr uint32_t OFF_HOOK=2400, DIAL_TONE=48000, DIGIT=9600;
constexpr uint32_t RINGBACK=192000, ANSAM=144000, CJ_SILENCE=3600;
const char DIAL_DIGITS[]="5551234"; // Decorative: no telephone network is dialled.
const char CI[]="CICICI", CMJM[]="CMJMCMJM", CJ[]="CJCJCJ";
struct Dtmf { char digit; uint16_t row,col; };
constexpr Dtmf DTMF[]={
  {'1',697,1209},{'2',697,1336},{'3',697,1477},
  {'4',770,1209},{'5',770,1336},{'6',770,1477},
  {'7',852,1209},{'8',852,1336},{'9',852,1477},
  {'*',941,1209},{'0',941,1336},{'#',941,1477}
};
}

Bell103Overture::Bell103Overture() {
  for(size_t i=0;i<TABLE_SIZE;++i)table_[i]=sinf(PI2*(float)i/TABLE_SIZE);
  reset();
}

void Bell103Overture::reset() {
  position_=0;noise_=0x2545f491;phaseA_=phaseB_=phaseAm_=0;clickEnvelope_=1;
}

float Bell103Overture::sine(float phase) const {
  float index=phase*TABLE_SIZE;
  size_t first=(size_t)index & (TABLE_SIZE-1);
  float fraction=index-(float)(size_t)index;
  return table_[first]+(table_[(first+1)&(TABLE_SIZE-1)]-table_[first])*fraction;
}

float Bell103Overture::oscillator(float frequency,float& phase) {
  float value=sine(phase);
  phase+=frequency/SAMPLE_RATE;
  if(phase>=1)phase-=1;
  return value;
}

float Bell103Overture::twoTone(float first,float second) {
  return .4f*(oscillator(first,phaseA_)+oscillator(second,phaseB_));
}

float Bell103Overture::v21ByteStream(const char* bytes,size_t count,uint32_t sample) {
  uint32_t symbol=sample/SYMBOL_SAMPLES;
  size_t byte=symbol/10;
  if(byte>=count)return 0;
  unsigned bit=symbol%10;
  bool mark=bit==9 || (bit>0 && (((uint8_t)bytes[byte]>>(bit-1))&1));
  return .6f*oscillator(mark?980.f:1180.f,phaseA_);
}

float Bell103Overture::sampleAt(uint32_t sample) {
  if(sample<OFF_HOOK){
    noise_^=noise_<<13;noise_^=noise_>>17;noise_^=noise_<<5;
    float out=.4f*clickEnvelope_*((float)(noise_&0xffff)/32767.5f-1.f);
    clickEnvelope_*=.9974f;
    return out;
  }
  sample-=OFF_HOOK;
  if(sample<DIAL_TONE)return twoTone(350,450);
  sample-=DIAL_TONE;
  if(sample<7*DIGIT){
    uint32_t part=sample%DIGIT;
    if(part>=4800)return 0;
    char digit=DIAL_DIGITS[sample/DIGIT];
    for(const auto& entry:DTMF)if(entry.digit==digit)return twoTone(entry.row,entry.col);
    return 0;
  }
  sample-=7*DIGIT;
  if(sample<RINGBACK){
    // Two UK double rings: 0.4 on, 0.2 off, 0.4 on, 2 s gap, then repeat.
    uint32_t part=sample<144000?sample:sample-144000;
    if((part<19200)||(part>=28800&&part<48000))return twoTone(400,450);
    return 0;
  }
  sample-=RINGBACK;
  constexpr uint32_t CI_SAMPLES=(sizeof(CI)-1)*10*SYMBOL_SAMPLES;
  if(sample<CI_SAMPLES)return v21ByteStream(CI,sizeof(CI)-1,sample);
  sample-=CI_SAMPLES;
  if(sample<ANSAM){
    float carrier=oscillator(2100,phaseA_);
    float am=oscillator(15,phaseAm_);
    float polarity=(sample/21600)&1?-1.f:1.f;
    return .55f*(1.f+.3f*am)*polarity*carrier;
  }
  sample-=ANSAM;
  constexpr uint32_t CMJM_SAMPLES=(sizeof(CMJM)-1)*10*SYMBOL_SAMPLES;
  if(sample<CMJM_SAMPLES)return v21ByteStream(CMJM,sizeof(CMJM)-1,sample);
  sample-=CMJM_SAMPLES;
  constexpr uint32_t CJ_SAMPLES=(sizeof(CJ)-1)*10*SYMBOL_SAMPLES;
  if(sample<CJ_SAMPLES)return v21ByteStream(CJ,sizeof(CJ)-1,sample);
  sample-=CJ_SAMPLES;
  if(sample<CJ_SILENCE)return 0;
  sample-=CJ_SILENCE;
  if(sample<30*10*SYMBOL_SAMPLES){
    uint32_t bit=(sample/SYMBOL_SAMPLES)%10;
    bool mark=bit==9 || (bit>0 && ((0x55>>(bit-1))&1));
    return .6f*oscillator(mark?980.f:1180.f,phaseA_);
  }
  return 0;
}

size_t Bell103Overture::render(int32_t* stereo,size_t frames) {
  if(!stereo)return 0;
  size_t written=0;
  for(;written<frames&&position_<TOTAL_SAMPLES;++written,++position_){
    float sample=sampleAt(position_);
    int32_t value=(int32_t)(sample*2147483647.f);
    stereo[written*2]=value;stereo[written*2+1]=value;
  }
  return written;
}
