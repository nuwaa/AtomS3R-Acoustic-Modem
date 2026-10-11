#include "Bell103DataLink.h"
#include <string.h>

void Bell103DataLink::reset() {
  session_=0;txSequence_=rxSequence_=1;ackSequence_=0;textLength_=0;
  awaitingAck_=pendingData_=failed_=false;pendingAcks_=0;attempts_=0;lastSent_=0;
}

void Bell103DataLink::begin(uint32_t session) {reset();session_=session;}

void Bell103DataLink::header(uint8_t* out,Bell103DataKind kind,uint32_t session,uint16_t sequence) {
  out[0]='B';out[1]='D';out[2]=1;out[3]=(uint8_t)kind;
  for(unsigned i=0;i<4;++i)out[4+i]=(uint8_t)(session>>(8*i));
  out[8]=(uint8_t)sequence;out[9]=(uint8_t)(sequence>>8);
}

bool Bell103DataLink::queue(const uint8_t* text,size_t length) {
  if(!session_||awaitingAck_||failed_||!text||!length||length>MAX_TEXT)return false;
  memcpy(text_,text,length);textLength_=length;awaitingAck_=pendingData_=true;
  attempts_=0;return true;
}

bool Bell103DataLink::next(uint32_t now,uint8_t* burst,size_t capacity,size_t& length,
                           Bell103DataKind& kind) {
  length=0;
  if(!session_||!burst)return false;
  if(pendingAcks_){
    if(capacity<HEADER_BYTES)return false;
    header(burst,Bell103DataKind::Ack,session_,ackSequence_);
    kind=Bell103DataKind::Ack;length=HEADER_BYTES;return true;
  }
  if(!awaitingAck_||failed_)return false;
  if(!pendingData_&&(uint32_t)(now-lastSent_)<RETRY_MS)return false;
  if(attempts_>=MAX_ATTEMPTS){failed_=true;return false;}
  if(capacity<HEADER_BYTES+textLength_)return false;
  header(burst,Bell103DataKind::Data,session_,txSequence_);
  memcpy(burst+HEADER_BYTES,text_,textLength_);
  kind=Bell103DataKind::Data;length=HEADER_BYTES+textLength_;return true;
}

void Bell103DataLink::sent(Bell103DataKind kind,uint32_t now) {
  if(kind==Bell103DataKind::Ack){if(pendingAcks_)--pendingAcks_;return;}
  if(kind==Bell103DataKind::Data&&awaitingAck_){
    pendingData_=false;lastSent_=now;++attempts_;
  }
}

bool Bell103DataLink::received(const uint8_t* burst,size_t length,uint8_t* text,
                               size_t capacity,size_t& textLength) {
  textLength=0;
  if(!session_||!burst||length<HEADER_BYTES||burst[0]!='B'||burst[1]!='D'||burst[2]!=1)return false;
  uint32_t session=0;
  for(unsigned i=0;i<4;++i)session|=(uint32_t)burst[4+i]<<(8*i);
  if(session!=session_)return false;
  uint16_t sequence=(uint16_t)burst[8]|((uint16_t)burst[9]<<8);
  if(burst[3]==(uint8_t)Bell103DataKind::Ack){
    if(length==HEADER_BYTES&&awaitingAck_&&sequence==txSequence_){
      awaitingAck_=pendingData_=false;failed_=false;++txSequence_;
    }
    return false;
  }
  if(burst[3]!=(uint8_t)Bell103DataKind::Data||length==HEADER_BYTES||
     length>HEADER_BYTES+MAX_TEXT)return false;
  if(sequence==rxSequence_){
    size_t n=length-HEADER_BYTES;
    if(!text||n>capacity)return false;
    memcpy(text,burst+HEADER_BYTES,n);textLength=n;
    ackSequence_=sequence;pendingAcks_=2;++rxSequence_;return true;
  }
  if(sequence==(uint16_t)(rxSequence_-1)){
    ackSequence_=sequence;pendingAcks_=2;
  }
  return false;
}
