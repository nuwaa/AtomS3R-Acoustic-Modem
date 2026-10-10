#pragma once
#include <Arduino.h>
#include "PacketTransport.h"

// Minimal RFC 1662 PPP peer for USB CDC: LCP, IPCP and IPv4 protocol 0021.
class PppCdcTransport : public PacketTransport {
 public:
  explicit PppCdcTransport(Stream& stream):stream_(stream){}
  const char* name()const override{return "usb-cdc-ppp";}
  void configure(const char* local,const char* remote){local_=local;remote_=remote;}
  void setReceiveHandler(ReceiveHandler handler,void* context)override{handler_=handler;context_=context;}
  bool send(uint8_t pid,const uint8_t* payload,size_t length)override{
    return pid==0xcc&&networkOpen_&&sendFrame(0x0021,payload,length);
  }
  bool sendPacket(const TransportPacket& packet)override{return send(packet.pid,packet.payload,packet.payloadLength);}
  void begin(){reset();sendConfigureRequest(0xc021);}
  bool networkOpen()const{return networkOpen_;}
  void acceptByte(uint8_t c){
    if(c==FLAG){if(length_)processFrame();length_=0;escaped_=false;return;}
    if(escaped_){c^=0x20;escaped_=false;}else if(c==ESC){escaped_=true;return;}
    if(length_<sizeof(buffer_))buffer_[length_++]=c;else{length_=0;escaped_=false;}
  }
 private:
  static constexpr uint8_t FLAG=0x7e,ESC=0x7d;static constexpr uint16_t GOOD_FCS=0xf0b8;
  Stream& stream_;const char* local_="LOCAL";const char* remote_="REMOTE";ReceiveHandler handler_=nullptr;void* context_=nullptr;
  uint8_t buffer_[1608];size_t length_=0;bool escaped_=false,lcpMine_=false,lcpPeer_=false,ipcpMine_=false,ipcpPeer_=false,ipcpStarted_=false,networkOpen_=false;
  uint8_t lcpId_=1,ipcpId_=2;
  void reset(){length_=0;escaped_=false;lcpMine_=lcpPeer_=ipcpMine_=ipcpPeer_=ipcpStarted_=networkOpen_=false;lcpId_=1;ipcpId_=2;}
  static uint16_t fcs16(const uint8_t* p,size_t n){uint16_t f=0xffff;while(n--){f^=*p++;for(uint8_t k=0;k<8;++k)f=(f&1)?(f>>1)^0x8408:f>>1;}return f;}
  bool sendFrame(uint16_t protocol,const uint8_t* info,size_t n){
    if(!info||n>1500)return false;uint8_t raw[1506];raw[0]=0xff;raw[1]=0x03;raw[2]=(uint8_t)(protocol>>8);raw[3]=(uint8_t)protocol;
    memcpy(raw+4,info,n);uint16_t f=fcs16(raw,n+4)^0xffff;raw[n+4]=(uint8_t)f;raw[n+5]=(uint8_t)(f>>8);
    stream_.write(FLAG);for(size_t k=0;k<n+6;++k){uint8_t c=raw[k];if(c<0x20||c==FLAG||c==ESC){stream_.write(ESC);stream_.write(c^0x20);}else stream_.write(c);}stream_.write(FLAG);return true;
  }
  void sendConfigureRequest(uint16_t protocol){
    uint8_t packet[10];size_t n=4;packet[0]=1;packet[1]=protocol==0xc021?lcpId_:ipcpId_;
    if(protocol==0xc021){packet[4]=1;packet[5]=4;packet[6]=0x05;packet[7]=0xdc;n=8;}
    else{packet[4]=3;packet[5]=6;packet[6]=10;packet[7]=23;packet[8]=0;packet[9]=254;n=10;}
    packet[2]=(uint8_t)(n>>8);packet[3]=(uint8_t)n;sendFrame(protocol,packet,n);
  }
  void maybeStartIpcp(){if(lcpMine_&&lcpPeer_&&!ipcpStarted_){ipcpStarted_=true;sendConfigureRequest(0x8021);}}
  void control(uint16_t protocol,const uint8_t* p,size_t n){
    if(n<4)return;size_t declared=((size_t)p[2]<<8)|p[3];if(declared<4||declared>n)return;uint8_t code=p[0],id=p[1];
    if(code==1){
      bool restart=protocol==0xc021&&networkOpen_;
      if(restart){lcpMine_=lcpPeer_=ipcpMine_=ipcpPeer_=ipcpStarted_=networkOpen_=false;++lcpId_;if(!lcpId_)++lcpId_;++ipcpId_;if(!ipcpId_)++ipcpId_;}
      uint8_t ack[1504];memcpy(ack,p,declared);ack[0]=2;sendFrame(protocol,ack,declared);
      if(protocol==0xc021){lcpPeer_=true;if(restart||!lcpMine_)sendConfigureRequest(0xc021);else maybeStartIpcp();}
      else{ipcpPeer_=true;if(!ipcpMine_)sendConfigureRequest(0x8021);else networkOpen_=true;}return;
    }
    if(code==2){if(protocol==0xc021&&id==lcpId_){lcpMine_=true;maybeStartIpcp();}else if(protocol==0x8021&&id==ipcpId_){ipcpMine_=true;if(ipcpPeer_)networkOpen_=true;}return;}
    if(code==5){uint8_t ack[1504];memcpy(ack,p,declared);ack[0]=6;sendFrame(protocol,ack,declared);}
  }
  void processFrame(){
    if(length_<6||fcs16(buffer_,length_)!=GOOD_FCS)return;size_t pos=0;if(buffer_[0]==0xff&&buffer_[1]==0x03)pos=2;if(pos+2>length_-2)return;
    uint16_t protocol=((uint16_t)buffer_[pos]<<8)|buffer_[pos+1];const uint8_t* info=buffer_+pos+2;size_t n=length_-pos-4;
    if(protocol==0xc021||protocol==0x8021){control(protocol,info,n);return;}
    if(protocol==0x0021&&handler_&&n&&n<=1500){TransportPacket packet={nullptr,0,local_,remote_,0x03,0xcc,info,n,0};handler_(packet,context_);}
  }
};
