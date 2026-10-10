#pragma once
#include "PacketTransport.h"

class TransportRouter {
 public:
  using Forwarder=bool (*)(PacketTransport& output,const TransportPacket& packet,void* context);
  using Observer=void (*)(PacketTransport& input,const TransportPacket& packet,void* context);
  void connect(PacketTransport& left,PacketTransport& right,
               Forwarder leftToRight=nullptr,Forwarder rightToLeft=nullptr,void* forwardContext=nullptr){
    left_=&left;right_=&right;l2r_=leftToRight;r2l_=rightToLeft;forwardContext_=forwardContext;
    left_->setReceiveHandler(fromLeft,this);right_->setReceiveHandler(fromRight,this);
  }
  void setObserver(Observer observer,void* context){observer_=observer;observerContext_=context;}
 private:
  PacketTransport* left_=nullptr;PacketTransport* right_=nullptr;
  Forwarder l2r_=nullptr,r2l_=nullptr;void* forwardContext_=nullptr;
  Observer observer_=nullptr;void* observerContext_=nullptr;
  static bool direct(PacketTransport& output,const TransportPacket& packet,void*){return output.sendPacket(packet);}
  static void fromLeft(const TransportPacket& packet,void* context){
    auto* self=(TransportRouter*)context;if(self->observer_)self->observer_(*self->left_,packet,self->observerContext_);
    (self->l2r_?self->l2r_:direct)(*self->right_,packet,self->forwardContext_);
  }
  static void fromRight(const TransportPacket& packet,void* context){
    auto* self=(TransportRouter*)context;if(self->observer_)self->observer_(*self->right_,packet,self->observerContext_);
    (self->r2l_?self->r2l_:direct)(*self->left_,packet,self->forwardContext_);
  }
};
