import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from web_chat_gateway import Gateway

class Client:
    def __init__(self):self.messages=[]
    def send(self,message):self.messages.append(message)

class WebGatewayTest(unittest.TestCase):
    def test_local_room_broadcasts_utf8(self):
        gateway=Gateway("room",("127.0.0.1",0),None);a=Client();b=Client();gateway.clients.update((a,b))
        gateway.browser_message(a,{"type":"send","sender":"手機A","text":"日本語／繁體中文"})
        self.assertEqual(a.messages[-1]["text"],"日本語／繁體中文")
        self.assertEqual(b.messages[-1]["sender"],"手機A")
        gateway.transport.socket.close()

if __name__=="__main__":unittest.main()
