#pragma once
#include <stdint.h>
#include <stddef.h>

struct TransportPacket {
  const uint8_t* raw;
  size_t rawLength;
  const char* source;
  const char* destination;
  uint8_t control;
  uint8_t pid;
  const uint8_t* payload;
  size_t payloadLength;
  uint64_t receivedAt;
};

class PacketTransport {
 public:
  using ReceiveHandler=void (*)(const TransportPacket&,void*);
  virtual ~PacketTransport() {}
  virtual const char* name() const=0;
  virtual void setReceiveHandler(ReceiveHandler handler,void* context)=0;
  virtual bool send(uint8_t pid,const uint8_t* payload,size_t length)=0;
  virtual bool sendPacket(const TransportPacket& packet) {
    return send(packet.pid,packet.payload,packet.payloadLength);
  }
};
