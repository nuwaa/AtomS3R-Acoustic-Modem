#include "../AtomS3R_AfskRx/Bell103Session.h"

#include <assert.h>

static Bell103Control transfer(Bell103Session& sender,Bell103Session& receiver,
                               Bell103Message expected,uint32_t now) {
  Bell103Control tx{},rx{};uint8_t bytes[Bell103Session::CONTROL_BYTES];
  assert(sender.action(now,tx));assert(tx.message==expected);
  assert(Bell103Session::encode(tx,bytes,sizeof(bytes)));
  assert(Bell103Session::decode(bytes,sizeof(bytes),rx));
  sender.sent(now);receiver.received(rx,now);return rx;
}

int main() {
  Bell103Session caller,answerer;
  caller.startCaller(0x12345678,0);answerer.startAnswerer();
  transfer(caller,answerer,Bell103Message::Hello,0);
  transfer(answerer,caller,Bell103Message::Ready,1000);
  transfer(caller,answerer,Bell103Message::Confirm,2000);
  assert(answerer.connected());assert(!caller.connected());
  transfer(answerer,caller,Bell103Message::Established,3000);
  assert(caller.connected()&&answerer.connected());

  // A lost ESTABLISHED is recovered by a duplicate CONFIRM.
  caller.startCaller(23,0);answerer.startAnswerer();
  transfer(caller,answerer,Bell103Message::Hello,0);
  transfer(answerer,caller,Bell103Message::Ready,1000);
  transfer(caller,answerer,Bell103Message::Confirm,2000);
  Bell103Control lost{};assert(answerer.action(3000,lost));answerer.sent(3000);
  assert(!caller.connected());
  transfer(caller,answerer,Bell103Message::Confirm,10001);
  transfer(answerer,caller,Bell103Message::Established,11000);
  assert(caller.connected()&&answerer.connected());

  // If READY is lost, the caller retries HELLO and the answerer replies again.
  caller.startCaller(24,0);answerer.startAnswerer();
  transfer(caller,answerer,Bell103Message::Hello,0);
  Bell103Control lostReady{};assert(answerer.action(1000,lostReady));
  answerer.sent(1000);
  transfer(caller,answerer,Bell103Message::Hello,8000);
  transfer(answerer,caller,Bell103Message::Ready,9000);
  transfer(caller,answerer,Bell103Message::Confirm,10000);
  transfer(answerer,caller,Bell103Message::Established,11000);
  assert(caller.connected()&&answerer.connected());

  // Wrong session, malformed control and timeout cannot establish a link.
  caller.startCaller(44,0);answerer.startAnswerer();
  caller.received({Bell103Message::Ready,45},100);
  assert(caller.state()==Bell103SessionState::WaitReady);
  uint8_t bad[Bell103Session::CONTROL_BYTES]={'B','C',1,6,44,0,0,0};
  Bell103Control parsed{};assert(!Bell103Session::decode(bad,sizeof(bad),parsed));
  for(unsigned i=0;i<Bell103Session::MAX_ATTEMPTS;++i){
    Bell103Control retry{};
    assert(caller.action(i*Bell103Session::RETRY_MS,retry));
    assert(retry.message==Bell103Message::Hello);caller.sent(i*Bell103Session::RETRY_MS);
  }
  Bell103Control none{};
  assert(!caller.action(Bell103Session::MAX_ATTEMPTS*Bell103Session::RETRY_MS,none));
  assert(caller.state()==Bell103SessionState::Idle);
}
