#pragma once
#include <Arduino.h>
#include "PacketTransport.h"

// RFC 1055 SLIP framing over USB CDC. This transport carries IPv4 (AX.25 PID CC).
class SlipCdcTransport : public PacketTransport {
 public:
  explicit SlipCdcTransport(Stream& stream):stream_(stream){}
  const char* name()const override{return "usb-cdc-slip";}
  void configure(const char* local,const char* remote){local_=local;remote_=remote;}
  void setReceiveHandler(ReceiveHandler handler,void* context)override{handler_=handler;context_=context;}
  bool send(uint8_t pid,const uint8_t* payload,size_t length)override{
    if(pid!=0xcc||!payload||!length||length>sizeof(buffer_))return false;
    stream_.write(END);
    for(size_t k=0;k<length;++k){uint8_t c=payload[k];if(c==END){stream_.write(ESC);stream_.write(ESC_END);}else if(c==ESC){stream_.write(ESC);stream_.write(ESC_ESC);}else stream_.write(c);}
    stream_.write(END);return true;
  }
  bool sendPacket(const TransportPacket& packet)override{return send(packet.pid,packet.payload,packet.payloadLength);}
  void reset(){length_=0;escaped_=false;}
  void acceptByte(uint8_t c){
    if(c==END){
      if(length_&&handler_){TransportPacket packet={nullptr,0,local_,remote_,0x03,0xcc,buffer_,length_,0};handler_(packet,context_);}
      length_=0;escaped_=false;return;
    }
    if(escaped_){if(c==ESC_END)c=END;else if(c==ESC_ESC)c=ESC;else{length_=0;escaped_=false;return;}escaped_=false;}
    else if(c==ESC){escaped_=true;return;}
    if(length_<sizeof(buffer_))buffer_[length_++]=c;else{length_=0;escaped_=false;}
  }
 private:
  static constexpr uint8_t END=0xc0,ESC=0xdb,ESC_END=0xdc,ESC_ESC=0xdd;
  Stream& stream_;const char* local_="LOCAL";const char* remote_="REMOTE";ReceiveHandler handler_=nullptr;void* context_=nullptr;
  uint8_t buffer_[1500];size_t length_=0;bool escaped_=false;
};
