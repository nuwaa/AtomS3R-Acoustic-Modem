#pragma once
#include <Arduino.h>
#include "PacketTransport.h"

// Line protocol carried by the board's USB CDC serial endpoint:
//   u <HEX>             PID F0 payload from PC
//   x <PIDHEX> <HEX>    arbitrary PID/payload from PC
//   k <HEX>             UTF-8 group-chat request (max 198 bytes)
// Incoming packets are emitted as USB_RX lines for host-side framing.
class UsbCdcTransport : public PacketTransport {
 public:
  explicit UsbCdcTransport(Stream& stream):stream_(stream){}
  const char* name() const override{return "usb-cdc";}
  void configure(const char* local,const char* remote){local_=local;remote_=remote;}
  void setReceiveHandler(ReceiveHandler handler,void* context) override{handler_=handler;context_=context;}
  bool send(uint8_t pid,const uint8_t* payload,size_t length) override {
    return writePacket(remote_,local_,pid,payload,length);
  }
  bool sendPacket(const TransportPacket& packet) override {
    return writePacket(packet.source,packet.destination,packet.pid,packet.payload,packet.payloadLength);
  }
  // Returns true when the complete command belongs to this transport.
  bool acceptLine(const char* line) {
    if(!line||!line[0]||line[1]!=' ')return false;
    uint8_t pid=0;const char* encoded=nullptr;
    if(line[0]=='u'||line[0]=='U'){pid=0xf0;encoded=line+2;}
    else if(line[0]=='z'||line[0]=='Z'){pid=0xfe;encoded=line+2;}
    else if(line[0]=='y'||line[0]=='Y'){pid=0xfd;encoded=line+2;}
    else if(line[0]=='k'||line[0]=='K'){pid=0xfc;encoded=line+2;}
    else if(line[0]=='x'||line[0]=='X'){
      int high=nibble(line[2]),low=nibble(line[3]);
      if(high<0||low<0||line[4]!=' '){stream_.println("ERROR: use x <PIDHEX> <even HEX>, max 1500 bytes.");return true;}
      pid=(uint8_t)((high<<4)|low);encoded=line+5;
    } else return false;
    size_t length=0;
    if(!parseHex(encoded,buffer_,sizeof(buffer_),length)){
      stream_.println((line[0]=='z'||line[0]=='Z'||line[0]=='y'||line[0]=='Y')?"ERROR: use z/y <even HEX>, max 1500 bytes.":(line[0]=='u'||line[0]=='U'?"ERROR: use u <even HEX>, max 1500 bytes.":"ERROR: use x <PIDHEX> <even HEX>, max 1500 bytes."));
      return true;
    }
    if(handler_){
      TransportPacket packet={nullptr,0,local_,remote_,0x03,pid,buffer_,length,0};
      handler_(packet,context_);
    }
    return true;
  }
 private:
  Stream& stream_;const char* local_="LOCAL";const char* remote_="REMOTE";
  ReceiveHandler handler_=nullptr;void* context_=nullptr;uint8_t buffer_[1500];
  static int nibble(char c){if(c>='0'&&c<='9')return c-'0';if(c>='A'&&c<='F')return c-'A'+10;if(c>='a'&&c<='f')return c-'a'+10;return -1;}
  static bool parseHex(const char* text,uint8_t* output,size_t capacity,size_t& length){
    length=0;int high=-1;
    for(;text&&*text;++text){if(*text==' '||*text=='\t')continue;int n=nibble(*text);if(n<0)return false;
      if(high<0)high=n;else{if(length>=capacity)return false;output[length++]=(uint8_t)((high<<4)|n);high=-1;}}
    return high<0&&length>0;
  }
  bool writePacket(const char* source,const char* destination,uint8_t pid,const uint8_t* payload,size_t length){
    if(!payload||!length)return false;
    stream_.print("USB_RX SRC=");stream_.print(source);stream_.print(" DEST=");stream_.print(destination);
    stream_.print(" PID=");if(pid<16)stream_.print('0');stream_.print(pid,HEX);stream_.print(" HEX=");
    for(size_t k=0;k<length;++k){if(payload[k]<16)stream_.print('0');stream_.print(payload[k],HEX);}
    stream_.println();return true;
  }
};
