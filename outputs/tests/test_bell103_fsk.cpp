#include "../AtomS3R_AfskRx/Bell103Fsk.h"

#include <assert.h>
#include <string.h>
#include <vector>

static void roundTrip(Bell103Role sender,Bell103Role receiver,size_t lead) {
  const uint8_t message[]={'H','E','L','L','O',' ','3','0','0'};
  Bell103FskTx tx;
  assert(tx.begin(message,sizeof(message),sender));
  std::vector<int16_t> pcm(lead,0);
  int32_t block[257*2];
  while(!tx.finished()){
    size_t count=tx.render(block,257);
    assert(count>0);
    for(size_t i=0;i<count;++i)pcm.push_back((int16_t)(block[2*i]>>16));
  }
  pcm.insert(pcm.end(),4800,0);
  Bell103FskRx rx;
  uint8_t decoded[80];size_t length=0;
  assert(rx.decode(pcm.data(),pcm.size(),receiver,decoded,sizeof(decoded),length));
  assert(length==sizeof(message)&&!memcmp(decoded,message,length));
}

int main() {
  roundTrip(Bell103Role::Originate,Bell103Role::Answer,0);
  roundTrip(Bell103Role::Originate,Bell103Role::Answer,37);
  roundTrip(Bell103Role::Answer,Bell103Role::Originate,91);
}
