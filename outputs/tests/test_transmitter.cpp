#include "../AtomS3R_AfskRx/Ax25Frame.h"
#include "../AtomS3R_AfskRx/AfskTransmitter.h"
#include "../AtomS3R_AfskRx/AfskDecoder.h"
#include <vector>
#include <cstdio>
#include <cstring>

static std::vector<int16_t> pcm;
static std::vector<uint8_t> expected;
static unsigned received=0;

static bool collect(const int32_t* stereo,size_t frames,void*) {
  for (size_t k=0;k<frames;++k) {
    if (stereo[k*2]!=stereo[k*2+1]) return false;
    pcm.push_back((int16_t)(stereo[k*2]>>16));
  }
  return true;
}

static void accept(const uint8_t* frame,size_t length,size_t) {
  if (std::vector<uint8_t>(frame,frame+length)!=expected) {
    std::puts("FAIL: decoded TX frame mismatch");
    return;
  }
  ++received;
}

int main() {
  const char* text="HELLO FROM ATOM";
  uint8_t frame[256]; size_t length=0;
  if (!Ax25Frame::makeUi(frame,sizeof(frame),length,"ATOMB",0,"ATOMA",0,
                         (const uint8_t*)text,strlen(text))) return 1;
  expected.assign(frame,frame+length);
  Ax25View view;
  if (!Ax25Frame::parse(frame,length,view) || strcmp(view.source,"ATOMA") ||
      strcmp(view.destination,"ATOMB") || view.control!=3 || view.pid!=0xf0 ||
      view.informationLength!=strlen(text) || memcmp(view.information,text,strlen(text))) return 1;
  AfskTransmitter tx;
  if (!tx.transmit(frame,length,collect,nullptr)) return 1;
  std::vector<float> scratch(pcm.size());
  AfskDecoder rx;
  rx.decode(pcm.data(),pcm.size(),1,scratch.data(),accept);
  if (received!=1) { std::printf("FAIL: received=%u\n",received); return 1; }
  size_t minimum=(40+4)*8*40+(length+2)*8*40;
  if (pcm.size()<minimum || pcm.size()>minimum+64*40) return 1;
  std::puts("PASS: AX.25 UI build/parse, FCS, HDLC flags, stuffing, NRZI, streaming Bell 202 and RX round-trip");
  return 0;
}
