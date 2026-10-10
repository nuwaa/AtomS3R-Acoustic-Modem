#pragma once
#include "PacketTransport.h"
#include "Ax25Frame.h"
#include "AfskTransmitter.h"
#include "StreamingAfskDecoder.h"
#include <string.h>

class AcousticAx25Transport : public PacketTransport {
 public:
  using AudioSink=AfskTransmitter::SampleSink;
  const char* name() const override { return "ax25-bell202-audio"; }
  void configure(const char* source,const char* destination) {
    strncpy(source_,source,6); source_[6]=0; strncpy(destination_,destination,6); destination_[6]=0;
  }
  const char* source() const{return source_;} const char* destination() const{return destination_;}
  void setAudioSink(AudioSink sink,void* context){sink_=sink;sinkContext_=context;}
  void setReceiveHandler(ReceiveHandler handler,void* context) override {handler_=handler;handlerContext_=context;}
  void resetReceiver(){decoder_.reset();}
  void processSamples(const int16_t* samples,size_t count,size_t stride=1) {
    decoder_.process(samples,count,stride,onDecoded,this);
  }
  bool send(uint8_t pid,const uint8_t* payload,size_t length) override {
    return sendTo(destination_,pid,payload,length);
  }
  bool sendTo(const char* destination,uint8_t pid,const uint8_t* payload,size_t length) {
    if(!sink_||!payload||!length||length>220)return false;
    uint8_t frame[256];size_t frameLength=0;
    if(!destination||!Ax25Frame::makeUi(frame,sizeof(frame),frameLength,destination,0,source_,0,payload,length,pid))return false;
    lastFrameLength_=frameLength;
    return transmitter_.transmit(frame,frameLength,sink_,sinkContext_);
  }
  size_t lastFrameLength()const{return lastFrameLength_;}
 private:
  char source_[7]="ATOMA",destination_[7]="ATOMB";
  AudioSink sink_=nullptr;void* sinkContext_=nullptr;
  ReceiveHandler handler_=nullptr;void* handlerContext_=nullptr;
  AfskTransmitter transmitter_;StreamingAfskDecoder decoder_;size_t lastFrameLength_=0;
  static void onDecoded(const uint8_t* raw,size_t length,uint64_t at,void* context) {
    auto* self=(AcousticAx25Transport*)context; if(!self->handler_)return;
    Ax25View view;if(!Ax25Frame::parse(raw,length,view))return;
    TransportPacket packet={raw,length,view.source,view.destination,view.control,view.pid,
                            view.information,view.informationLength,at};
    self->handler_(packet,self->handlerContext_);
  }
};
