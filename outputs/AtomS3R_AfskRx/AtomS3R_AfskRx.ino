#include <Arduino.h>
#include <Wire.h>
#include <ESP_I2S.h>
#include <es8311.h> // M5Atomic-EchoBase 1.0.2
#include <esp_heap_caps.h>
#include <esp_system.h>
#include <M5GFX.h>
#include <Preferences.h>
#include "AfskDecoder.h"
#include "Ax25Frame.h"
#include "AcousticAx25Transport.h"
#include "UsbCdcTransport.h"
#include "SlipCdcTransport.h"
#include "PppCdcTransport.h"
#include "TransportRouter.h"
#include "ReliablePacketLink.h"
#include "GroupChatProtocol.h"
#include "GroupChatRuntime.h"
#include "AcousticMode.h"
#include "Bell103Overture.h"
#include "Bell103Fsk.h"
#include "Bell103Session.h"
#include "Bell103DataLink.h"

constexpr size_t SAMPLE_RATE = 48000;
constexpr size_t SAMPLES = SAMPLE_RATE * 3;
I2SClass audio;
es8311_handle_t codec = nullptr;
int16_t* pcm = nullptr; // interleaved I2S slots, NOT 96000 Hz mono
float* discriminator = nullptr;
AfskDecoder decoder;
AcousticAx25Transport acousticTransport;
UsbCdcTransport usbTransport(Serial);
SlipCdcTransport slipTransport(Serial);
PppCdcTransport pppTransport(Serial);
PacketTransport* hostTransport=&usbTransport;
TransportRouter transportRouter;
ReliablePacketLink reliableLink;
GroupChatProtocol groupChat;
GroupChatRuntime groupRuntime;
unsigned frames = 0;
bool haveRecording = false;
M5GFX display;
bool displayReady = false;
char commandLine[3072];
size_t commandLength = 0;
Preferences preferences;
char localCall[7]="ATOMA",remoteCall[7]="ATOMB";
bool liveRx=false;
bool monitorMode=false; // Receive-only; never acknowledge or retransmit overheard packets.
bool slipMode=false;
bool pppMode=false;
enum class BootMode:uint8_t { Normal,Slip,Ppp };
BootMode bootMode=BootMode::Normal;
AcousticMode acousticMode=AcousticMode::Ax25;
Bell103Overture bell103Overture;
Bell103FskTx bell103Tx;
Bell103FskRx bell103Rx;
Bell103Session bell103Session;
Bell103DataLink bell103Data;
Bell103Role bell103SessionRole=Bell103Role::Originate;
uint32_t liveMaxProcessUs=0;
size_t liveBlocks=0;
int32_t liveBlock[256*2];
int16_t liveMono[256];

void startLiveReceiver();
void stopLiveReceiver(bool report=true);
void serviceLiveReceiver();
bool audioSink(const int32_t* samples,size_t count,void* context);
bool sendPayload(uint8_t pid,const uint8_t* payload,size_t length);
bool forwardUsbToAcoustic(PacketTransport& output,const TransportPacket& packet,void* context);
bool forwardAcousticToUsb(PacketTransport& output,const TransportPacket& packet,void* context);
void observeTransport(PacketTransport& input,const TransportPacket& packet,void* context);
bool reliableSend(uint8_t pid,const uint8_t* payload,size_t length,void* context);
bool groupSend(const uint8_t* payload,size_t length,void* context);
void groupDelivery(const char* source,uint32_t id,const uint8_t* text,size_t length,void* context);
void reliableDelivery(uint8_t pid,const uint8_t* payload,size_t length,void* context);
void reliableStatus(const char* state,uint16_t id,uint8_t current,uint8_t total,void* context);
const char* bootModeName(BootMode mode);
bool parseBootMode(const char* text,BootMode& mode);
void activateHostMode(BootMode mode);
bool binaryHostMode();
bool playBell103Overture();
bool bell103SendDiagnostic(const uint8_t* text,size_t length,Bell103Role role);
bool bell103ReceiveDiagnostic(Bell103Role role);
bool bell103SelfTest();
bool bell103SessionSelfTest();
bool bell103DataSelfTest();
bool bell103SendBurst(const uint8_t* payload,size_t length,Bell103Role role);
bool bell103ReceiveBurst(Bell103Role role,uint8_t* payload,size_t capacity,size_t& length);
void bell103SessionCommand(const char* command);
void bell103DataCommand(const char* command,size_t length);

bool writeRegister(uint8_t address,uint8_t reg,uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg); Wire.write(value);
  return Wire.endTransmission()==0;
}

bool speakerEnable(bool enabled) {
  if (enabled) {
    if (!writeRegister(0x43,0x07,0x00) || !writeRegister(0x43,0x0d,0xff) ||
        !writeRegister(0x43,0x03,0x6f) || !writeRegister(0x43,0x05,0xff)) return false;
    return es8311_voice_volume_set(codec,50,nullptr)==ESP_OK && es8311_voice_mute(codec,false)==ESP_OK;
  }
  bool ok=es8311_voice_mute(codec,true)==ESP_OK;
  return writeRegister(0x43,0x05,0x00) && ok;
}

void screenStatus(const char* status) {
  if (!displayReady) return;
  display.fillRect(0,0,128,20,TFT_BLACK);
  display.setFont(&fonts::Font0);
  display.setTextSize(1);
  display.setTextColor(TFT_GREEN,TFT_BLACK);
  display.setCursor(4,4);
  display.print(status);
}

bool traditionalChineseHint(uint32_t cp) {
  // Characters whose modern Japanese forms differ from Traditional Chinese.
  // Common Han characters are rendered with the Japanese font by default so
  // Japanese place/person names containing kanji only do not become tofu.
  switch(cp) {
    case 0x570B: // 國
    case 0x5B78: // 學
    case 0x5EE3: // 廣
    case 0x7063: // 灣
    case 0x81FA: // 臺
    case 0x842C: // 萬
    case 0x865F: // 號
    case 0x9AD4: // 體
      return true;
    default:
      return false;
  }
}

void screenText(const uint8_t* text, size_t length) {
  if (!displayReady) return;
  display.fillRect(0,20,128,108,TFT_BLACK);
  display.setTextColor(TFT_WHITE,TFT_BLACK);
  display.setTextSize(1);
  display.setTextWrap(true,true);
  display.setCursor(2,24);
  for(size_t pos=0;pos<length;){
    size_t start=pos;
    uint32_t cp=text[pos++];
    if((cp&0xe0)==0xc0 && pos<length)cp=((cp&0x1f)<<6)|(text[pos++]&0x3f);
    else if((cp&0xf0)==0xe0 && pos+1<length){cp=((cp&0x0f)<<12)|((text[pos]&0x3f)<<6)|(text[pos+1]&0x3f);pos+=2;}
    else if((cp&0xf8)==0xf0 && pos+2<length){cp=((cp&7)<<18)|((text[pos]&0x3f)<<12)|((text[pos+1]&0x3f)<<6)|(text[pos+2]&0x3f);pos+=3;}
    // efontTW covers traditional variants but lacks some Japanese kana.
    // Switch for the specific traditional glyph, then restore Japanese font
    // for the rest of a mixed Japanese/Traditional Chinese message.
    display.setFont(traditionalChineseHint(cp) ? &fonts::efontTW_16 : &fonts::efontJA_16);
    display.write(text+start,pos-start);
  }
}

