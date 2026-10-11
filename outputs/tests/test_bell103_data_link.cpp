#include "../AtomS3R_AfskRx/Bell103DataLink.h"
#include <assert.h>
#include <string.h>

int main() {
  Bell103DataLink a,b;a.begin(99);b.begin(99);
  const uint8_t message[]={'H','E','L','L','O'};
  uint8_t frame[80],ack[80],text[70];size_t frameLength=0,ackLength=0,textLength=0;
  Bell103DataKind kind=Bell103DataKind::Ack;
  assert(a.queue(message,sizeof(message)));
  assert(a.next(0,frame,sizeof(frame),frameLength,kind));
  assert(kind==Bell103DataKind::Data);a.sent(kind,0);
  assert(b.received(frame,frameLength,text,sizeof(text),textLength));
  assert(textLength==sizeof(message)&&!memcmp(text,message,sizeof(message)));
  // A duplicate does not reach the UI but must trigger another ACK.
  assert(!b.received(frame,frameLength,text,sizeof(text),textLength));
  assert(textLength==0);
  assert(b.next(1,ack,sizeof(ack),ackLength,kind));
  assert(kind==Bell103DataKind::Ack);b.sent(kind,1);
  assert(!a.received(ack,ackLength,text,sizeof(text),textLength));
  assert(!a.awaitingAck()&&a.pendingSequence()==2);

  // Lost ACK: exactly the same sequence is retransmitted after the timeout.
  assert(a.queue(message,sizeof(message)));
  assert(a.next(2,frame,sizeof(frame),frameLength,kind));a.sent(kind,2);
  assert(b.received(frame,frameLength,text,sizeof(text),textLength));
  assert(!a.next(2+Bell103DataLink::RETRY_MS-1,ack,sizeof(ack),ackLength,kind));
  assert(a.next(2+Bell103DataLink::RETRY_MS,frame,sizeof(frame),frameLength,kind));
  assert(kind==Bell103DataKind::Data);a.sent(kind,2+Bell103DataLink::RETRY_MS);
  assert(!b.received(frame,frameLength,text,sizeof(text),textLength));
  assert(textLength==0);
  assert(b.next(3,ack,sizeof(ack),ackLength,kind));b.sent(kind,3);
  assert(!a.received(ack,ackLength,text,sizeof(text),textLength));
  assert(!a.awaitingAck());

  // A frame from another connection cannot deliver text or clear an ACK wait.
  assert(a.queue(message,sizeof(message)));
  assert(a.next(0,frame,sizeof(frame),frameLength,kind));a.sent(kind,0);
  frame[4]^=1;
  assert(!b.received(frame,frameLength,text,sizeof(text),textLength));
  assert(textLength==0);
}
