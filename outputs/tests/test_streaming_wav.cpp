#include "../AtomS3R_AfskRx/StreamingAfskDecoder.h"
#include <vector>
#include <cstdio>
#include <cstdint>
static unsigned got;
static void frame(const uint8_t*,size_t n,uint64_t at,void*){++got;std::printf("frame len=%u at=%llu\n",(unsigned)n,(unsigned long long)at);}
int main(int argc,char** argv){
  if(argc!=2)return 2; FILE* f=fopen(argv[1],"rb");if(!f)return 2;fseek(f,44,SEEK_SET);
  std::vector<int16_t> pcm;int16_t x;while(fread(&x,2,1,f)==1)pcm.push_back(x);fclose(f);
  StreamingAfskDecoder rx;for(size_t p=0;p<pcm.size();){size_t n=256;if(n>pcm.size()-p)n=pcm.size()-p;rx.process(&pcm[p],n,1,frame,nullptr);p+=n;}
  std::printf("frames=%u winning_lane=%u\n",got,(unsigned)rx.winningLane());return got?0:1;
}
