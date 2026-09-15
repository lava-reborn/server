class lol.core.globmap.GlobalMap
{
   var XMC;
   var dispatchEvent;
   var markList;
   var master;
   var playerList;
   var spt;
   var spt_int;
   var tempMark;
   var tempMark_ID;
   var tempMoveObj;
   var canMove = true;
   var ma_state = "empty";
   function GlobalMap()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("newUser",this);
      this.XMC.addEventListener("userLost",this);
      this.XMC.addEventListener("userMove",this);
      this.XMC.addEventListener("moveAck",this);
      this.XMC.addEventListener("marks",this);
      this.playerList = new Array();
      this.master = lol.core.Master.getInstance();
      this.master.addEventListener("changeWorld",this);
      this.startPC();
   }
   function addGamer(obj)
   {
      var _loc6_ = Number(obj.param.x);
      var _loc5_ = Number(obj.param.y);
      var _loc4_ = Number(obj.param.v_rad);
      var _loc2_ = this.addPlayer(lol.core.player.Gamer.ID,_loc6_,_loc5_).walker;
      _loc2_.v_rad = Number(_loc4_);
      clearInterval(_loc2_.liveInterval);
      return _loc2_;
   }
   function newUser(evt_obj)
   {
      var _loc4_ = evt_obj.param.id;
      var _loc3_ = !this.gamer.walker ? 0 : this.gamer.walker.x;
      var _loc2_ = !this.gamer.walker ? 0 : this.gamer.walker.y;
      var _loc6_ = Number(evt_obj.param.dx);
      var _loc5_ = Number(evt_obj.param.dy);
      var _loc9_ = _loc3_ - _loc6_;
      var _loc8_ = _loc2_ - _loc5_;
      this.addPlayer(_loc4_,_loc9_,_loc8_);
   }
   function userLost(evt_obj)
   {
      var _loc2_ = evt_obj.param.id;
      this.removePlayer(_loc2_);
   }
   function addPlayer(id, x, y)
   {
      var _loc3_ = this.master.addPlayer(id);
      _loc3_.walker = new lol.core.globmap.MapObject(id,x,y);
      _loc3_.walker.addEventListener("position",this);
      _loc3_.walker.addEventListener("faraway",this);
      _loc3_.walker.addEventListener("near",this);
      _loc3_.walker.addEventListener("lost",this);
      _loc3_.walker.startCheckLive();
      this.playerList[id] = _loc3_;
      this.dispatchEvent({type:"addPlayer",player:_loc3_});
      return _loc3_;
   }
   function removePlayer(id)
   {
      var _loc3_ = this.playerList[id];
      _loc3_.walker.removeEventListener("position",this);
      _loc3_.walker.removeEventListener("faraway",this);
      _loc3_.walker.removeEventListener("near",this);
      _loc3_.walker.removeEventListener("lost",this);
      _loc3_.walker.kill();
      _loc3_.walker = null;
      delete this.playerList[id];
      this.playerList[id] = null;
      this.dispatchEvent({type:"removePlayer",player:_loc3_});
   }
   function playerMove(dx, dy)
   {
      var _loc2_ = new lol.server.mess.CSM_GM_MovePlayer(dx,dy);
      this.XMC.Send(_loc2_);
      this.dispatchEvent({type:"startMove"});
   }
   function changeWorld(obj)
   {
      this.canMove = !obj.success;
   }
   function moveAck(evt_obj)
   {
      this.moveObject(this.gamer,evt_obj);
   }
   function userMove(evt_obj)
   {
      var _loc2_ = evt_obj.param.id;
      var _loc3_;
      if(!_loc2_)
      {
         _loc3_ = this.gamer;
      }
      else if(this.playerList[_loc2_] == null || this.playerList[_loc2_] == undefined)
      {
         _loc3_ = this.addPlayer(_loc2_);
      }
      else
      {
         _loc3_ = this.playerList[_loc2_];
      }
      _loc3_.walker.x = Number(evt_obj.param.dx);
      _loc3_.walker.y = Number(evt_obj.param.dy);
      var _loc6_ = Number(evt_obj.param.vx);
      var _loc5_ = Number(evt_obj.param.vy);
      var _loc7_ = Number(evt_obj.param.t);
      _loc3_.walker.startMove(_loc6_,_loc5_,_loc7_);
   }
   function moveObject(player, evt_obj)
   {
      var _loc2_ = Number(evt_obj.param.vx);
      var _loc1_ = Number(evt_obj.param.vy);
      var _loc3_ = Number(evt_obj.param.t);
      player.walker.startMove(_loc2_,_loc1_,_loc3_);
   }
   function position(obj)
   {
      this.dispatchEvent({type:"position",walker:obj.target});
   }
   function faraway(obj)
   {
      this.dispatchEvent({type:"faraway",walker:obj.target,id:obj.target.id});
   }
   function near(obj)
   {
      this.dispatchEvent({type:"near",walker:obj.target,id:obj.target.id});
   }
   function lost(obj)
   {
      this.dispatchEvent({type:"lost",player:obj.target,id:obj.target.id});
      this.removePlayer(obj.target.id);
   }
   function getUsers()
   {
      return this.playerList;
   }
   function marks(obj)
   {
      this.markList = new Array();
      var _loc8_ = obj.param.dxdy;
      var _loc9_ = obj.param.title;
      var _loc10_ = obj.param.info;
      var _loc11_ = _loc9_.length;
      var _loc2_ = 0;
      var _loc4_;
      var _loc3_;
      var _loc6_;
      var _loc5_;
      var _loc7_;
      while(_loc2_ < _loc11_)
      {
         _loc4_ = lol.server.XMLString.unescape(_loc9_[_loc2_]);
         _loc3_ = lol.server.XMLString.unescape(_loc10_[_loc2_]);
         _loc6_ = _loc8_[_loc2_ * 2];
         _loc5_ = _loc8_[_loc2_ * 2 + 1];
         _loc7_ = this.createMark(_loc6_,_loc5_,_loc4_,_loc3_);
         this.__addMark(_loc7_);
         _loc2_ = _loc2_ + 1;
      }
   }
   function createMark(dx, dy, title, info)
   {
      var _loc2_ = new Object();
      _loc2_.title = title;
      _loc2_.info = info;
      _loc2_.x = Math.floor(this.gamer.walker.x + dx);
      _loc2_.y = Math.floor(this.gamer.walker.y + dy);
      return _loc2_;
   }
   function addMark(x, y, title, info)
   {
      var _loc3_ = Math.floor(x - this.gamer.walker.x);
      var _loc2_ = Math.floor(y - this.gamer.walker.y);
      this.tempMark = this.createMark(_loc3_,_loc2_,title,info);
      this.ma_state = "add";
      var _loc4_ = new lol.server.mess.CSM_GM_InsMark(_loc3_,_loc2_,new lol.data.GDString(title),new lol.data.GDString(info));
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cmdAck);
      }
   }
   function __addMark(mark)
   {
      this.markList.push(mark);
      this.dispatchEvent({type:"addMark",mark:mark});
   }
   function removeMark(mark)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.markList.length)
      {
         if(this.markList[_loc2_] == mark)
         {
            this.tempMark = mark;
            this.tempMark_ID = _loc2_;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.ma_state = "remove";
      var _loc4_ = new lol.server.mess.CSM_GM_RemoveMark(this.tempMark_ID);
      if(this.XMC.Send(_loc4_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cmdAck);
      }
   }
   function __removeMark(id)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.markList.length)
      {
         if(this.markList[_loc2_] == this.tempMark)
         {
            this.markList.splice(_loc2_,1);
            this.dispatchEvent({type:"removeMark",mark:this.tempMark});
            delete this.tempMark;
            return undefined;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function editMark(obj)
   {
      var _loc8_ = obj.mark;
      var _loc5_ = obj.info;
      var _loc6_ = obj.title;
      var _loc7_;
      var _loc2_ = 0;
      while(_loc2_ < this.markList.length)
      {
         if(this.markList[_loc2_] == _loc8_)
         {
            _loc7_ = _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc4_ = new lol.server.mess.CSM_GM_UpdMark(_loc7_,new lol.data.GDString(_loc6_),new lol.data.GDString(_loc5_));
      this.XMC.Send(_loc4_);
      _loc8_.title = _loc6_;
      _loc8_.info = _loc5_;
      this.dispatchEvent({type:"updateMark",mark:_loc8_,id:_loc7_,title:_loc6_,info:_loc5_});
   }
   function selectMark(mark, select)
   {
      this.dispatchEvent({type:"selectMark",mark:mark,select:select});
   }
   function cmdAck(obj)
   {
      if(obj.param.res == 0 && this.ma_state != "empty")
      {
         if(this.ma_state == "add")
         {
            this.__addMark(this.tempMark);
         }
         else if(this.ma_state == "remove")
         {
            this.__removeMark(this.tempMark);
         }
         this.dispatchEvent({type:"ack"});
         this.ma_state = "empty";
      }
   }
   function kill()
   {
      this.master.removeEventListener("changeWorld",this);
      this.XMC.removeEventListener("newUser",this);
      this.XMC.removeEventListener("userLost",this);
      this.XMC.removeEventListener("userMove",this);
      this.XMC.removeEventListener("moveAck",this);
      this.XMC.removeEventListener("marks",this);
      this.clearObjList();
      this.markList = new Array();
      this.tempMark = null;
   }
   function clearObjList()
   {
      this.master.gamer.walker.kill();
      this.master.gamer.walker = null;
      for(var _loc2_ in this.playerList)
      {
         this.removePlayer(_loc2_);
      }
      this.playerList = new Array();
   }
   function get gamer()
   {
      return this.master.gamer;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("GlobalMap_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function testMove(player, obj)
   {
      if(!this.tempMoveObj)
      {
         this.tempMoveObj = new Object();
      }
      var _loc3_ = getTimer();
      var _loc2_ = (_loc3_ - this.tempMoveObj.t) / 1000;
      var _loc6_ = obj.param.dx;
      var _loc5_ = obj.param.dy;
      var _loc7_ = obj.param.vx;
      var _loc8_ = obj.param.vy;
      var _loc12_ = this.tempMoveObj.x + this.tempMoveObj.vx * _loc2_;
      var _loc11_ = this.tempMoveObj.y + this.tempMoveObj.vy * _loc2_;
      var _loc10_ = (_loc6_ - this.tempMoveObj.x) / _loc2_;
      var _loc9_ = (_loc5_ - this.tempMoveObj.y) / _loc2_;
      this.tempMoveObj.vx = _loc7_;
      this.tempMoveObj.vy = _loc8_;
      this.tempMoveObj.x = _loc6_;
      this.tempMoveObj.y = _loc5_;
      this.tempMoveObj.t = _loc3_;
   }
   function interceptPlayer(id, flag)
   {
      var _loc2_;
      if(id)
      {
         if(flag)
         {
            _loc2_ = new lol.server.mess.CSM_GM_InterceptPlayer(id);
            if(!this.XMC.Send(_loc2_))
            {
            }
         }
         else
         {
            this.playerMove(0,1);
         }
      }
   }
   function gotoLastPlayerPosition(id)
   {
      var _loc2_ = lol.core.globmap.MapObject(lol.core.Master.getInstance().getPlayer(id).walker);
      var _loc4_ = Math.floor(100 * (_loc2_.x - this.gamer.walker.x));
      var _loc3_ = Math.floor(100 * (_loc2_.y - this.gamer.walker.y));
      this.playerMove(_loc4_,_loc3_);
   }
   function interceptAck(obj)
   {
   }
}
