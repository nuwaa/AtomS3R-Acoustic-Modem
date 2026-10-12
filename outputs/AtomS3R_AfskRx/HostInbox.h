#pragma once
#include <Arduino.h>

// Normal USB CDC chat only. Acoustic ACKs are independent of this host inbox.
// Entries remain in RAM until the Android host confirms durable receipt.
class HostInbox {
 public:
  static constexpr size_t CAPACITY=16;
  static constexpr size_t MAX_PAYLOAD=1500;
  explicit HostInbox(Print& output):output_(output){}
  void begin(uint32_t session){session_=session?session:1;nextSequence_=1;head_=0;count_=0;enabled_=false;}
  bool enabled()const{return enabled_;}
  void enable(){enabled_=true;output_.printf("USB_INBOX READY SESSION=%08lX PENDING=%u\n",(unsigned long)session_,(unsigned)count_);}
  void disable(){enabled_=false;output_.println("USB_INBOX OFF");}
  bool store(const char* source,const char* destination,uint8_t pid,const uint8_t* payload,size_t length){
    if(!enabled_||!payload||!length||length>MAX_PAYLOAD)return false;
    if(count_==CAPACITY){
      output_.printf("USB_INBOX OVERFLOW SESSION=%08lX DROPPED=%lu\n",(unsigned long)session_,
                     (unsigned long)entries_[head_].sequence);
      head_=(head_+1)%CAPACITY;--count_;
    }
    Entry& entry=entries_[(head_+count_)%CAPACITY];
    entry.sequence=nextSequence_++;entry.acknowledged=false;entry.pid=pid;entry.length=length;
    copyCall(entry.source,source);copyCall(entry.destination,destination);
    memcpy(entry.payload,payload,length);++count_;emit(entry);return true;
  }
  void pull(){if(!enabled_)return;for(size_t i=0;i<count_;++i){const Entry& entry=entries_[(head_+i)%CAPACITY];if(!entry.acknowledged)emit(entry);}}
  bool acknowledge(uint32_t session,uint32_t sequence){
    if(!enabled_||session!=session_)return false;
    bool found=false;
    for(size_t i=0;i<count_;++i){Entry& entry=entries_[(head_+i)%CAPACITY];if(entry.sequence==sequence){entry.acknowledged=true;found=true;break;}}
    while(count_&&entries_[head_].acknowledged){head_=(head_+1)%CAPACITY;--count_;}
    return found;
  }
 private:
  struct Entry {uint32_t sequence=0;bool acknowledged=false;uint8_t pid=0;size_t length=0;char source[7]={};char destination[7]={};uint8_t payload[MAX_PAYLOAD]={};};
  Print& output_;Entry entries_[CAPACITY];uint32_t session_=0,nextSequence_=1;size_t head_=0,count_=0;bool enabled_=false;
  static void copyCall(char (&target)[7],const char* source){size_t i=0;for(;source&&source[i]&&i<6;++i)target[i]=source[i];target[i]=0;}
  void emit(const Entry& entry){
    output_.printf("USB_INBOX SESSION=%08lX SEQ=%lu SRC=%s DEST=%s PID=%02X HEX=",
                   (unsigned long)session_,(unsigned long)entry.sequence,entry.source,entry.destination,entry.pid);
    for(size_t i=0;i<entry.length;++i){if(entry.payload[i]<16)output_.print('0');output_.print(entry.payload[i],HEX);}
    output_.println();
  }
};
