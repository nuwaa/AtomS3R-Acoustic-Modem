#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>

// Wire envelope reserved for future multi-node acoustic chat.
// Direct two-node mode continues to carry the existing plain UTF-8 payload.
class GroupChatProtocol {
 public:
  static constexpr uint8_t VERSION=1;
  static constexpr uint8_t TYPE_DATA=1;
  static constexpr uint8_t TYPE_NACK=2;
  static constexpr uint8_t TYPE_SUMMARY=3;
  static constexpr size_t NAME_SIZE=6;
  static constexpr size_t HEADER_SIZE=22;
  static constexpr size_t MAX_TEXT=220-HEADER_SIZE;
  struct Message {
    uint8_t type=0;
    uint32_t id=0;
    char source[NAME_SIZE+1]={};
    char group[NAME_SIZE+1]={};
    const uint8_t* text=nullptr;
    size_t textLength=0;
  };

  void configure(const char* local,const char* group){copyName(local_,local);copyName(group_,group);}
  const char* local()const{return local_;}
  const char* group()const{return group_;}
  void setMessageSeed(uint32_t seed){nextId_=seed?seed:1;}
  uint32_t nextId(){if(++nextId_==0)++nextId_;return nextId_;}

  bool encodeData(uint8_t* output,size_t capacity,size_t& length,uint32_t id,const uint8_t* text,size_t textLength)const{
    if(!output||!text||!textLength||textLength>MAX_TEXT||capacity<HEADER_SIZE+textLength)return false;
    encodeHeader(output,TYPE_DATA,id,local_,group_,(uint16_t)textLength);
    memcpy(output+HEADER_SIZE,text,textLength);length=HEADER_SIZE+textLength;return true;
  }
  bool encodeNack(uint8_t* output,size_t capacity,size_t& length,const char* missingSource,uint32_t missingId)const{
    if(!output||!missingSource||capacity<HEADER_SIZE+NAME_SIZE)return false;
    encodeHeader(output,TYPE_NACK,missingId,local_,group_,NAME_SIZE);
    writeName(output+HEADER_SIZE,missingSource);length=HEADER_SIZE+NAME_SIZE;return true;
  }
  bool encodeSummary(uint8_t* output,size_t capacity,size_t& length,uint32_t firstRetainedId,uint32_t latestId)const{
    if(!output||capacity<HEADER_SIZE+4||firstRetainedId>latestId)return false;
    encodeHeader(output,TYPE_SUMMARY,latestId,local_,group_,4);
    write32(output+HEADER_SIZE,firstRetainedId);length=HEADER_SIZE+4;return true;
  }
  bool decode(const uint8_t* input,size_t length,Message& message)const{
    if(!input||length<HEADER_SIZE||input[0]!='G'||input[1]!='C'||input[2]!=VERSION)return false;
    uint16_t textLength=(uint16_t)input[20]|((uint16_t)input[21]<<8);
    if(length!=HEADER_SIZE+textLength)return false;
    message.type=input[3];message.id=read32(input+4);readName(message.source,input+8);readName(message.group,input+14);
    message.text=input+HEADER_SIZE;message.textLength=textLength;
    return (message.type==TYPE_DATA&&textLength>0&&textLength<=MAX_TEXT)||
           (message.type==TYPE_NACK&&textLength==NAME_SIZE)||
           (message.type==TYPE_SUMMARY&&textLength==4&&read32(message.text)<=message.id);
  }
  bool isDuplicate(const Message& message){
    uint32_t sourceHash=hashName(message.source);
    for(size_t i=0;i<CACHE_SIZE;++i)if(cache_[i].sourceHash==sourceHash&&cache_[i].id==message.id)return true;
    cache_[cachePosition_]={sourceHash,message.id};cachePosition_=(cachePosition_+1)%CACHE_SIZE;return false;
  }

 private:
  static constexpr size_t CACHE_SIZE=16;
  struct Seen {uint32_t sourceHash=0,id=0;};
  char local_[NAME_SIZE+1]="ATOMA",group_[NAME_SIZE+1]="CHAT";
  uint32_t nextId_=0;Seen cache_[CACHE_SIZE];size_t cachePosition_=0;
  static void copyName(char* destination,const char* source){memset(destination,0,NAME_SIZE+1);if(source)strncpy(destination,source,NAME_SIZE);}
  static void writeName(uint8_t* destination,const char* source){memset(destination,' ',NAME_SIZE);if(source)for(size_t i=0;i<NAME_SIZE&&source[i];++i)destination[i]=(uint8_t)source[i];}
  static void readName(char* destination,const uint8_t* source){memcpy(destination,source,NAME_SIZE);destination[NAME_SIZE]=0;for(int i=NAME_SIZE-1;i>=0&&destination[i]==' ';--i)destination[i]=0;}
  static void write32(uint8_t* p,uint32_t value){p[0]=(uint8_t)value;p[1]=(uint8_t)(value>>8);p[2]=(uint8_t)(value>>16);p[3]=(uint8_t)(value>>24);}
  static uint32_t read32(const uint8_t* p){return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
  static uint32_t hashName(const char* text){uint32_t hash=2166136261u;while(text&&*text){hash^=(uint8_t)*text++;hash*=16777619u;}return hash;}
  static void encodeHeader(uint8_t* output,uint8_t type,uint32_t id,const char* source,const char* group,uint16_t textLength){
    output[0]='G';output[1]='C';output[2]=VERSION;output[3]=type;write32(output+4,id);writeName(output+8,source);writeName(output+14,group);
    output[20]=(uint8_t)textLength;output[21]=(uint8_t)(textLength>>8);
  }
};
