#include "Bell103Fsk.h"
#include <math.h>
#include <string.h>

namespace {
constexpr float TAU=6.2831853071795864769f;
constexpr uint8_t SYNC[4]={'B','1','0','3'};
constexpr uint8_t VERSION=1;

uint16_t crc16(const uint8_t* bytes,size_t length) {
  uint16_t crc=0xffff;
  for(size_t i=0;i<length;++i){
    crc^=(uint16_t)bytes[i]<<8;
    for(int bit=0;bit<8;++bit)crc=(crc&0x8000)?(uint16_t)((crc<<1)^0x1021):(uint16_t)(crc<<1);
  }
  return crc;
}
}

Bell103FskTx::Bell103FskTx() {
  for(size_t i=0;i<1024;++i)table_[i]=sinf(TAU*i/1024.f);
}

void Bell103FskTx::appendByte(uint8_t byte) {
  bits_[bitCount_++]=0; // space start bit
  for(int bit=0;bit<8;++bit)bits_[bitCount_++]=(byte>>bit)&1;
  bits_[bitCount_++]=1; // mark stop bit
}

bool Bell103FskTx::begin(const uint8_t* payload,size_t length,Bell103Role role) {
  if(!payload||!length||length>MAX_PAYLOAD)return false;
  bitCount_=0;sample_=0;phase_=0;role_=role;
  for(int i=0;i<30;++i)appendByte(0x55); // transitions for timing acquisition
  for(int i=0;i<10;++i)bits_[bitCount_++]=1; // idle mark resets UART alignment
  for(uint8_t byte:SYNC)appendByte(byte);
  uint8_t contents[2+MAX_PAYLOAD];
  contents[0]=VERSION;contents[1]=(uint8_t)length;
  memcpy(contents+2,payload,length);
  for(size_t i=0;i<length+2;++i)appendByte(contents[i]);
  uint16_t crc=crc16(contents,length+2);
  appendByte((uint8_t)crc);appendByte((uint8_t)(crc>>8));
  for(int i=0;i<10;++i)bits_[bitCount_++]=1;
  return true;
}

float Bell103FskTx::sine(float phase) const {
  float index=phase*1024;
  size_t first=(size_t)index&1023;
  float fraction=index-(size_t)index;
  return table_[first]+(table_[(first+1)&1023]-table_[first])*fraction;
}

size_t Bell103FskTx::render(int32_t* stereo,size_t frames) {
  if(!stereo)return 0;
  size_t done=0;
  while(done<frames&&!finished()){
    bool mark=bits_[sample_/SYMBOL_SAMPLES]!=0;
    float frequency=role_==Bell103Role::Originate?(mark?1270.f:1070.f):(mark?2225.f:2025.f);
    int32_t value=(int32_t)(.6f*sine(phase_)*2147483647.f);
    stereo[2*done]=value;stereo[2*done+1]=value;
    phase_+=frequency/SAMPLE_RATE;if(phase_>=1)phase_-=1;
    ++sample_;++done;
  }
  return done;
}

void Bell103FskRx::tune(Bell103Role localRole) {
  // Receive the other station's band, never our own transmit band.
  float mark=localRole==Bell103Role::Originate?2225.f:1270.f;
  float space=localRole==Bell103Role::Originate?2025.f:1070.f;
  for(size_t i=0;i<40;++i){
    markCos_[i]=cosf(TAU*mark*i/12000.f);
    markSin_[i]=sinf(TAU*mark*i/12000.f);
    spaceCos_[i]=cosf(TAU*space*i/12000.f);
    spaceSin_[i]=sinf(TAU*space*i/12000.f);
  }
}

bool Bell103FskRx::decode(const int16_t* pcm,size_t samples,Bell103Role localRole,
                          uint8_t* payload,size_t capacity,size_t& length) {
  length=0;
  if(!pcm||!payload||samples<48000||capacity==0)return false;
  tune(localRole);
  for(size_t offset=0;offset<40;++offset)
    if(decodeOffset(pcm,samples,offset,payload,capacity,length))return true;
  return false;
}

bool Bell103FskRx::decodeOffset(const int16_t* pcm,size_t samples,size_t offset,
                                uint8_t* payload,size_t capacity,size_t& length) {
  size_t downsampled=samples/4;
  size_t symbols=(downsampled>offset?(downsampled-offset)/40:0);
  if(symbols>MAX_SYMBOLS)symbols=MAX_SYMBOLS;
  for(size_t symbol=0;symbol<symbols;++symbol){
    float mi=0,mq=0,si=0,sq=0;
    size_t start=(offset+symbol*40)*4;
    for(size_t k=0;k<40;++k){
      size_t at=start+4*k;
      float sample=(float)((int32_t)pcm[at]+pcm[at+1]+pcm[at+2]+pcm[at+3]);
      mi+=sample*markCos_[k];mq+=sample*markSin_[k];
      si+=sample*spaceCos_[k];sq+=sample*spaceSin_[k];
    }
    bits_[symbol]=(mi*mi+mq*mq)>=(si*si+sq*sq);
  }
  size_t byteCount=0;
  bool framed=false;unsigned count=0;uint8_t byte=0;
  for(size_t i=0;i<symbols;++i){
    bool mark=bits_[i]!=0;
    if(!framed){if(!mark){framed=true;count=0;byte=0;}continue;}
    if(count<8){if(mark)byte|=(uint8_t)(1U<<count);++count;continue;}
    framed=false;
    if(mark&&byteCount<sizeof(bytes_))bytes_[byteCount++]=byte;
  }
  for(size_t i=0;i+8<=byteCount;++i){
    if(memcmp(bytes_+i,SYNC,4)||bytes_[i+4]!=VERSION)continue;
    size_t len=bytes_[i+5];
    if(!len||len>MAX_PAYLOAD||len>capacity||i+8+len>byteCount)continue;
    uint16_t received=(uint16_t)bytes_[i+6+len]|((uint16_t)bytes_[i+7+len]<<8);
    if(crc16(bytes_+i+4,2+len)!=received)continue;
    memcpy(payload,bytes_+i+6,len);length=len;return true;
  }
  return false;
}