void fatal(const char* message) {
  Serial.println(message);
  while (true) delay(1000);
}

bool validCall(const char* call) {
  size_t n=strlen(call); if(n<1||n>6)return false;
  for(size_t k=0;k<n;++k)if(!((call[k]>='A'&&call[k]<='Z')||(call[k]>='0'&&call[k]<='9')))return false;
  return true;
}

void configureCalls(const char* source,const char* destination) {
  if(!validCall(source)||!validCall(destination)) {
    Serial.println("ERROR: callsigns must be 1..6 uppercase A-Z/0-9 characters."); return;
  }
  strncpy(localCall,source,sizeof(localCall)); localCall[6]=0;
  strncpy(remoteCall,destination,sizeof(remoteCall)); remoteCall[6]=0;
  preferences.putString("src",localCall); preferences.putString("dst",remoteCall);
  acousticTransport.configure(localCall,remoteCall);
  usbTransport.configure(localCall,remoteCall);
  slipTransport.configure(localCall,remoteCall);
  pppTransport.configure(localCall,remoteCall);
  reliableLink.setContentionIdentity(localCall);
  groupChat.configure(localCall,"CHAT");
  groupRuntime.configure(localCall,"CHAT",groupSend,groupDelivery,nullptr);
  Serial.printf("CONFIG SRC=%s DEST=%s saved.\n",localCall,remoteCall);
  screenStatus("CONFIG SAVED");
}

const char* bootModeName(BootMode mode) {
  if(mode==BootMode::Slip)return "slip";
  if(mode==BootMode::Ppp)return "ppp";
  return "normal";
}

bool parseBootMode(const char* text,BootMode& mode) {
  if(!strcmp(text,"normal")){mode=BootMode::Normal;return true;}
  if(!strcmp(text,"slip")){mode=BootMode::Slip;return true;}
  if(!strcmp(text,"ppp")){mode=BootMode::Ppp;return true;}
  return false;
}

void activateHostMode(BootMode mode) {
  slipMode=mode==BootMode::Slip;pppMode=mode==BootMode::Ppp;
  if(slipMode){slipTransport.reset();hostTransport=&slipTransport;transportRouter.connect(slipTransport,acousticTransport,forwardUsbToAcoustic,forwardAcousticToUsb,nullptr);screenStatus("BOOT SLIP");}
  else if(pppMode){hostTransport=&pppTransport;transportRouter.connect(pppTransport,acousticTransport,forwardUsbToAcoustic,forwardAcousticToUsb,nullptr);screenStatus("BOOT PPP");pppTransport.begin();}
  else{hostTransport=&usbTransport;transportRouter.connect(usbTransport,acousticTransport,forwardUsbToAcoustic,forwardAcousticToUsb,nullptr);screenStatus("BOOT NORMAL");Serial.println("NORMAL READY command console.");}
}

bool binaryHostMode(){return slipMode||pppMode;}

