"""Real socket: Said's new quests, paid statuses, rental extension and total cap."""
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
os.environ.pop("LAVA_DB_URL",None)
import accounts
import progression
import world
from protocol import decode
from testkit import check,fails,connect

root=Path(__file__).resolve().parent
work=Path(tempfile.mkdtemp(prefix="lava-residence-wire-"))
db=work/"game.sqlite"
with socket.socket() as probe:
    probe.bind(("127.0.0.1",0));port=probe.getsockname()[1]
store=accounts.Store(str(db))
account,_=store.register("residentwire","test-only")
cid,_=store.create_character(account,"ResidentWire",0,"1")
said_cell=next(cell for cell,t in world.location(36).spawns if t==44)
gx,gy=world.cell_of(36)
store.save_position(cid,36,said_cell,gx,gy,False)
store.save_character_state(cid,gold=10000,afro=1000000)
store.close()
env=dict(os.environ,LAVA_DB=str(db),LAVA_PORT=str(port),LAVA_HOST="127.0.0.1",
         LAVA_POLICY_PORT="0",LAVA_CHEATS="1",LAVA_COMBAT_LINGER="0")
process=subprocess.Popen([sys.executable,"-B","server.py"],cwd=root,env=env,
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8")
logs=[]
thread=threading.Thread(target=lambda:logs.extend(process.stdout),daemon=True);thread.start()


class Client:
    def __init__(self):
        self.socket=connect(port,process,logs)
        self.socket.settimeout(30)
        self.buffer=b""
    def send(self,text):self.socket.sendall(text.encode("utf-8")+b"\0")
    def until(self,predicate):
        frames=[]
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if b"\0" not in self.buffer:
                chunk=self.socket.recv(65536)
                if not chunk:raise RuntimeError("socket closed")
                self.buffer+=chunk
            while b"\0" in self.buffer:
                raw,self.buffer=self.buffer.split(b"\0",1)
                if not raw:continue
                event=decode(raw.decode("utf-8"));frames.append(event)
                if predicate(*event):return frames
        raise RuntimeError("response not received")
    def named(self,name):return self.until(lambda cmd,p:cmd==name)
    def login(self):
        self.send("hello;minor=2;major=0;")
        self.send("login;hash=@%s@;"%accounts.credential("residentwire","test-only"))
        self.named("accountInfo")
        self.send("selPers;num=0;");self.named("lcall")
        self.send("lenter;accept=1;")
        return self.until(lambda cmd,p:cmd.startswith("userInfo_") and p.get("name")==44)
    def ack(self,command):
        self.send(command);return self.named("cmdAck")
    def logout(self):
        self.send("logout;")
        while self.socket.recv(65536):pass
        self.socket.close()


def get(frames,cmd):return next(p for c,p in frames if c==cmd)
def result(frames):return get(frames,"cmdAck")["res"]
def take(client,npc,t):
    index=npc["give_quests"].index(t)
    client.send("q_st;mob=%d;q_idx=%d;"%(npc["id"],index))
    frames=client.named("q_di_del_obj")
    check("quest %d taken through actual NPC list"%t,result(frames),0)
    return get(frames,"q_di_del_obj")["q_id"]


client=None
try:
    client=Client();arrival=client.login()
    said=next(p for cmd,p in arrival if cmd=="userInfo_Commoner" and p.get("name")==44)
    check("Said advertises both status quests",set((2129,2130)).issubset(said["give_quests"]),True)
    qid=take(client,said,2129)
    frames=client.ack("q_co;q_id=%d;mob=%d;obj_idx=0;"%(qid,said["id"]))
    check("registration paid and applied on the wire",(result(frames),get(frames,"userInfo_Player")["gold"],get(frames,"rp_info")["max_weight"]),(0,9000,65000))
    p_until=get(frames,"rp_info")["residence_until"]
    qid=take(client,said,2130)
    check("unconfirmed replacement is refused",result(client.ack("q_co;q_id=%d;mob=%d;obj_idx=0;"%(qid,said["id"])))!=0,True)
    frames=client.ack("q_co;q_id=%d;mob=%d;obj_idx=0;residence_from=%d;"%(qid,said["id"],p_until))
    check("confirmed VNJ gives correct gold, status and weight",(result(frames),get(frames,"userInfo_Player")["gold"],get(frames,"userInfo_Player")["pr"],get(frames,"rp_info")["max_weight"]),(0,6000,2,90000))
    for t in (2129,2130):
        client.send("q_status;q_type=%d;"%t)
        check("active VNJ blocks status quest %d"%t,get(client.named("q_status"),"q_status")["status"],0)
    client.send("userMsg;entry=@/goto 102@;group=0;");client.named("lcall")
    client.send("lenter;accept=1;")
    arrival=client.until(lambda cmd,p:cmd=="userInfo_Lessor" and p.get("name")==653)
    lessor=get(arrival,"userInfo_Lessor")
    cell=next(p["pos"] for cmd,p in arrival if cmd=="lch" and p.get("newUser")==lessor["id"])
    client.send("moveTo;path=|%d|;"%cell);client.named("userMove")
    command="on_conv;op=2;mob=%d;p1=4;p2=1;"%lessor["id"]
    first=client.ack(command);first_info=get(first,"userInfo_Player")
    second=client.ack(command);second_info=get(second,"userInfo_Player")
    check("same UAZ extends the exact deadline by a day",(result(first),result(second),second_info["rental_until"]-first_info["rental_until"]),(0,0,86400))
    check("two extensions charge gold, not afro",(first_info["afro"],second_info["afro"],first_info["gold"],second_info["gold"]),(1000000,1000000,5930,5860))
    frames=client.ack("on_conv;op=2;mob=%d;p1=5;p2=1;"%lessor["id"])
    check("VNJ can rent Hummer for 0.90 gold",(result(frames),get(frames,"userInfo_Player")["afro"],get(frames,"userInfo_Player")["gold"],get(frames,"userInfo_Player")["tr"]),(0,1000000,5770,5))
    client.logout();client=None
    store=accounts.Store(str(db))
    store.save_position(cid,36,said_cell,gx,gy,False)
    store.save_character_state(cid,premium_until=time.time()+3600,transport_type=None,transport_until=None)
    store.close()
    client=Client();client.login()
    client.send("userMsg;entry=@/goto 102@;group=0;");client.named("lcall")
    client.send("lenter;accept=1;")
    arrival=client.until(lambda cmd,p:cmd=="userInfo_Lessor" and p.get("name")==653)
    lessor=get(arrival,"userInfo_Lessor")
    cell=next(p["pos"] for cmd,p in arrival if cmd=="lch" and p.get("newUser")==lessor["id"])
    client.send("moveTo;path=|%d|;"%cell);client.named("userMove")
    check("one-hour status refuses two-day rental",result(client.ack("on_conv;op=2;mob=%d;p1=5;p2=2;"%lessor["id"]))!=0,True)
    check("one-hour status still allows one full day",result(client.ack("on_conv;op=2;mob=%d;p1=5;p2=1;"%lessor["id"])),0)
    check("repeated extension cannot escape the total status cap",result(client.ack("on_conv;op=2;mob=%d;p1=5;p2=1;"%lessor["id"]))!=0,True)
    client.logout();client=None
except Exception:
    import traceback
    fails.append(traceback.format_exc())
finally:
    if client is not None:client.socket.close()
    process.terminate();process.wait(timeout=10);thread.join(timeout=2)
    if "Traceback" in "".join(logs):fails.append("server traceback: "+"".join(logs)[-3000:])
if fails:
    print("FAILED:",*fails,sep="\n")
    raise SystemExit(1)
print("residence protocol OK")
