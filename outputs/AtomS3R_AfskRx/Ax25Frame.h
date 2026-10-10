#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

struct Ax25View {
  char destination[10] = {};
  char source[10] = {};
  uint8_t control = 0;
  uint8_t pid = 0;
  const uint8_t* information = nullptr;
  size_t informationLength = 0;
};

class Ax25Frame {
 public:
  static uint16_t crc(const uint8_t* data, size_t length) {
    uint16_t value=0xffff;
    while (length--) {
      value^=*data++;
      for (int bit=0;bit<8;++bit) value=(value>>1)^((value&1)?0x8408:0);
    }
    return value;
  }

  static bool makeUi(uint8_t* output, size_t capacity, size_t& length,
                     const char* destination, uint8_t destinationSsid,
                     const char* source, uint8_t sourceSsid,
                     const uint8_t* information, size_t informationLength,
                     uint8_t pid=0xf0) {
    if (!output || !information || informationLength>240 || capacity<16+informationLength) return false;
    length=0;
    if (!appendAddress(output,capacity,length,destination,destinationSsid,false) ||
        !appendAddress(output,capacity,length,source,sourceSsid,true)) return false;
    output[length++]=0x03;
    output[length++]=pid;
    memcpy(output+length,information,informationLength);
    length+=informationLength;
    return true;
  }

  static bool parse(const uint8_t* frame, size_t length, Ax25View& view) {
    if (!frame || length<16) return false;
    size_t offset=0,addresses=0;
    char first[10]={},second[10]={};
    bool last=false;
    while (offset+7<=length && addresses<10) {
      char* target=addresses==0?first:addresses==1?second:nullptr;
      if (target && !decodeAddress(frame+offset,target,10)) return false;
      for (size_t k=0;k<6;++k) if (frame[offset+k]&1) return false;
      last=(frame[offset+6]&1)!=0;
      offset+=7;
      ++addresses;
      if (last) break;
    }
    if (!last || addresses<2 || offset+2>length) return false;
    memcpy(view.destination,first,sizeof(first));
    memcpy(view.source,second,sizeof(second));
    view.control=frame[offset++];
    view.pid=frame[offset++];
    view.information=frame+offset;
    view.informationLength=length-offset;
    return true;
  }

 private:
  static bool appendAddress(uint8_t* output,size_t capacity,size_t& length,
                            const char* call,uint8_t ssid,bool last) {
    if (!call || ssid>15 || length+7>capacity) return false;
    size_t n=strlen(call);
    if (n<1 || n>6) return false;
    for (size_t k=0;k<6;++k) {
      char c=k<n?call[k]:' ';
      if (c>='a' && c<='z') c-=32;
      if (!((c>='A'&&c<='Z')||(c>='0'&&c<='9')||c==' ')) return false;
      output[length++]=(uint8_t)c<<1;
    }
    output[length++]=(uint8_t)(0x60|(ssid<<1)|(last?1:0));
    return true;
  }

  static bool decodeAddress(const uint8_t* encoded,char* output,size_t capacity) {
    size_t used=0;
    for (size_t k=0;k<6 && used+1<capacity;++k) {
      char c=(char)(encoded[k]>>1);
      if (c!=' ') output[used++]=c;
    }
    uint8_t ssid=(encoded[6]>>1)&15;
    if (ssid && used+3<capacity) {
      output[used++]='-';
      if (ssid>=10) output[used++]=(char)('0'+ssid/10);
      output[used++]=(char)('0'+ssid%10);
    }
    output[used]=0;
    return used>0;
  }
};