void setup() {
  Serial.begin(115200);
  unsigned long start = millis();
  while (!Serial && millis()-start < 5000) delay(10);
  esp_reset_reason_t resetReason=esp_reset_reason();
  const char* resetName="OTHER";
  switch(resetReason){
    case ESP_RST_POWERON: resetName="POWERON";break;
    case ESP_RST_SW: resetName="SOFTWARE";break;
    case ESP_RST_PANIC: resetName="PANIC";break;
    case ESP_RST_INT_WDT: resetName="INT_WDT";break;
    case ESP_RST_TASK_WDT: resetName="TASK_WDT";break;
    case ESP_RST_WDT: resetName="WDT";break;
    case ESP_RST_BROWNOUT: resetName="BROWNOUT";break;
    case ESP_RST_USB: resetName="USB";break;
    case ESP_RST_PWR_GLITCH: resetName="POWER_GLITCH";break;
    case ESP_RST_CPU_LOCKUP: resetName="CPU_LOCKUP";break;
    default:break;
  }
  Serial.printf("BOOT DIAG reset_reason=%d name=%s uptime_ms=%lu\n",(int)resetReason,resetName,millis());
  displayReady=display.init();
  if (displayReady) {
    display.setRotation(0);
    display.setBrightness(128);
    display.setFont(&fonts::Font0);
    display.setTextWrap(false);
    display.fillScreen(TFT_BLACK);
    screenStatus("READY / SEND l");
    Serial.printf("Display ready: %d x %d\n",display.width(),display.height());
  } else Serial.println("WARNING: display init failed; Serial reception still available.");
  if (!psramFound()) fatal("ERROR: enable OPI PSRAM (ATOM S3R).");
  if(!preferences.begin("afsk",false))fatal("ERROR: NVS preferences.");
  String savedSource=preferences.getString("src","ATOMA");
  String savedDestination=preferences.getString("dst","ATOMB");
  if(validCall(savedSource.c_str())&&validCall(savedDestination.c_str())) {
    strncpy(localCall,savedSource.c_str(),sizeof(localCall)); localCall[6]=0;
    strncpy(remoteCall,savedDestination.c_str(),sizeof(remoteCall)); remoteCall[6]=0;
  }
  String savedBoot=preferences.getString("boot","normal");
  if(!parseBootMode(savedBoot.c_str(),bootMode)){bootMode=BootMode::Normal;preferences.remove("boot");}
  // Bell 103 is not activated until its carrier and handshake are implemented.
  // A stale or future preference must never silently replace the working AX.25 path.
  acousticMode=AcousticMode::Ax25;
  acousticTransport.configure(localCall,remoteCall);
  usbTransport.configure(localCall,remoteCall);
  slipTransport.configure(localCall,remoteCall);
  pppTransport.configure(localCall,remoteCall);
  pcm = (int16_t*)heap_caps_malloc(SAMPLES*2*sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  discriminator = (float*)heap_caps_malloc(SAMPLES*sizeof(float), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!pcm || !discriminator) fatal("ERROR: PSRAM allocation failed.");
  if (!Wire.begin(38,39,100000)) fatal("ERROR: I2C init.");
  Wire.beginTransmission(0x18);
  if (Wire.endTransmission() != 0) fatal("ERROR: ES8311 not found at 0x18. Check Echo Base.");

  // Full-duplex I2S hardware; firmware deliberately uses either TX or RX at a time.
  audio.setPins(8,6,5,7,-1); // BCLK, WS, TX, RX, MCLK
  if (!audio.begin(I2S_MODE_STD,SAMPLE_RATE,I2S_DATA_BIT_WIDTH_32BIT,I2S_SLOT_MODE_STEREO))
    fatal("ERROR: I2S init.");
  acousticTransport.setAudioSink(audioSink,nullptr);
  reliableLink.configure(reliableSend,reliableDelivery,reliableStatus,nullptr);
  reliableLink.setContentionIdentity(localCall);
  groupChat.configure(localCall,"CHAT");
  groupChat.setMessageSeed(esp_random());
  groupRuntime.configure(localCall,"CHAT",groupSend,groupDelivery,nullptr);
  groupRuntime.setSeed(esp_random()&0x7fffffffU);
  transportRouter.connect(usbTransport,acousticTransport,forwardUsbToAcoustic,forwardAcousticToUsb,nullptr);
  transportRouter.setObserver(observeTransport,nullptr);
  es8311_set_twowire(&Wire);
  codec = es8311_create(I2C_NUM_0,0x18);
  if (!codec) fatal("ERROR: codec allocation.");
  es8311_clock_config_t clock = {};
  clock.mclk_from_mclk_pin = false; // derive clock from BCLK = 48000*32*2
  clock.sample_frequency = SAMPLE_RATE;
  if (es8311_init(codec,&clock,ES8311_RESOLUTION_32,ES8311_RESOLUTION_32) != ESP_OK ||
      es8311_microphone_config(codec,false) != ESP_OK ||
      es8311_microphone_gain_set(codec,ES8311_MIC_GAIN_6DB) != ESP_OK ||
      es8311_voice_volume_set(codec,50,nullptr) != ESP_OK ||
      es8311_voice_mute(codec,true) != ESP_OK)
    fatal("ERROR: codec init.");
  if (!writeRegister(0x43,0x07,0x00) || !writeRegister(0x43,0x0d,0xff) ||
      !writeRegister(0x43,0x03,0x6f) || !writeRegister(0x43,0x05,0x00))
    fatal("ERROR: Atomic Voice Base speaker control at 0x43.");
  Serial.printf("Ready: SRC=%s DEST=%s BOOT=%s ACOUSTIC=%s; ?=help.\n",localCall,remoteCall,bootModeName(bootMode),acousticModeName(acousticMode));
  startLiveReceiver();
  activateHostMode(bootMode);
}

// Read small blocks, explicitly detecting errors/short reads. 32-bit I2S -> s16 PCM.
bool capture(size_t count, bool save) {
  int32_t block[256*2];
  for (size_t pos=0; pos<count;) {
    size_t n = count-pos;
    if (n > 256) n=256;
    size_t received=0;
    esp_err_t err = i2s_channel_read(audio.rxChan(),block,n*2*sizeof(int32_t),&received,1000);
    if (err != ESP_OK || received != n*2*sizeof(int32_t)) return false;
    if (save) for (size_t k=0; k<n*2; ++k) pcm[pos*2+k]=(int16_t)(block[k] >> 16);
    pos += n;
  }
  return true;
}

// TX and RX share the same full-duplex I2S peripheral.  While a packet is
// transmitted the RX DMA keeps collecting samples, so discard everything
// already queued before starting a new timed recording.
void prepareReceiver() {
  speakerEnable(false);
  es8311_microphone_config(codec,false);
  es8311_microphone_gain_set(codec,ES8311_MIC_GAIN_6DB);
  int32_t stale[256*2];
  size_t total=0;
  for (int pass=0;pass<64;++pass) {
    size_t received=0;
    esp_err_t err=i2s_channel_read(audio.rxChan(),stale,sizeof(stale),&received,0);
    if (err!=ESP_OK || received==0) break;
    total+=received;
    if (received<sizeof(stale)) break;
  }
  if(!binaryHostMode())Serial.printf("RX prepared: discarded %u stale byte(s).\n",(unsigned)total);
}

void handlePacket(const TransportPacket& packet) {
  ++frames;
  if(!binaryHostMode()){
    Serial.printf("AX25 CRC OK len=%u end_ms=%u transport=%s (FCS excluded):\n",
                  (unsigned)packet.rawLength,(unsigned)(packet.receivedAt*1000/SAMPLE_RATE),acousticTransport.name());
    for(size_t k=0;k<packet.rawLength;++k)Serial.printf("%02X%s",packet.raw[k],k+1==packet.rawLength?"\n":" ");
    Serial.printf("SRC=%s DEST=%s CTRL=%02X PID=%02X FCS=OK\n",packet.source,packet.destination,packet.control,packet.pid);
  }
  if((packet.control&0xef)!=0x03||packet.pid!=0xf0)return;
  if(!binaryHostMode()){
    Serial.print("TEXT: ");
    for(size_t k=0;k<packet.payloadLength;++k) {
      uint8_t c=packet.payload[k];
      if (c>=0x20 && c<=0x7E) Serial.write(c);
      else Serial.printf("\\x%02X",c);
    }
    Serial.println();
  }
  screenStatus("RX OK / FCS OK");
  screenText(packet.payload,packet.payloadLength);
}
void observeTransport(PacketTransport& input,const TransportPacket& packet,void*) {
  if(&input!=&acousticTransport)return;
  if(!monitorMode){handlePacket(packet);return;}
  Serial.printf("USB_MON_RX SRC=%s DEST=%s CTRL=%02X PID=%02X LEN=%u HEX=",
                packet.source,packet.destination,packet.control,packet.pid,(unsigned)packet.payloadLength);
  for(size_t i=0;i<packet.payloadLength;++i)Serial.printf("%02X",packet.payload[i]);
  Serial.println();
  screenStatus("MON RX / CRC OK");
}
bool forwardUsbToAcoustic(PacketTransport&,const TransportPacket& packet,void*) {
  if(monitorMode){Serial.println("ERROR: monitor mode is receive-only.");return false;}
  if(packet.pid==0xfc){
    bool ok=!reliableLink.busy()&&groupRuntime.sendText(packet.payload,packet.payloadLength,millis());
    if(!ok)Serial.println("GROUP TX FAILED (use group on; length 1..198 bytes).");
    else Serial.println("GROUP TX OK");
    return ok;
  }
  if(packet.pid==ReliablePacketLink::HOST_REQUEST_PID){
    bool ok=reliableLink.beginSend(0xf0,packet.payload,packet.payloadLength);
    if(!ok)Serial.println("RELIABLE BUSY_OR_INVALID");
    return ok;
  }
  if(packet.pid==ReliablePacketLink::HOST_REQUEST_IPV4_PID){
    bool ok=reliableLink.beginSend(0xcc,packet.payload,packet.payloadLength);
    if(!ok)Serial.println("RELIABLE BUSY_OR_INVALID");
    return ok;
  }
  if((slipMode||pppMode)&&packet.pid==0xcc){
    bool ok=reliableLink.beginSend(0xcc,packet.payload,packet.payloadLength);
    return ok;
  }
  bool resume=liveRx;stopLiveReceiver(false);Serial.println("STATE RX -> TX");
  bool ok=sendPayload(packet.pid,packet.payload,packet.payloadLength);
  if(resume){Serial.println("STATE TX -> RX");startLiveReceiver();}
  return ok;
}
bool forwardAcousticToUsb(PacketTransport& output,const TransportPacket& packet,void*) {
  if(monitorMode)return true;
  if(packet.pid==0xf1 && !strcmp(packet.destination,"CHAT")){
    if(groupRuntime.enabled()&&packet.payloadLength>=8)
      Serial.printf("GROUP WIRE RX type=%u id=%lu from=%s\n",(unsigned)packet.payload[3],
                    (unsigned long)((uint32_t)packet.payload[4]|((uint32_t)packet.payload[5]<<8)|
                                    ((uint32_t)packet.payload[6]<<16)|((uint32_t)packet.payload[7]<<24)),packet.source);
    groupRuntime.receive(packet.payload,packet.payloadLength,millis());return true;
  }
  if(packet.pid==ReliablePacketLink::WIRE_PID){reliableLink.onPacket(packet.payload,packet.payloadLength);return true;}
  return output.sendPacket(packet);
}
bool reliableSend(uint8_t pid,const uint8_t* payload,size_t length,void*) {
  if(monitorMode)return false;
  bool resume=liveRx;stopLiveReceiver(false);if(!binaryHostMode())Serial.println("STATE RX -> RELIABLE TX");
  bool ok=sendPayload(pid,payload,length);
  if(resume){if(!binaryHostMode())Serial.println("STATE RELIABLE TX -> RX");startLiveReceiver();}
  return ok;
}
bool groupSend(const uint8_t* payload,size_t length,void*) {
  if(monitorMode)return false;
  bool resume=liveRx;stopLiveReceiver(false);
  if(length>=8)Serial.printf("GROUP WIRE TX type=%u id=%lu\n",(unsigned)payload[3],
                             (unsigned long)((uint32_t)payload[4]|((uint32_t)payload[5]<<8)|
                                             ((uint32_t)payload[6]<<16)|((uint32_t)payload[7]<<24)));
  if(!speakerEnable(true)){if(resume)startLiveReceiver();return false;}
  bool ok=acousticTransport.sendTo("CHAT",0xf1,payload,length);
  int32_t silence[256*2]={};for(int k=0;k<4;++k)audioSink(silence,256,nullptr);
  ok=speakerEnable(false)&&ok;
  if(resume)startLiveReceiver();
  return ok;
}
void groupDelivery(const char* source,uint32_t id,const uint8_t* text,size_t length,void*) {
  Serial.printf("USB_GROUP_RX SRC=%s ID=%lu HEX=",source,(unsigned long)id);
  for(size_t i=0;i<length;++i)Serial.printf("%02X",text[i]);
  Serial.println();
  Serial.printf("GROUP RX %s #%lu: ",source,(unsigned long)id);
  Serial.write(text,length);Serial.println();
  screenStatus("GROUP RX / FCS OK");screenText(text,length);
}
void reliableDelivery(uint8_t pid,const uint8_t* payload,size_t length,void*) {
  TransportPacket packet={nullptr,0,remoteCall,localCall,0x03,pid,payload,length,0};
  hostTransport->sendPacket(packet);screenStatus("RX RELIABLE OK");if(pid==0xf0)screenText(payload,length);
}
void reliableStatus(const char* state,uint16_t id,uint8_t current,uint8_t total,void*) {
  if(!binaryHostMode())Serial.printf("RELIABLE %s ID=%u PART=%u/%u\n",state,(unsigned)id,(unsigned)current,(unsigned)total);
}
void printFrame(const uint8_t* raw,size_t length,size_t at) {
  Ax25View view;if(!Ax25Frame::parse(raw,length,view))return;
  TransportPacket packet={raw,length,view.source,view.destination,view.control,view.pid,
                          view.information,view.informationLength,at};
  usbTransport.sendPacket(packet);
  handlePacket(packet);
}
void cooperate() { delay(1); }

bool audioSink(const int32_t* samples,size_t count,void*) {
  size_t written=0;
  esp_err_t err=i2s_channel_write(audio.txChan(),samples,count*2*sizeof(int32_t),&written,1000);
  return err==ESP_OK && written==count*2*sizeof(int32_t);
}

bool playBell103Overture() {
  if(binaryHostMode()||monitorMode||reliableLink.busy()||groupRuntime.enabled()) {
    Serial.println("ERROR: Bell 103 tone requires normal, direct, idle mode.");
    return false;
  }
  bool resume=liveRx;
  stopLiveReceiver(false);
  screenStatus("B103 DIAL SOUND");
  Serial.println("BELL103 OVERTURE DEMO: sound only; no connection or data.");
  if(!speakerEnable(true)) {
    if(resume)startLiveReceiver();
    Serial.println("ERROR: Bell 103 speaker enable failed.");
    return false;
  }
  bell103Overture.reset();
  int32_t block[256*2];
  uint32_t maxRenderUs=0;
  unsigned long began=millis();
  bool ok=true;
  while(!bell103Overture.finished()) {
    uint32_t startUs=micros();
    size_t count=bell103Overture.render(block,256);
    uint32_t elapsed=micros()-startUs;
    if(elapsed>maxRenderUs)maxRenderUs=elapsed;
    if(!count||!audioSink(block,count,nullptr)){ok=false;break;}
  }
  int32_t silence[256*2]={};
  for(int k=0;k<4;++k)if(!audioSink(silence,256,nullptr))ok=false;
  if(!speakerEnable(false))ok=false;
  Serial.printf("BELL103 OVERTURE %s samples=%lu elapsed_ms=%lu max_render_us=%lu (demo only)\n",
                ok?"OK":"FAILED",(unsigned long)bell103Overture.position(),millis()-began,(unsigned long)maxRenderUs);
  if(resume)startLiveReceiver();
  return ok;
}

bool bell103SendBurst(const uint8_t* text,size_t length,Bell103Role role) {
  if(!bell103Tx.begin(text,length,role)) {
    Serial.println("ERROR: Bell 103 text must be 1..80 UTF-8 bytes.");return false;
  }
  bool resume=liveRx;stopLiveReceiver(false);
  screenStatus("B103 DATA TX");
  if(!speakerEnable(true)){if(resume)startLiveReceiver();return false;}
  int32_t block[256*2];bool ok=true;
  while(!bell103Tx.finished()){
    size_t count=bell103Tx.render(block,256);
    if(!count||!audioSink(block,count,nullptr)){ok=false;break;}
  }
  int32_t silence[256*2]={};
  for(int k=0;k<4;++k)if(!audioSink(silence,256,nullptr))ok=false;
  if(!speakerEnable(false))ok=false;
  Serial.printf("BELL103 DIAGNOSTIC TX %s role=%s bytes=%u bits=%u\n",ok?"OK":"FAILED",
                role==Bell103Role::Originate?"originate":"answer",(unsigned)length,(unsigned)bell103Tx.bits());
  if(resume)startLiveReceiver();
  return ok;
}

bool bell103SendDiagnostic(const uint8_t* text,size_t length,Bell103Role role) {
  if(binaryHostMode()||monitorMode||reliableLink.busy()||groupRuntime.enabled()) {
    Serial.println("ERROR: Bell 103 diagnostic requires normal, direct, idle mode.");return false;
  }
  return bell103SendBurst(text,length,role);
}

bool bell103ReceiveBurst(Bell103Role role,uint8_t* text,size_t capacity,size_t& length) {
  length=0;
  if(!text||!capacity)return false;
  constexpr size_t MAX_SAMPLES=6*SAMPLE_RATE;
  int16_t* samples=(int16_t*)heap_caps_malloc(MAX_SAMPLES*sizeof(int16_t),MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
  if(!samples){Serial.println("ERROR: Bell 103 capture allocation failed.");return false;}
  bool resume=liveRx;stopLiveReceiver(false);prepareReceiver();
  screenStatus("B103 RX 6 SEC");
  Serial.println("BELL103 REC 6 seconds -- transmit NOW");
  int32_t block[256*2];bool ok=true;
  if(!capture(12000,false))ok=false; // 250 ms warm-up
  for(size_t pos=0;ok&&pos<MAX_SAMPLES;){
    size_t count=MAX_SAMPLES-pos;if(count>256)count=256;
    size_t received=0;
    esp_err_t err=i2s_channel_read(audio.rxChan(),block,count*2*sizeof(int32_t),&received,1000);
    if(err!=ESP_OK||received!=count*2*sizeof(int32_t)){ok=false;break;}
    for(size_t i=0;i<count;++i)samples[pos+i]=(int16_t)(block[2*i]>>16);
    pos+=count;
  }
  if(ok)ok=bell103Rx.decode(samples,MAX_SAMPLES,role,text,capacity,length);
  heap_caps_free(samples);
  if(resume)startLiveReceiver();
  return ok;
}

bool bell103ReceiveDiagnostic(Bell103Role role) {
  if(binaryHostMode()||monitorMode||reliableLink.busy()||groupRuntime.enabled()) {
    Serial.println("ERROR: Bell 103 diagnostic requires normal, direct, idle mode.");return false;
  }
  uint8_t text[81];size_t length=0;
  bool ok=bell103ReceiveBurst(role,text,sizeof(text)-1,length);
  if(ok){
    text[length]=0;
    Serial.printf("BELL103 RX CRC OK LEN=%u HEX=",(unsigned)length);
    for(size_t i=0;i<length;++i)Serial.printf("%02X",text[i]);
    Serial.println();Serial.print("BELL103 TEXT: ");Serial.write(text,length);Serial.println();
    screenStatus("B103 RX CRC OK");screenText(text,length);
  }else Serial.println("BELL103 RX NO VALID FRAME");
  return ok;
}

bool bell103SelfTest() {
  if(binaryHostMode()||monitorMode||reliableLink.busy()||groupRuntime.enabled()) {
    Serial.println("ERROR: Bell 103 self-test requires normal, direct, idle mode.");return false;
  }
  bool resume=liveRx;stopLiveReceiver(false);
  const uint8_t message[]={'B','1','0','3',' ','T','E','S','T'};
  bool ok=true;
  int32_t block[256*2];uint8_t decoded[81];size_t length=0;
  for(int role=0;role<2;++role){
    Bell103Role txRole=role?Bell103Role::Answer:Bell103Role::Originate;
    Bell103Role rxRole=role?Bell103Role::Originate:Bell103Role::Answer;
    if(!bell103Tx.begin(message,sizeof(message),txRole)){ok=false;break;}
    size_t count=0;
    while(!bell103Tx.finished()){
      size_t made=bell103Tx.render(block,256);
      if(!made||count+made>SAMPLES){ok=false;break;}
      for(size_t i=0;i<made;++i)pcm[count+i]=(int16_t)(block[2*i]>>16);
      count+=made;
    }
    if(!ok||!bell103Rx.decode(pcm,count,rxRole,decoded,sizeof(decoded),length)||
       length!=sizeof(message)||memcmp(decoded,message,length)){ok=false;break;}
  }
  haveRecording=false;
  Serial.println(ok?"BELL103 SELFTEST PASS both bands CRC OK":"BELL103 SELFTEST FAILED");
  if(resume)startLiveReceiver();
  return ok;
}

bool bell103SessionSelfTest() {
  Bell103Session caller,answerer;
  constexpr uint32_t ID=0x12345678;
  caller.startCaller(ID,0);answerer.startAnswerer();
  const Bell103Message sequence[]={Bell103Message::Hello,Bell103Message::Ready,
      Bell103Message::Confirm,Bell103Message::Established};
  bool ok=true;
  for(unsigned i=0;i<4&&ok;++i){
    Bell103Session& sender=(i&1)?answerer:caller;
    Bell103Session& receiver=(i&1)?caller:answerer;
    Bell103Control outgoing{},incoming{};uint8_t bytes[Bell103Session::CONTROL_BYTES];
    ok=sender.action(i*1000,outgoing)&&outgoing.message==sequence[i]&&
       Bell103Session::encode(outgoing,bytes,sizeof(bytes))&&
       Bell103Session::decode(bytes,sizeof(bytes),incoming)&&incoming.session==ID;
    if(ok){sender.sent(i*1000);receiver.received(incoming,i*1000);}
  }
  ok=ok&&caller.connected()&&answerer.connected();
  Bell103Control stale{Bell103Message::Bye,ID+1};
  caller.received(stale,5000);ok=ok&&caller.connected();
  caller.received({Bell103Message::Bye,ID},6000);ok=ok&&!caller.connected();
  Serial.println(ok?"BELL103 SESSION SELFTEST PASS":"BELL103 SESSION SELFTEST FAILED");
  return ok;
}

bool bell103DataSelfTest() {
  Bell103DataLink a,b;a.begin(0x12345678);b.begin(0x12345678);
  const uint8_t message[]={'B','1','0','3',' ','D','A','T','A'};
  uint8_t burst[80],reply[80],delivered[70];
  size_t length=0,replyLength=0,deliveredLength=0;
  Bell103DataKind kind=Bell103DataKind::Ack;
  bool ok=a.queue(message,sizeof(message))&&
          a.next(0,burst,sizeof(burst),length,kind)&&kind==Bell103DataKind::Data;
  if(ok){
    a.sent(kind,0);
    ok=b.received(burst,length,delivered,sizeof(delivered),deliveredLength)&&
       deliveredLength==sizeof(message)&&!memcmp(delivered,message,sizeof(message));
  }
  if(ok){
    size_t duplicateLength=0;
    ok=!b.received(burst,length,delivered,sizeof(delivered),duplicateLength)&&
       duplicateLength==0&&b.next(1000,reply,sizeof(reply),replyLength,kind)&&
       kind==Bell103DataKind::Ack;
  }
  if(ok){
    b.sent(kind,1000);
    size_t none=0;
    ok=!a.received(reply,replyLength,delivered,sizeof(delivered),none)&&
       !a.awaitingAck()&&a.pendingSequence()==2;
  }
  Serial.println(ok?"BELL103 DATA SELFTEST PASS":"BELL103 DATA SELFTEST FAILED");
  return ok;
}

const char* bell103SessionStateName(Bell103SessionState state) {
  switch(state){
    case Bell103SessionState::Idle:return "idle";
    case Bell103SessionState::WaitReady:return "wait-ready";
    case Bell103SessionState::WaitConfirm:return "wait-confirm";
    case Bell103SessionState::WaitEstablished:return "wait-established";
    case Bell103SessionState::Connected:return "connected";
  }
  return "unknown";
}

void bell103SessionCommand(const char* command) {
  if(!strcmp(command,"bell103 session caller")||!strcmp(command,"bell103 session answerer")){
    if(acousticMode!=AcousticMode::Ax25||binaryHostMode()||monitorMode||
       reliableLink.busy()||groupRuntime.enabled()){
      Serial.println("ERROR: Bell 103 session requires AX.25 normal, direct, idle mode.");return;
    }
    stopLiveReceiver(false);
    acousticTransport.resetReceiver();speakerEnable(false);
    bell103Data.reset();
    bool caller=!strcmp(command,"bell103 session caller");
    bell103SessionRole=caller?Bell103Role::Originate:Bell103Role::Answer;
    if(caller)bell103Session.startCaller(esp_random(),millis());
    else bell103Session.startAnswerer();
    acousticMode=AcousticMode::Bell103;
    screenStatus(caller?"B103 CALLER":"B103 ANSWERER");
    Serial.printf("BELL103 SESSION START role=%s id=%lu state=%s\n",
                  caller?"caller":"answerer",(unsigned long)bell103Session.session(),
                  bell103SessionStateName(bell103Session.state()));
    return;
  }
  if(!strcmp(command,"bell103 session stop")){
    bell103Session.reset();bell103Data.reset();acousticMode=AcousticMode::Ax25;
    speakerEnable(false);startLiveReceiver();
    Serial.println("BELL103 SESSION STOP; ACOUSTIC MODE=ax25");return;
  }
  if(!strcmp(command,"bell103 session show")){
    Serial.printf("BELL103 SESSION mode=%s state=%s id=%lu\n",acousticModeName(acousticMode),
                  bell103SessionStateName(bell103Session.state()),
                  (unsigned long)bell103Session.session());return;
  }
  if(acousticMode!=AcousticMode::Bell103){
    Serial.println("ERROR: start bell103 session caller|answerer first.");return;
  }
  if(!strcmp(command,"bell103 session tx")){
    Bell103Control outgoing{};uint8_t bytes[Bell103Session::CONTROL_BYTES];
    if(!bell103Session.action(millis(),outgoing)){
      Serial.println("BELL103 SESSION NO TX PENDING");return;
    }
    if(!Bell103Session::encode(outgoing,bytes,sizeof(bytes))||
       !bell103SendBurst(bytes,sizeof(bytes),bell103SessionRole)){
      Serial.println("BELL103 SESSION TX FAILED");return;
    }
    bell103Session.sent(millis());
    Serial.printf("BELL103 SESSION TX type=%u id=%lu state=%s\n",
                  (unsigned)outgoing.message,(unsigned long)outgoing.session,
                  bell103SessionStateName(bell103Session.state()));return;
  }
  if(!strcmp(command,"bell103 session rx")){
    uint8_t bytes[81];size_t length=0;Bell103Control incoming{};
    if(!bell103ReceiveBurst(bell103SessionRole,bytes,sizeof(bytes),length)||
       !Bell103Session::decode(bytes,length,incoming)){
      Serial.println("BELL103 SESSION RX NO VALID CONTROL");return;
    }
    bool wasConnected=bell103Session.connected();
    bell103Session.received(incoming,millis());
    if(!wasConnected&&bell103Session.connected())bell103Data.begin(bell103Session.session());
    Serial.printf("BELL103 SESSION RX type=%u id=%lu state=%s\n",
                  (unsigned)incoming.message,(unsigned long)incoming.session,
                  bell103SessionStateName(bell103Session.state()));
    screenStatus(bell103Session.connected()?"B103 CONNECTED":"B103 HANDSHAKE");return;
  }
  Serial.println("ERROR: bell103 session caller|answerer|tx|rx|show|stop.");
}

void bell103DataCommand(const char* command,size_t length) {
  if(acousticMode!=AcousticMode::Bell103||!bell103Session.connected()){
    Serial.println("ERROR: Bell 103 session is not connected.");return;
  }
  if(!strncmp(command,"bell103 data send ",18)){
    size_t textLength=length-18;
    if(!bell103Data.queue((const uint8_t*)command+18,textLength)){
      Serial.println("BELL103 DATA QUEUE FAILED (1..70 UTF-8 bytes, one outstanding frame).");return;
    }
    Serial.printf("BELL103 DATA QUEUED seq=%u len=%u\n",(unsigned)bell103Data.pendingSequence(),(unsigned)textLength);
    return;
  }
  if(!strcmp(command,"bell103 data tx")){
    uint8_t bytes[80];size_t burstLength=0;Bell103DataKind kind=Bell103DataKind::Data;
    if(!bell103Data.next(millis(),bytes,sizeof(bytes),burstLength,kind)){
      Serial.println(bell103Data.failed()?"BELL103 DATA RETRIES EXHAUSTED":"BELL103 DATA NO TX PENDING");return;
    }
    if(!bell103SendBurst(bytes,burstLength,bell103SessionRole)){
      Serial.println("BELL103 DATA TX FAILED");return;
    }
    bell103Data.sent(kind,millis());
    Serial.printf("BELL103 DATA TX type=%u seq=%u len=%u\n",(unsigned)kind,
                  (unsigned)((uint16_t)bytes[8]|((uint16_t)bytes[9]<<8)),(unsigned)burstLength);
    return;
  }
  if(!strcmp(command,"bell103 data rx")){
    uint8_t bytes[81],text[71];size_t burstLength=0,textLength=0;
    if(!bell103ReceiveBurst(bell103SessionRole,bytes,sizeof(bytes),burstLength)){
      Serial.println("BELL103 DATA RX NO VALID FRAME");return;
    }
    bool awaiting=bell103Data.awaitingAck();
    bool delivered=bell103Data.received(bytes,burstLength,text,sizeof(text)-1,textLength);
    if(delivered){
      text[textLength]=0;
      Serial.printf("BELL103 DATA RX NEW len=%u text=",(unsigned)textLength);
      Serial.write(text,textLength);Serial.println();
      screenStatus("B103 DATA RX");screenText(text,textLength);
    }else if(burstLength==Bell103DataLink::HEADER_BYTES&&bytes[0]=='B'&&bytes[1]=='D'&&
             bytes[3]==(uint8_t)Bell103DataKind::Ack&&awaiting&&!bell103Data.awaitingAck()){
      Serial.println("BELL103 DATA ACK OK");
    }else Serial.println("BELL103 DATA RX DUPLICATE OR IGNORED");
    return;
  }
  if(!strcmp(command,"bell103 data show")){
    Serial.printf("BELL103 DATA awaiting_ack=%u failed=%u next_seq=%u\n",
                  bell103Data.awaitingAck(),bell103Data.failed(),(unsigned)bell103Data.pendingSequence());return;
  }
  Serial.println("ERROR: bell103 data send <UTF-8>|tx|rx|show.");
}

bool sendPayload(uint8_t pid,const uint8_t* payload,size_t length) {
  if(monitorMode){Serial.println("ERROR: monitor mode is receive-only.");return false;}
  if(!payload||!length||length>220){if(!binaryHostMode())Serial.println("ERROR: payload must be 1..220 bytes.");return false;}
  char status[22]; snprintf(status,sizeof(status),"TX %s>%s",localCall,remoteCall);
  screenStatus(status); if(pid==0xf0)screenText(payload,length);
  if(!binaryHostMode())Serial.printf("TX START SRC=%s DEST=%s CTRL=03 PID=%02X LEN=%u\n",localCall,remoteCall,pid,(unsigned)length);
  if (!speakerEnable(true)) { if(!binaryHostMode())Serial.println("ERROR: speaker enable failed."); return false; }
  bool ok=acousticTransport.send(pid,payload,length);
  int32_t silence[256*2]={};
  for (int k=0;k<4;++k) audioSink(silence,256,nullptr);
  bool muted=speakerEnable(false);
  if (!ok || !muted) { if(!binaryHostMode())Serial.println("ERROR: AFSK transmit failed."); return false; }
  if(!binaryHostMode())Serial.printf("TX OK AX25 len=%u FCS generated; returned to RX LISTEN.\n",(unsigned)acousticTransport.lastFrameLength());
  screenStatus("RX LISTEN / TX OK");
  return true;
}

bool sendText(const char* text) {
  size_t length=strlen(text);
  if(!length||length>120){Serial.println("ERROR: TX text must be 1..120 printable ASCII characters.");return false;}
  for(size_t k=0;k<length;++k)if(text[k]<0x20||text[k]>0x7e){Serial.println("ERROR: TX text must be printable ASCII.");return false;}
  return sendPayload(0xf0,(const uint8_t*)text,length);
}

void dumpRecording() {
  if (!haveRecording) { Serial.println("ERROR: no complete PCM recording."); return; }
  Serial.printf("PCM_S16LE_STEREO 48000 %u %u\n",(unsigned)SAMPLES,(unsigned)(SAMPLES*4));
  const uint8_t* data=(const uint8_t*)pcm;
  uint32_t lastProgress=millis();
  for (size_t pos=0;pos<SAMPLES*4;) {
    size_t n=SAMPLES*4-pos; if (n>1024) n=1024;
    size_t sent=Serial.write(data+pos,n); pos+=sent;
    if (sent) lastProgress=millis();
    else { if (!Serial || millis()-lastProgress>2000) return; delay(1); }
  }
  Serial.println("\nEND PCM");
}

void receiveThreeSeconds() {
  haveRecording=false;
  screenStatus("RX / AFSK 1200");
  prepareReceiver();
  Serial.println("Preparing (discard 250 ms)...");
  if (!capture(SAMPLE_RATE/4,false)) { Serial.println("ERROR: I2S warmup read."); return; }
  Serial.println("REC 3 seconds -- transmit NOW");
  unsigned long started=millis();
  if (!capture(SAMPLES,true)) { Serial.println("ERROR: incomplete recording; not decoded."); return; }
  haveRecording=true;
  screenStatus("DECODING...");
  Serial.printf("Recorded %u ms. Decoding...\n",(unsigned)(millis()-started));
  decoder.reset(); frames=0;
  for (size_t slot=0;slot<2;++slot) {
    int peak=0; double sum=0,squares=0; size_t clipped=0;
    for (size_t k=0;k<SAMPLES;++k) {
      int x=pcm[k*2+slot]; int a=x<0?-x:x;
      if (a>peak) peak=a; if (a>=32760) ++clipped;
      sum+=x; squares+=(double)x*x;
    }
    double mean=sum/SAMPLES,variance=squares/SAMPLES-mean*mean;
    double rms=sqrt(variance>0?variance:0);
    Serial.printf("slot%u peak=%d AC_RMS=%.1f clipped=%u\n",(unsigned)slot,peak,rms,(unsigned)clipped);
    if (rms>=8) decoder.decode(pcm+slot,SAMPLES,2,discriminator,printFrame,cooperate);
  }
  Serial.printf("Done: %u valid frame(s). Send r to retry.\n",frames);
  if (!frames) screenStatus("RX LISTEN / NO FRAME");
}

void startLiveReceiver() {
  if(liveRx||acousticMode!=AcousticMode::Ax25)return;
  frames=0; liveMaxProcessUs=0; liveBlocks=0;
  acousticTransport.resetReceiver(); prepareReceiver(); liveRx=true;
  screenStatus("RX LISTEN / LIVE");
  if(!binaryHostMode())Serial.println("STATE RX LISTEN (q=stop, t <text>=TX).");
}

void stopLiveReceiver(bool report) {
  if(!liveRx)return; liveRx=false;
  if(!report)return;
  if(!binaryHostMode())Serial.printf("LIVE RX stopped: %u valid frame(s), blocks=%u max_process_us=%u.\n",
                                    frames,(unsigned)liveBlocks,(unsigned)liveMaxProcessUs);
  screenStatus("READY / SEND l");
}

void serviceLiveReceiver() {
  if(!liveRx||acousticMode!=AcousticMode::Ax25)return;
  size_t received=0;
  esp_err_t err=i2s_channel_read(audio.rxChan(),liveBlock,sizeof(liveBlock),&received,20);
  if(err==ESP_ERR_TIMEOUT || received==0)return;
  if(err!=ESP_OK) { if(!binaryHostMode())Serial.println("ERROR: LIVE RX I2S read; RX stopped."); stopLiveReceiver(); return; }
  size_t samples=received/(2*sizeof(int32_t));
  for(size_t k=0;k<samples;++k)liveMono[k]=(int16_t)(liveBlock[k*2]>>16);
  uint32_t began=micros();
  acousticTransport.processSamples(liveMono,samples,1);
  uint32_t elapsed=micros()-began;
  if(elapsed>liveMaxProcessUs)liveMaxProcessUs=elapsed; ++liveBlocks;
}

void loop() {
  if(pppMode){
    while(Serial.available())pppTransport.acceptByte((uint8_t)Serial.read());
    serviceLiveReceiver();reliableLink.service();return;
  }
  if(slipMode){
    while(Serial.available())slipTransport.acceptByte((uint8_t)Serial.read());
    serviceLiveReceiver();reliableLink.service();return;
  }
  if (!Serial.available()) { if(acousticMode==AcousticMode::Bell103)return; serviceLiveReceiver(); if(!monitorMode){reliableLink.service();if(!reliableLink.busy())groupRuntime.service(millis());} return; }
  char c=Serial.read();
  if (acousticMode==AcousticMode::Ax25 && !commandLength && (c=='q'||c=='Q')) { stopLiveReceiver(); return; }
  if (acousticMode==AcousticMode::Ax25 && !commandLength && (c=='l'||c=='L')) { startLiveReceiver(); return; }
  if (acousticMode==AcousticMode::Ax25 && !commandLength && (c=='r'||c=='R')) {
    stopLiveReceiver(false); receiveThreeSeconds(); startLiveReceiver(); return;
  }
  if (acousticMode==AcousticMode::Ax25 && !commandLength && (c=='p'||c=='P')) {
    bool resume=liveRx; stopLiveReceiver(false); dumpRecording(); if(resume)startLiveReceiver(); return;
  }
  if (!commandLength && c=='?') {
    Serial.println("Commands: t <ASCII>; g <UTF-8>; k <UTF8-HEX>; group on|off|show; monitor on|off|show; acoustic show|ax25|bell103; bell103 tone|selftest|session selftest|session caller|answerer|tx|rx|show|stop|rx originate|rx answer|tx originate <text>|tx answer <text>; z <HEX>; y <HEX>; mode ppp; slip on; boot show|normal|slip|ppp|reset; u <HEX>; x <PIDHEX> <HEX>; c <SRC> <DEST>; l=RX; q=stop; r=batch; p=PCM."); return;
  }
  if (c=='\r') return;
  if (c=='\n') {
    commandLine[commandLength]=0;
    if(!strcmp(commandLine,"bell103 data selftest")){
      bell103DataSelfTest();
    }
    else if(!strncmp(commandLine,"bell103 session ",16)){
      bell103SessionCommand(commandLine);
    }
    else if(!strncmp(commandLine,"bell103 data ",13)){
      bell103DataCommand(commandLine,commandLength);
    }
    else if(acousticMode==AcousticMode::Bell103 && strcmp(commandLine,"acoustic show") &&
            strcmp(commandLine,"acoustic ax25")){
      Serial.println("ERROR: Bell 103 session active; use bell103 session stop first.");
    }
    else if (commandLength>=3 && (commandLine[0]=='t'||commandLine[0]=='T') && commandLine[1]==' ') {
      bool resume=liveRx; stopLiveReceiver(false); Serial.println("STATE RX -> TX");
      sendText(commandLine+2);
      if(resume) { Serial.println("STATE TX -> RX"); startLiveReceiver(); }
    }
    else if(commandLength>=3 && commandLine[0]=='g' && commandLine[1]==' '){
      size_t length=commandLength-2;
      if(!groupRuntime.enabled())Serial.println("ERROR: use group on first.");
      else if(reliableLink.busy())Serial.println("ERROR: reliable transfer is busy; retry group send.");
      else if(!groupRuntime.sendText((const uint8_t*)commandLine+2,length,millis()))Serial.println("GROUP TX FAILED (length 1..198 bytes).");
      else Serial.println("GROUP TX OK");
    }
    else if(usbTransport.acceptLine(commandLine)) {}
    else if(!strcmp(commandLine,"monitor show")) {
      Serial.printf("MONITOR MODE=%s\n",monitorMode?"on":"off");
    }
    else if(!strcmp(commandLine,"monitor on")) {
      if(binaryHostMode())Serial.println("ERROR: monitor requires normal USB command mode.");
      else {
        monitorMode=true;reliableLink.cancel();groupRuntime.enable(false,millis());
        speakerEnable(false);startLiveReceiver();screenStatus("MONITOR RX ONLY");
        Serial.println("MONITOR MODE=on RX_ONLY=1 CRC_ONLY=1");
      }
    }
    else if(!strcmp(commandLine,"monitor off")) {
      monitorMode=false;screenStatus("RX LISTEN / LIVE");Serial.println("MONITOR MODE=off");
    }
    else if(!strcmp(commandLine,"slip on")) {
      activateHostMode(BootMode::Slip);
    }
    else if(!strcmp(commandLine,"mode ppp")) {
      activateHostMode(BootMode::Ppp);
    }
    else if(!strcmp(commandLine,"boot show")) {
      Serial.printf("BOOT MODE=%s saved=%s\n",bootModeName(bootMode),preferences.isKey("boot")?"yes":"no");
    }
    else if(!strcmp(commandLine,"acoustic show")) {
      if(acousticMode==AcousticMode::Ax25)Serial.println("ACOUSTIC MODE=ax25 READY=ax25");
      else Serial.printf("ACOUSTIC MODE=bell103 state=%s\n",bell103SessionStateName(bell103Session.state()));
    }
    else if(!strcmp(commandLine,"bell103 tone")) {
      playBell103Overture();
    }
    else if(!strcmp(commandLine,"bell103 selftest")) {
      bell103SelfTest();
    }
    else if(!strcmp(commandLine,"bell103 session selftest")) {
      bell103SessionSelfTest();
    }
    else if(!strcmp(commandLine,"bell103 rx originate")) {
      bell103ReceiveDiagnostic(Bell103Role::Originate);
    }
    else if(!strcmp(commandLine,"bell103 rx answer")) {
      bell103ReceiveDiagnostic(Bell103Role::Answer);
    }
    else if(!strncmp(commandLine,"bell103 tx originate ",21)) {
      bell103SendDiagnostic((const uint8_t*)commandLine+21,commandLength-21,Bell103Role::Originate);
    }
    else if(!strncmp(commandLine,"bell103 tx answer ",18)) {
      bell103SendDiagnostic((const uint8_t*)commandLine+18,commandLength-18,Bell103Role::Answer);
    }
    else if(!strncmp(commandLine,"acoustic ",9)) {
      AcousticMode requested;
      if(!parseAcousticMode(commandLine+9,requested)) Serial.println("ERROR: use acoustic show|ax25|bell103.");
      else if(requested==AcousticMode::Bell103) Serial.println("ERROR: Bell 103 is not ready in this build; AX.25 remains active.");
      else if(acousticMode==AcousticMode::Bell103)bell103SessionCommand("bell103 session stop");
      else Serial.println("ACOUSTIC MODE=ax25 (unchanged).");
    }
    else if(!strcmp(commandLine,"group show")) {
      Serial.printf("GROUP MODE=%s READY=v%u LOCAL=%s GROUP=%s\n",groupRuntime.enabled()?"on":"direct",GroupChatProtocol::VERSION,groupChat.local(),groupRuntime.group());
    }
    else if(!strcmp(commandLine,"group on")){
      groupRuntime.enable(true,millis());Serial.println("GROUP MODE=on (temporary; direct chat remains available).");
    }
    else if(!strcmp(commandLine,"group off")){
      groupRuntime.enable(false,millis());Serial.println("GROUP MODE=direct.");
    }
    else if(!strcmp(commandLine,"boot reset")) {
      preferences.remove("boot");bootMode=BootMode::Normal;Serial.println("BOOT MODE=normal saved=no; restart to apply.");screenStatus("BOOT RESET");
    }
    else if(!strncmp(commandLine,"boot ",5)) {
      BootMode requested;
      if(parseBootMode(commandLine+5,requested)){preferences.putString("boot",bootModeName(requested));bootMode=requested;Serial.printf("BOOT MODE=%s saved=yes; restart to apply.\n",bootModeName(bootMode));screenStatus("BOOT SAVED");}
      else Serial.println("ERROR: use boot normal|slip|ppp|show|reset.");
    }
    else if(commandLength>=5 && (commandLine[0]=='c'||commandLine[0]=='C') && commandLine[1]==' ') {
      char src[7]={},dst[7]={},extra=0;
      if(sscanf(commandLine+2,"%6s %6s %c",src,dst,&extra)==2)configureCalls(src,dst);
      else Serial.println("ERROR: use c <SRC> <DEST>.");
    }
    else if (commandLength) Serial.println("ERROR: command; use ? for help.");
    commandLength=0; return;
  }
  if (commandLength+1<sizeof(commandLine)) commandLine[commandLength++]=c;
  else { commandLength=0; Serial.println("ERROR: command too long."); }
}
