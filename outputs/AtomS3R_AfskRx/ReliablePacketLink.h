#pragma once
#include <Arduino.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <esp_random.h>

// Stop-and-wait reliable message layer carried in AX.25 PID CF frames.
// It is transport-independent: the caller supplies send, delivery and status callbacks.
class ReliablePacketLink {
 public:
  static constexpr uint8_t WIRE_PID=0xcf;
  static constexpr uint8_t HOST_REQUEST_PID=0xfe;
  static constexpr uint8_t HOST_REQUEST_IPV4_PID=0xfd;
  static constexpr size_t MAX_MESSAGE=1500;
  static constexpr size_t FRAGMENT_DATA=64;
  static constexpr uint8_t MAX_FRAGMENTS=(MAX_MESSAGE+FRAGMENT_DATA-1)/FRAGMENT_DATA;
  using SendFunction=bool (*)(uint8_t,const uint8_t*,size_t,void*);
  using DeliveryHandler=void (*)(uint8_t,const uint8_t*,size_t,void*);
  using StatusHandler=void (*)(const char*,uint16_t,uint8_t,uint8_t,void*);

  void configure(SendFunction sender,DeliveryHandler delivery,StatusHandler status,void* context){
    sender_=sender;delivery_=delivery;status_=status;context_=context;
  }
  void cancel(){active_=waiting_=retryPending_=ackPending_=rxActive_=false;}
  void setContentionIdentity(const char* identity){
    uint32_t hash=2166136261u;
    if(identity)while(*identity){hash^=(uint8_t)*identity++;hash*=16777619u;}
    // Keep common ATOMA/ATOMB peers in separate ~1 s airtime slots.
    contentionDelayMs_=(hash%3u)*1000u;
    if(!nextId_){nextId_=(uint16_t)esp_random();if(!nextId_)nextId_=1;}
  }
  bool beginSend(uint8_t applicationPid,const uint8_t* data,size_t length){
    if(active_||!data||!length||length>MAX_MESSAGE)return false;
    memcpy(tx_,data,length);txLength_=length;txPid_=applicationPid;
    txId_=++nextId_;if(!txId_)txId_=++nextId_;
    txCrc_=crc32(tx_,txLength_);txCount_=(uint8_t)((length+FRAGMENT_DATA-1)/FRAGMENT_DATA);
    txIndex_=0;attempts_=0;waiting_=false;active_=true;report("START",txId_,0,txCount_);return true;
  }
  void onPacket(const uint8_t* data,size_t length){
    Header h;if(!decode(data,length,h))return;
    if(h.type==2){
      if(active_&&waiting_&&h.id==txId_&&h.index==txIndex_){
        waiting_=false;retryPending_=false;attempts_=0;report("ACK",txId_,txIndex_+1,txCount_);
        if(++txIndex_>=txCount_){active_=false;report("SENT",txId_,txCount_,txCount_);}
      }
      return;
    }
    if(h.type!=1||h.count<1||h.count>MAX_FRAGMENTS||h.index>=h.count||h.total<1||h.total>MAX_MESSAGE)return;
    size_t expected=h.index+1==h.count?h.total-(size_t)h.index*FRAGMENT_DATA:FRAGMENT_DATA;
    if(length!=HEADER_SIZE+expected)return;
    if(h.id==lastCompleteId_&&h.crc==lastCompleteCrc_){queueAck(h);return;}
    if(!rxActive_||h.id!=rxId_||h.crc!=rxCrc_){
      rxActive_=true;rxId_=h.id;rxCrc_=h.crc;rxTotal_=h.total;rxCount_=h.count;rxMask_=0;rxPid_=h.applicationPid;
    }
    if(h.total!=rxTotal_||h.count!=rxCount_)return;
    memcpy(rx_+(size_t)h.index*FRAGMENT_DATA,data+HEADER_SIZE,expected);rxMask_|=(1u<<h.index);queueAck(h);
    uint32_t complete=(1u<<rxCount_)-1u;
    if(rxMask_==complete&&crc32(rx_,rxTotal_)==rxCrc_){
      lastCompleteId_=rxId_;lastCompleteCrc_=rxCrc_;rxActive_=false;
      report("RECEIVED",rxId_,rxCount_,rxCount_);if(delivery_)delivery_(rxPid_,rx_,rxTotal_,context_);
    }
  }
  void service(){
    if(ackPending_){if((uint32_t)(millis()-ackQueuedAt_)<ACK_DELAY_MS)return;uint8_t frame[HEADER_SIZE];encode(frame,2,ackId_,ackIndex_,ackCount_,ackTotal_,ackCrc_,ackPid_);
      if(sender_&&sender_(WIRE_PID,frame,sizeof(frame),context_)){ackPending_=false;if(retryPending_)retryAt_=millis()+POST_ACK_GUARD_MS;}return;}
    if(!active_||!sender_)return;
    uint32_t now=millis();
    if(retryPending_){
      if((int32_t)(now-retryAt_)<0)return;
      retryPending_=false;
    }
    if(waiting_){
      if((uint32_t)(now-sentAt_)<ACK_TIMEOUT_MS)return;
      if(attempts_>=MAX_ATTEMPTS){uint16_t id=txId_;active_=waiting_=false;report("FAILED",id,txIndex_+1,txCount_);return;}
      waiting_=false;retryPending_=true;retryAt_=now+250u+contentionDelayMs_+(esp_random()%501u);
      report("RETRY",txId_,txIndex_+1,txCount_);return;
    }
    size_t offset=(size_t)txIndex_*FRAGMENT_DATA;
    size_t amount=txLength_-offset;if(amount>FRAGMENT_DATA)amount=FRAGMENT_DATA;
    uint8_t frame[HEADER_SIZE+FRAGMENT_DATA];encode(frame,1,txId_,txIndex_,txCount_,txLength_,txCrc_,txPid_);
    memcpy(frame+HEADER_SIZE,tx_+offset,amount);
    ++attempts_;if(sender_(WIRE_PID,frame,HEADER_SIZE+amount,context_)){waiting_=true;sentAt_=millis();report("FRAGMENT",txId_,txIndex_+1,txCount_);}
  }
  bool busy()const{return active_;}
 private:
  static constexpr size_t HEADER_SIZE=15;static constexpr uint32_t ACK_DELAY_MS=350,ACK_TIMEOUT_MS=3000,POST_ACK_GUARD_MS=600;static constexpr uint8_t MAX_ATTEMPTS=4;
  struct Header{uint8_t type;uint16_t id;uint8_t index,count;uint16_t total;uint32_t crc;uint8_t applicationPid;};
  SendFunction sender_=nullptr;DeliveryHandler delivery_=nullptr;StatusHandler status_=nullptr;void* context_=nullptr;
  uint8_t tx_[MAX_MESSAGE],rx_[MAX_MESSAGE];size_t txLength_=0,rxTotal_=0;uint8_t txPid_=0,rxPid_=0;
  uint16_t nextId_=0,txId_=0,rxId_=0,lastCompleteId_=0;uint32_t rxMask_=0,txCrc_=0,rxCrc_=0,lastCompleteCrc_=0;
  uint8_t txIndex_=0,txCount_=0,rxCount_=0,attempts_=0;bool active_=false,waiting_=false,retryPending_=false,rxActive_=false;uint32_t sentAt_=0,retryAt_=0;
  bool ackPending_=false;uint16_t ackId_=0,ackTotal_=0;uint8_t ackIndex_=0,ackCount_=0,ackPid_=0;uint32_t ackCrc_=0,ackQueuedAt_=0,contentionDelayMs_=0;
  void report(const char* state,uint16_t id,uint8_t current,uint8_t total){if(status_)status_(state,id,current,total,context_);}
  void queueAck(const Header& h){ackPending_=true;ackQueuedAt_=millis();ackId_=h.id;ackIndex_=h.index;ackCount_=h.count;ackTotal_=h.total;ackCrc_=h.crc;ackPid_=h.applicationPid;}
  static void encode(uint8_t* p,uint8_t type,uint16_t id,uint8_t index,uint8_t count,uint16_t total,uint32_t crc,uint8_t pid){
    p[0]='R';p[1]='L';p[2]=1;p[3]=type;p[4]=(uint8_t)id;p[5]=(uint8_t)(id>>8);p[6]=index;p[7]=count;
    p[8]=(uint8_t)total;p[9]=(uint8_t)(total>>8);p[10]=(uint8_t)crc;p[11]=(uint8_t)(crc>>8);p[12]=(uint8_t)(crc>>16);p[13]=(uint8_t)(crc>>24);p[14]=pid;
  }
  static bool decode(const uint8_t* p,size_t n,Header& h){
    if(!p||n<HEADER_SIZE||p[0]!='R'||p[1]!='L'||p[2]!=1)return false;h.type=p[3];h.id=(uint16_t)p[4]|((uint16_t)p[5]<<8);
    h.index=p[6];h.count=p[7];h.total=(uint16_t)p[8]|((uint16_t)p[9]<<8);h.crc=(uint32_t)p[10]|((uint32_t)p[11]<<8)|((uint32_t)p[12]<<16)|((uint32_t)p[13]<<24);h.applicationPid=p[14];return true;
  }
  static uint32_t crc32(const uint8_t* data,size_t length){
    uint32_t crc=0xffffffffu;for(size_t i=0;i<length;++i){crc^=data[i];for(int b=0;b<8;++b)crc=(crc>>1)^(0xedb88320u&-(int32_t)(crc&1));}return ~crc;
  }
};
