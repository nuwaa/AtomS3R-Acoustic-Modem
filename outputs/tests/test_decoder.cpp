// Native test of the actual sketch decoder. g++ -O2 -std=c++11 test_decoder.cpp -o test_decoder
#include "../AtomS3R_AfskRx/AfskDecoder.h"
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <algorithm>

static std::vector<uint8_t> expected;
static unsigned received;
static void accept(const uint8_t* p, size_t n, size_t) {
  if (std::vector<uint8_t>(p,p+n) != expected) { std::puts("wrong frame"); std::exit(1); }
  ++received;
}
static std::vector<int> hdlc(bool corrupt=false, bool closing=true) {
  std::vector<uint8_t> p = expected;
  uint16_t c = AfskDecoder::crc(p.data(),p.size()) ^ 0xffff;
  p.push_back(c & 255); p.push_back(c >> 8);
  if (corrupt) p[16] ^= 1;
  std::vector<int> bits;
  auto flag = [&]() { for(int k=0;k<8;++k) bits.push_back((0x7e>>k)&1); };
  for(int k=0;k<35;++k) flag();
  int ones=0;
  for(uint8_t b:p) for(int k=0;k<8;++k) {
    int v=(b>>k)&1; bits.push_back(v);
    ones=v?ones+1:0;
    if(ones==5) { bits.push_back(0); ones=0; }
  }
  if(closing) for(int k=0;k<4;++k) flag();
  return bits;
}
static std::vector<int16_t> modulate(const std::vector<int>& bits, double baud, double offset, bool noisy, double spaceGain=1.0) {
  std::vector<int> tones;
  int tone=0;
  for(int bit:bits) { if(!bit) tone^=1; tones.push_back(tone); }
  std::vector<int16_t> pcm(144000,0);
  double phase=0;
  uint32_t seed=17;
  size_t begin=7313;
  for(size_t i=begin;i<pcm.size();++i) {
    size_t symbol=(size_t)((i-begin)*baud/48000.0);
    if(symbol>=tones.size()) break;
    double frequency=(tones[symbol]?2200:1200)+offset;
    phase += 6.283185307179586*frequency/48000.0;
    seed=1664525*seed+1013904223;
    double noise=noisy ? ((int)(seed>>16)-32768)*0.04 : 0;
    pcm[i]=(int16_t)(9000*(tones[symbol]?spaceGain:1.0)*sin(phase)+900+noise);
  }
  return pcm;
}
static void printPacket(const uint8_t* p,size_t n,size_t) {
  ++received;
  std::printf("CRC OK len=%u: ",(unsigned)n);
  for(size_t k=0;k<n;++k) std::printf("%02X%s",p[k],k+1==n?"\n":" ");
}
int main(int argc,char** argv) {
  if(argc==2) {
    std::FILE* file=std::fopen(argv[1],"rb");
    if(!file) return 2;
    std::fseek(file,0,SEEK_END);long bytes=std::ftell(file);std::rewind(file);
    if(bytes<0 || bytes%2) { std::fclose(file);return 2; }
    std::vector<int16_t> pcm((size_t)bytes/2);
    size_t got=std::fread(pcm.data(),2,pcm.size(),file);std::fclose(file);
    if(got!=pcm.size()) return 2;
    std::vector<float> scratch(pcm.size());AfskDecoder d;
    d.decode(pcm.data(),pcm.size(),1,scratch.data(),printPacket);
    return received?0:1;
  }
  const uint8_t check[]={'1','2','3','4','5','6','7','8','9'};
  if((AfskDecoder::crc(check,9)^0xffff)!=0x906e) return 1;
  expected={0x82,0xa0,0xa4,0xa6,0x40,0x40,0x60,0x9c,0x60,0x86,0x82,0x98,0x98,0x61,0x03,0xf0};
  for(int k=0;k<180;++k) expected.push_back(k%3 ? (uint8_t)k : 0xff);
  AfskDecoder d;
  std::vector<float> scratch(144000);
  for(double baud: {1196.4,1200.0,1203.6}) {
    auto pcm=modulate(hdlc(),baud,7,true);
    received=0; d.reset();
    d.decode(pcm.data(),pcm.size(),1,scratch.data(),accept);
    d.decode(pcm.data(),pcm.size(),1,scratch.data(),accept); // duplicate I2S slot
    if(received!=1) { std::printf("FAIL baud=%f count=%u\n",baud,received); return 1; }
  }
  // Unequal tone levels exercise the short-window least-squares fallback.
  {
    auto pcm=modulate(hdlc(),1200,0,false,0.5);
    received=0; d.reset();
    d.decode(pcm.data(),pcm.size(),1,scratch.data(),accept);
    if(received!=1) { std::puts("FAIL unequal tone levels"); return 1; }
  }
  for(int mode=0;mode<3;++mode) {
    auto pcm=modulate(hdlc(mode==0,mode!=1),1200,0,false);
    if(mode==2) std::fill(pcm.begin(),pcm.end(),0);
    received=0; d.reset();
    d.decode(pcm.data(),pcm.size(),1,scratch.data(),accept);
    if(received) { std::puts("FAIL negative test"); return 1; }
  }
  expected.resize(16);
  expected.push_back('X');
  auto bits=hdlc();
  auto second=hdlc();
  bits.insert(bits.end(),second.begin(),second.end());
  auto repeated=modulate(bits,1200,0,false);
  received=0; d.reset();
  d.decode(repeated.data(),repeated.size(),1,scratch.data(),accept);
  if(received!=2) { std::puts("FAIL repeated transmissions"); return 1; }
  uint32_t seed=7;
  for(auto& sample:repeated) { seed=1664525*seed+1013904223; sample=(int16_t)((int)(seed>>16)-32768); }
  received=0; d.reset();
  d.decode(repeated.data(),repeated.size(),1,scratch.data(),accept);
  if(received) { std::puts("FAIL noise only, unequal tone levels"); return 1; }
  std::puts("PASS: CRC vector, AFSK, baud offsets, noise, stuffing, dedup, bad CRC, truncation, silence, repeats, noise only, unequal tone levels");
}
