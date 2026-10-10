import queue,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import chat_protocol as protocol
from ip_chat import UdpChatTransport

class IpChatTest(unittest.TestCase):
    def pair(self):
        received_a=queue.Queue();received_b=queue.Queue()
        a=UdpChatTransport(("127.0.0.1",0),("127.0.0.1",1),lambda m,p:received_a.put(m))
        b=UdpChatTransport(("127.0.0.1",0),("127.0.0.1",1),lambda m,p:received_b.put(m))
        a.peer=b.socket.getsockname();b.peer=a.socket.getsockname();a.start();b.start()
        self.addCleanup(a.close);self.addCleanup(b.close)
        return a,b,received_a,received_b
    def test_utf8_both_directions(self):
        a,b,received_a,received_b=self.pair()
        self.assertEqual(a.send("PC-A","日本語の漢字",timeout=.5)[1],1)
        self.assertEqual(b.send("PC-B","繁體中文測試",timeout=.5)[1],1)
        self.assertEqual(received_b.get(timeout=1)["text"],"日本語の漢字")
        self.assertEqual(received_a.get(timeout=1)["text"],"繁體中文測試")
    def test_duplicate_is_delivered_once(self):
        a,b,_,received_b=self.pair();data=protocol.encode(protocol.chat("PC-A","重複抑止",message_id="fixed-duplicate-id"))
        a.socket.sendto(data,a.peer);a.socket.sendto(data,a.peer);time.sleep(.3)
        self.assertEqual(received_b.qsize(),1)

if __name__=="__main__":unittest.main()
