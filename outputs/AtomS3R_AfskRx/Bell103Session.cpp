#include "Bell103Session.h"

namespace {
constexpr uint8_t MAGIC[3]={'B','C',1};
}

void Bell103Session::queue(Bell103Message message) {
  pending_=true;pendingMessage_=message;
}

void Bell103Session::reset() {
  state_=Bell103SessionState::Idle;caller_=false;session_=0;
  lastTx_=0;attempts_=0;pending_=false;
}

void Bell103Session::startCaller(uint32_t session,uint32_t now) {
  reset();caller_=true;session_=session?session:1;
  state_=Bell103SessionState::WaitReady;lastTx_=now;queue(Bell103Message::Hello);
}

void Bell103Session::startAnswerer() { reset(); }

bool Bell103Session::action(uint32_t now,Bell103Control& outgoing) {
  if(!pending_ && state_!=Bell103SessionState::Idle &&
     state_!=Bell103SessionState::Connected &&
     (uint32_t)(now-lastTx_)>=RETRY_MS) {
    if(attempts_>=MAX_ATTEMPTS){reset();return false;}
    queue(state_==Bell103SessionState::WaitReady?Bell103Message::Hello:
          state_==Bell103SessionState::WaitConfirm?Bell103Message::Ready:
          Bell103Message::Confirm);
  }
  if(!pending_)return false;
  outgoing={pendingMessage_,session_};return true;
}

void Bell103Session::sent(uint32_t now) {
  if(!pending_)return;
  pending_=false;lastTx_=now;++attempts_;
}

void Bell103Session::received(const Bell103Control& incoming,uint32_t now) {
  if(!incoming.session)return;
  if(state_==Bell103SessionState::Idle && !caller_ &&
     incoming.message==Bell103Message::Hello) {
    session_=incoming.session;state_=Bell103SessionState::WaitConfirm;
    attempts_=0;lastTx_=now;queue(Bell103Message::Ready);return;
  }
  if(incoming.session!=session_)return;
  if(caller_ && state_==Bell103SessionState::WaitReady &&
     incoming.message==Bell103Message::Ready) {
    state_=Bell103SessionState::WaitEstablished;
    attempts_=0;lastTx_=now;queue(Bell103Message::Confirm);return;
  }
  if(!caller_ && state_==Bell103SessionState::WaitConfirm &&
     incoming.message==Bell103Message::Confirm) {
    state_=Bell103SessionState::Connected;pending_=false;
    queue(Bell103Message::Established);return;
  }
  // Lost reply recovery: duplicate request receives the same reply.
  if(!caller_ && state_==Bell103SessionState::WaitConfirm &&
     incoming.message==Bell103Message::Hello){queue(Bell103Message::Ready);return;}
  if(!caller_ && state_==Bell103SessionState::Connected &&
     incoming.message==Bell103Message::Confirm){queue(Bell103Message::Established);return;}
  if(caller_ && state_==Bell103SessionState::WaitEstablished &&
     incoming.message==Bell103Message::Established) {
    state_=Bell103SessionState::Connected;pending_=false;return;
  }
  if(incoming.message==Bell103Message::Bye)reset();
}

bool Bell103Session::encode(const Bell103Control& control,uint8_t* out,size_t capacity) {
  if(!out||capacity<CONTROL_BYTES||!control.session||
     (uint8_t)control.message<1||(uint8_t)control.message>5)return false;
  out[0]=MAGIC[0];out[1]=MAGIC[1];out[2]=MAGIC[2];out[3]=(uint8_t)control.message;
  for(unsigned i=0;i<4;++i)out[4+i]=(uint8_t)(control.session>>(8*i));
  return true;
}

bool Bell103Session::decode(const uint8_t* bytes,size_t length,Bell103Control& out) {
  if(!bytes||length!=CONTROL_BYTES||bytes[0]!=MAGIC[0]||
     bytes[1]!=MAGIC[1]||bytes[2]!=MAGIC[2]||bytes[3]<1||bytes[3]>5)return false;
  uint32_t session=0;
  for(unsigned i=0;i<4;++i)session|=(uint32_t)bytes[4+i]<<(8*i);
  if(!session)return false;
  out={(Bell103Message)bytes[3],session};return true;
}
