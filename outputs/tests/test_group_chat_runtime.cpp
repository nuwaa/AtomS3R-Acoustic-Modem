#include "../AtomS3R_AfskRx/GroupChatRuntime.h"
#include <assert.h>
#include <string.h>

namespace {
struct Result { uint32_t ids[8]={};size_t count=0; };
bool send(const uint8_t*,size_t,void*) {return true;}
void deliver(const char*,uint32_t id,const uint8_t*,size_t,void* context) {
  Result& result=*static_cast<Result*>(context);
  assert(result.count<8);result.ids[result.count++]=id;
}
void receive(GroupChatRuntime& runtime,GroupChatProtocol& source,uint32_t id,uint32_t now) {
  const uint8_t text[]={'x'};uint8_t wire[64];size_t size=0;
  assert(source.encodeData(wire,sizeof(wire),size,id,text,sizeof(text)));
  runtime.receive(wire,size,now);
}
}

int main() {
  GroupChatProtocol source;source.configure("ATOMA","CHAT");
  Result result;GroupChatRuntime runtime;
  runtime.configure("ATOMB","CHAT",send,deliver,&result);runtime.enable(true,0);
  receive(runtime,source,100,1000);
  receive(runtime,source,102,2000);
  assert(result.count==1&&result.ids[0]==100); // hold 102 while 101 is repaired
  receive(runtime,source,101,3000);
  assert(result.count==3&&result.ids[1]==101&&result.ids[2]==102);
  receive(runtime,source,102,4000);
  assert(result.count==3); // duplicate cannot reach the UI

  receive(runtime,source,104,5000);
  runtime.service(18000); // recovery window expired: release 104
  assert(result.count==4&&result.ids[3]==104);
  receive(runtime,source,103,19000);
  assert(result.count==4); // late 103 must not appear after 104

  // A summary may arrive before any DATA. Recover its latest ID while keeping
  // the following DATA eligible for ordered delivery.
  Result fresh;GroupChatRuntime joined;
  joined.configure("ATOMC","CHAT",send,deliver,&fresh);joined.enable(true,0);
  uint8_t summary[64];size_t summaryLength=0;
  assert(source.encodeSummary(summary,sizeof(summary),summaryLength,200,200));
  joined.receive(summary,summaryLength,1000);
  receive(joined,source,200,2000);
  assert(fresh.count==1&&fresh.ids[0]==200);
}
