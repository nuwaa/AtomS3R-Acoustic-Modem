#include "../AtomS3R_AfskRx/Ax25Frame.h"
#include "../AtomS3R_AfskRx/AfskTransmitter.h"
#include "../AtomS3R_AfskRx/StreamingAfskDecoder.h"
#include <vector>
#include <cstdio>
#include <cstring>
static std::vector<int16_t> pcm; static std::vector<uint8_t> expected; static unsigned got;
static bool sink(const int32_t* p,size_t n,void*) { for(size_t i=0;i<n;++i)pcm.push_back(p[i*2]>>16); return true; }
static void frame(const uint8_t* p,size_t n,uint64_t,void*) { if(std::vector<uint8_t>(p,p+n)==expected)++got; }
int main(){
  uint8_t f[256]; size_t n=0; const char* text="STREAMING RX TEST";
  if(!Ax25Frame::makeUi(f,sizeof(f),n,"ATOMB",0,"ATOMA",0,(const uint8_t*)text,strlen(text)))return 1;
  expected.assign(f,f+n); AfskTransmitter tx; if(!tx.transmit(f,n,sink,nullptr))return 1;
  StreamingAfskDecoder rx; size_t pos=0; const size_t chunks[]={1,17,63,256,509}; size_t ci=0;
  while(pos<pcm.size()){size_t take=chunks[ci++%5];if(take>pcm.size()-pos)take=pcm.size()-pos;rx.process(pcm.data()+pos,take,1,frame,nullptr);pos+=take;}
  if(got!=1){std::printf("FAIL got=%u\n",got);return 1;} std::puts("PASS: stateful chunked Bell 202/HDLC/AX.25 streaming decode");
}
