#pragma once
#include "GroupChatProtocol.h"
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Bounded, single-threaded group state machine. service() is called from loop();
// the send callback may block while an AFSK frame is transmitted.
class GroupChatRuntime {
 public:
  using Send=bool (*)(const uint8_t*,size_t,void*);
  using Deliver=void (*)(const char*,uint32_t,const uint8_t*,size_t,void*);
  static constexpr size_t HISTORY=32, PEERS=8, REQUESTS=8;
  void configure(const char* local,const char* group,Send send,Deliver deliver,void* context){
    protocol_.configure(local,group);send_=send;deliver_=deliver;context_=context;
  }
  void setSeed(uint32_t seed){protocol_.setMessageSeed(seed);}
  void enable(bool value,uint32_t now){
    if(enabled_!=value)clearSession();
    enabled_=value;nextSummary_=now+SUMMARY_MS;fastSummaryPending_=false;
  }
  bool enabled()const{return enabled_;}
  const char* group()const{return protocol_.group();}
  bool sendText(const uint8_t* text,size_t length,uint32_t now){
    if(!enabled_||!send_||!text||!length||length>GroupChatProtocol::MAX_TEXT)return false;
    uint32_t id=protocol_.nextId();
    uint8_t wire[220];size_t size=0;
    if(!protocol_.encodeData(wire,sizeof(wire),size,id,text,length))return false;
    if(!send_(wire,size,context_))return false;
    History& entry=history_[historyNext_];entry.id=id;entry.size=size;entry.sentAt=now;memcpy(entry.wire,wire,size);
    historyNext_=(historyNext_+1)%HISTORY;if(historyCount_<HISTORY)++historyCount_;
    nextSummary_=now+FIRST_SUMMARY_MS;fastSummaryPending_=true;
    return true;
  }
  void receive(const uint8_t* wire,size_t length,uint32_t now){
    if(!enabled_)return;
    GroupChatProtocol::Message msg;
    if(!protocol_.decode(wire,length,msg)||strcmp(msg.group,protocol_.group())||!strcmp(msg.source,protocol_.local()))return;
    if(msg.type==GroupChatProtocol::TYPE_DATA){
      Peer* peer=findPeer(msg.source,true);if(!peer)return;
      if(!peer->known){peer->next=msg.id;peer->known=true;}
      if(msg.id>peer->next && msg.id-peer->next<=REQUESTS)
        for(uint32_t id=peer->next;id<msg.id;++id)arm(*peer,id,now);
      if(!seen(*peer,msg.id)){
        remember(*peer,msg.id);
        if(deliver_)deliver_(msg.source,msg.id,msg.text,msg.textLength,context_);
      }
      if(msg.id>=peer->next)peer->next=msg.id+1;
      cancel(msg.source,msg.id);
    }else if(msg.type==GroupChatProtocol::TYPE_SUMMARY){
      Peer* peer=findPeer(msg.source,true);if(!peer)return;
      uint32_t first=read32(msg.text);
      // A newly joined receiver must not fetch messages sent before it joined.
      // Once DATA has established the peer, SUMMARY can repair later gaps.
      if(!peer->known){peer->next=msg.id+1;peer->known=true;return;}
      uint32_t end=msg.id-first<HISTORY?msg.id:first+HISTORY-1;
      for(uint32_t id=first;id<=end;++id)if(!seen(*peer,id))arm(*peer,id,now);
    }else if(msg.type==GroupChatProtocol::TYPE_NACK){
      char missing[7];memcpy(missing,msg.text,6);missing[6]=0;
      for(int i=5;i>=0&&missing[i]==' ';--i)missing[i]=0;
      if(!strcmp(missing,protocol_.local())){
        for(size_t i=0;i<HISTORY;++i)if(recoverable(history_[i],now)&&history_[i].id==msg.id){
          if(!retransmit_.active){retransmit_={true,msg.id,now+150+(msg.id%350)};}break;
        }
      }else defer(missing,msg.id,now); // Suppress immediate duplicates, but retry if no DATA follows.
    }
  }
  void service(uint32_t now){
    if(!enabled_||!send_)return;
    if(retransmit_.active && due(now,retransmit_.at)){
      for(size_t i=0;i<HISTORY;++i)if(recoverable(history_[i],now)&&history_[i].id==retransmit_.id)
        {send_(history_[i].wire,history_[i].size,context_);break;}
      retransmit_.active=false;return;
    }
    for(auto& request:requests_)if(request.active&&due(now,request.at)){
      if(!seenSource(request.source,request.id)){
        uint8_t wire[32];size_t size=0;
        if(protocol_.encodeNack(wire,sizeof(wire),size,request.source,request.id))send_(wire,size,context_);
        if(++request.tries<3)request.at=now+3000+(request.id%1000);
        else request.active=false;
      }else request.active=false;
      return;
    }
    if(historyCount_&&due(now,nextSummary_)){
      const History* oldest=nullptr;const History* latest=nullptr;
      for(size_t i=0;i<historyCount_;++i){
        const History& entry=history_[(historyNext_+HISTORY-historyCount_+i)%HISTORY];
        if(recoverable(entry,now)){if(!oldest)oldest=&entry;latest=&entry;}
      }
      if(oldest&&latest){
        uint8_t wire[32];size_t size=0;
        if(protocol_.encodeSummary(wire,sizeof(wire),size,oldest->id,latest->id))
          send_(wire,size,context_);
      }
      nextSummary_=now+(fastSummaryPending_?SECOND_SUMMARY_MS:SUMMARY_MS);
      fastSummaryPending_=false;
    }
  }
 private:
  static constexpr uint32_t FIRST_SUMMARY_MS=3000, SECOND_SUMMARY_MS=5000;
  static constexpr uint32_t SUMMARY_MS=10000, RECOVERY_WINDOW_MS=60000;
  struct History{uint32_t id=0;size_t size=0;uint32_t sentAt=0;uint8_t wire[220];};
  struct Peer{char name[7]={};bool known=false;uint32_t next=0;uint32_t seenIds[32]={};size_t seenCount=0,seenNext=0;};
  struct Request{bool active=false;char source[7]={};uint32_t id=0,at=0;uint8_t tries=0;};
  struct Retransmit{bool active=false;uint32_t id=0,at=0;};
  GroupChatProtocol protocol_;Send send_=nullptr;Deliver deliver_=nullptr;void* context_=nullptr;
  bool enabled_=false,fastSummaryPending_=false;uint32_t nextSummary_=0;
  History history_[HISTORY];size_t historyNext_=0,historyCount_=0;
  Peer peers_[PEERS];Request requests_[REQUESTS];Retransmit retransmit_;
  static uint32_t read32(const uint8_t* p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
  static bool due(uint32_t now,uint32_t at){return (int32_t)(now-at)>=0;}
  static bool recoverable(const History& entry,uint32_t now){
    return entry.size&&(uint32_t)(now-entry.sentAt)<RECOVERY_WINDOW_MS;
  }
  void clearSession(){
    memset(history_,0,sizeof(history_));historyNext_=historyCount_=0;
    memset(peers_,0,sizeof(peers_));memset(requests_,0,sizeof(requests_));retransmit_={};
  }
  Peer* findPeer(const char* name,bool create){
    for(auto& peer:peers_)if(peer.name[0]&&!strcmp(peer.name,name))return &peer;
    if(create)for(auto& peer:peers_)if(!peer.name[0]){strncpy(peer.name,name,6);peer.name[6]=0;return &peer;}
    return nullptr;
  }
  static bool seen(const Peer& peer,uint32_t id){for(size_t i=0;i<peer.seenCount;++i)if(peer.seenIds[i]==id)return true;return false;}
  static void remember(Peer& peer,uint32_t id){peer.seenIds[peer.seenNext]=id;peer.seenNext=(peer.seenNext+1)%32;if(peer.seenCount<32)++peer.seenCount;}
  bool seenSource(const char* source,uint32_t id){Peer* peer=findPeer(source,false);return peer&&seen(*peer,id);}
  void cancel(const char* source,uint32_t id){for(auto& request:requests_)if(request.active&&request.id==id&&!strcmp(request.source,source))request.active=false;}
  void defer(const char* source,uint32_t id,uint32_t now){
    for(auto& request:requests_)if(request.active&&request.id==id&&!strcmp(request.source,source))
      request.at=now+3000+(id%1000);
  }
  void arm(Peer& peer,uint32_t id,uint32_t now){
    if(seen(peer,id))return;
    for(auto& request:requests_)if(request.active&&request.id==id&&!strcmp(request.source,peer.name))return;
    for(auto& request:requests_)if(!request.active){request.active=true;strncpy(request.source,peer.name,7);request.id=id;request.tries=0;
      uint32_t salt=0;for(const char* p=protocol_.local();*p;++p)salt=salt*33u+(uint8_t)*p;
      request.at=now+200+((id*1103515245u+now+salt)%600);return;}
  }
};
