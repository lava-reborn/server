class lol.core.location.Location
{
   var XMC;
   var curFireEvent;
   var dispatchEvent;
   var exLocPan;
   var locInfo;
   var locationGrid;
   var lootBagList;
   var master;
   var playerList;
   var spt;
   var spt_int;
   var staticObjectList;
   var warStatus;
   function Location()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.init();
      this.master = lol.core.Master.getInstance();
      this.staticObjectList = new Array();
      this.playerList = new Array();
      this.lootBagList = new Array();
      this.startPC();
   }
   function init()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("lch",this);
      this.XMC.addEventListener("prepare",this);
      this.XMC.addEventListener("userMove",this);
      this.XMC.addEventListener("breakMv",this);
      this.XMC.addEventListener("cor_pos",this);
      this.XMC.addEventListener("fireAck",this);
      this.XMC.addEventListener("ss_loot",this);
      this.XMC.addEventListener("faAim",this);
      this.XMC.addEventListener("faShot",this);
      this.XMC.addEventListener("faHit",this);
      this.XMC.addEventListener("faWall",this);
      this.XMC.addEventListener("faMiss",this);
      this.XMC.addEventListener("heal",this);
      this.XMC.addEventListener("caHit",this);
      this.XMC.addEventListener("caMiss",this);
   }
   function lch(obj)
   {
      var _loc7_ = obj.param.ws;
      var _loc4_ = obj.param.newUser;
      var _loc6_ = obj.param.pos;
      var _loc3_ = obj.param.rtype;
      var _loc5_ = obj.param.lostUser;
      var _loc10_ = obj.param.friend;
      var _loc8_ = obj.param.enemy;
      var _loc13_ = obj.param.dead;
      var _loc11_ = obj.param.refl;
      if(_loc7_ != undefined)
      {
         this.warState(_loc7_);
      }
      if(_loc4_ != undefined && _loc6_ != undefined && _loc3_ != undefined)
      {
         if(_loc11_ != undefined)
         {
            this.addPlayer(_loc4_,undefined,_loc3_);
         }
         else
         {
            this.addPlayer(_loc4_,_loc6_,_loc3_);
         }
      }
      if(_loc5_ != undefined)
      {
         this.removePlayer(_loc5_);
         lol.services.GameEvents.addEvent(lol.services.GameEvents.LOST_PLAYER,{nickname:this.master.getPlayer(_loc5_).playerInfo.name,locationname:this.locationName});
      }
      if(!_loc10_)
      {
      }
      if(_loc8_)
      {
         this.setEnemy(_loc8_);
      }
      var _loc9_;
      if(_loc13_ != undefined)
      {
         _loc9_ = lol.core.Master.getInstance().getPlayer(_loc13_);
         if(_loc9_ instanceof lol.core.player.NPC && lol.core.player.NPC(_loc9_).hasAvailableQuests())
         {
            lol.core.quests.QuestInspector.getInstance().setQuestNPC(null);
         }
         this.dispatchEvent({type:"dead",dead:_loc13_});
      }
   }
   function prepare(obj)
   {
      var _loc3_ = obj.param.id;
      var _loc2_ = obj.param.time;
      var _loc4_ = this.master.getPlayer(_loc3_);
      _loc4_.prepare = !_loc2_ ? 0 : _loc2_;
   }
   function addGamer(pos)
   {
      var _loc2_ = this.addPlayer(lol.core.player.Gamer.ID,pos).walker;
      return _loc2_;
   }
   function addPlayer(id, pos, rtype)
   {
      var _loc5_ = this.master.addPlayer(id,rtype);
      var _loc2_;
      if(pos != undefined)
      {
         _loc5_.walker = new lol.core.location.LocWalker(id);
         _loc2_ = this.getCellFromNumber(pos);
         _loc2_.busy = true;
         if(_loc5_ instanceof lol.core.player.NPC)
         {
            _loc2_.alwaysBusy = true;
         }
         _loc5_.walker.numPos = pos;
         _loc5_.walker.x = _loc2_.rx;
         _loc5_.walker.y = _loc2_.ry;
         _loc5_.walker.addEventListener("position",this);
         _loc5_.walker.addEventListener("finishPart",this);
         _loc5_.walker.addEventListener("finishMove",this);
      }
      else
      {
         _loc5_.walker = undefined;
      }
      this.playerList[id] = _loc5_;
      this.dispatchEvent({type:"addPlayer",player:_loc5_});
      return _loc5_;
   }
   function removePlayer(id)
   {
      var _loc4_ = this.playerList[id];
      var _loc3_;
      if(_loc4_.walker != undefined)
      {
         _loc4_.walker.removeEventListener("position",this);
         _loc4_.walker.removeEventListener("finishPart",this);
         _loc4_.walker.removeEventListener("finishMove",this);
         _loc3_ = this.getCellFromNumber(_loc4_.walker.numPos);
         _loc3_.busy = false;
         _loc4_.walker.kill();
         _loc4_.walker = null;
      }
      delete this.playerList[id];
      this.playerList[id] = null;
      this.master.removePlayer(id);
      this.dispatchEvent({type:"removePlayer",player:_loc4_});
   }
   function getPlayer(id)
   {
      return this.master.getPlayer(id);
   }
   function getWalker(id)
   {
      var _loc2_ = !id ? this.gamer.walker : this.playerList[id].walker;
      return _loc2_;
   }
   function position(obj)
   {
      this.dispatchEvent({type:"position",walker:obj.target});
   }
   function finishPart(obj)
   {
      var _loc4_ = obj.target;
      var _loc2_ = this.getCellFromNumber(_loc4_.prevNumPos);
      _loc2_.busy = false;
      var _loc3_ = this.getCellFromNumber(_loc4_.numPos);
      _loc3_.busy = true;
      this.dispatchEvent({type:"finishPart",walker:_loc4_});
   }
   function finishMove(obj)
   {
      var _loc2_ = obj.target;
      if(_loc2_ == this.gamer.walker && this.getCellFromNumber(_loc2_.numPos).zone)
      {
         this.exitLocation();
      }
      this.dispatchEvent({type:"finishMove",walker:_loc2_});
   }
   function userMove(obj)
   {
      var _loc8_ = obj.param.id;
      var _loc4_ = obj.param.path;
      var _loc7_ = new Array();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = this.locationGrid.getCellFromNumber(_loc4_[_loc2_]);
         _loc7_.push(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      var _loc5_ = this.getWalker(obj.param.id);
      _loc5_.createMove(_loc7_);
      this.dispatchEvent({type:"moveWalker",id:_loc8_,path:_loc7_});
   }
   function movePlayer(cell, spliceNum)
   {
      var _loc7_ = this.getCellFromNumber(this.gamer.walker.numPos);
      var _loc3_ = this.findPath(_loc7_,cell);
      var _loc4_;
      var _loc6_;
      var _loc2_;
      var _loc9_;
      if(_loc3_.length > 0)
      {
         if(_loc7_ != cell && cell.num != this.gamer.walker.finishPos)
         {
            _loc3_.unshift(_loc7_);
            _loc2_ = 0;
            while(_loc2_ < _loc3_.length)
            {
               _loc4_ = _loc3_[_loc2_];
               if(cell == _loc4_)
               {
                  _loc6_ = true;
                  break;
               }
               _loc2_ = _loc2_ + 1;
            }
            if(!_loc6_ && !this.locationGrid.isUnreachible(cell))
            {
               _loc3_.push(cell);
            }
            if(spliceNum)
            {
               _loc3_.splice(_loc3_.length - spliceNum,spliceNum);
            }
            _loc9_ = new lol.server.mess.CSM_L_MovePlayer(new lol.data.GDList(_loc3_));
            if(this.XMC.Send(_loc9_))
            {
               this.gamer.walker.finishPos = cell.num;
               lol.server.XMLCCallStack.addCall("cmdAck",this,this.moveCmdAck,cell.num);
            }
         }
      }
   }
   function moveCmdAck(obj)
   {
      var _loc1_ = obj.param.res;
      if(_loc1_ == 0)
      {
      }
   }
   function breakMv(obj)
   {
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.moveCmdAck);
      var _loc4_ = obj.param.pos;
      var _loc3_ = obj.param.id;
      var _loc2_ = this.getWalker(_loc3_);
      _loc2_.breakMove(_loc4_);
      var _loc5_ = this.getCellFromNumber(_loc2_.prevNumPos);
      _loc5_.busy = false;
      var _loc6_ = this.getCellFromNumber(_loc2_.numPos);
      _loc6_.busy = true;
   }
   function cor_pos(obj)
   {
      var _loc5_ = obj.param.pos;
      var _loc4_ = this.getPlayer(obj.param.id);
      this.breakMv(obj);
      var _loc3_;
      if(_loc4_ == this.gamer)
      {
         _loc3_ = this.getCellFromNumber(this.gamer.walker.finishPos);
         this.gamer.walker.finishPos = null;
         this.movePlayer(_loc3_);
      }
   }
   function warState(ws)
   {
      this.warStatus = Boolean(ws);
      this.gamer.walker.warState(ws);
      this.gamer.apManager.warState(ws);
      this.gamer.walker.finishPos = this.gamer.walker.numPos;
      var _loc3_;
      if(ws)
      {
         lol.sound.SoundManager.getInstance().playSoundTrack("Battle");
      }
      else
      {
         _loc3_ = !this.locInfo.bg_soundID ? "Desert" : this.locInfo.bg_soundID;
         lol.sound.SoundManager.getInstance().playSoundTrack(_loc3_);
      }
      this.wsLogMessage(ws);
      this.dispatchEvent({type:"warState",status:this.warStatus});
   }
   function wsLogMessage(ws)
   {
      if(ws)
      {
         lol.services.GameEvents.addEvent(lol.services.GameEvents.WAR_STATE_START);
      }
      else
      {
         lol.services.GameEvents.addEvent(lol.services.GameEvents.WAR_STATE_END);
      }
   }
   function fireUser(id)
   {
      this.gamer.addEventListener("useAck",this,this.fireFailed);
   }
   function fireHex(cellNum)
   {
      this.gamer.addEventListener("useAck",this,this.fireFailed);
   }
   function fireFailed(obj)
   {
      this.gamer.removeEventListener("useAck",this,this.fireFailed);
      if(!(obj.res == 0 || obj.param.res == 0))
      {
         this.dispatchEvent({type:"fire",gunner:this.gamer,access:false,res:obj.res});
      }
   }
   function faAim(obj)
   {
      var _loc5_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc6_ = obj.param.ang;
      var _loc3_ = !obj.param.num_shots ? 1 : obj.param.num_shots;
      this.aiming(_loc5_,_loc6_,_loc3_);
      var _loc4_ = this.getWalker(_loc5_);
      _loc4_.numOfShot = _loc3_;
      _loc4_.currNumOfShot = _loc3_;
   }
   function aiming(aimID, ang, num_shots)
   {
      this.dispatchEvent({type:"aim",aim:aimID,ang:ang,num_shots:num_shots});
   }
   function faShot(obj)
   {
      var _loc5_ = obj.param.status;
      var _loc2_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc3_;
      if(_loc5_)
      {
         this.curFireEvent = new lol.events.FireEvent();
         this.curFireEvent.gunnerID = _loc2_;
         this.curFireEvent.shot = true;
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.SHOT,_loc2_));
      }
      else
      {
         this.dispatchEvent(this.curFireEvent);
         _loc3_ = this.getWalker(_loc2_);
         _loc3_.currNumOfShot = _loc3_.currNumOfShot - 1;
         if(_loc3_.currNumOfShot == 0)
         {
            this.endOfShot(_loc2_);
         }
         this.curFireEvent = null;
      }
   }
   function endOfShot(gunnerID)
   {
      var _loc4_ = this.getWalker(gunnerID);
      var _loc3_ = this.getWalker(_loc4_.targetID);
      var _loc2_;
      _loc2_ = {};
      _loc2_.health_damage = _loc3_.damage;
      _loc2_.stamina_damage = _loc3_.sdamage;
      _loc2_.nickname = lol.core.Master.getInstance().getPlayer(gunnerID).playerInfo.name;
      _loc2_.nickname2 = lol.core.Master.getInstance().getPlayer(_loc4_.targetID).playerInfo.name;
      _loc2_.value = _loc4_.numOfShot;
      _loc2_.itemname = this.master.getPlayer(gunnerID).equipment.primaryItem;
      var _loc7_ = _loc2_.itemname;
      var _loc6_ = _loc7_.getProp("weapon_type");
      if(_loc4_.numOfShot == 1 || _loc6_ == lol.core.objects.FireArm.SHOTGUN)
      {
         lol.services.GameEvents.addEvent(lol.services.GameEvents.DAMAGE,_loc2_);
      }
      else
      {
         lol.services.GameEvents.addEvent(lol.services.GameEvents.SUMMARY_DAMAGE,_loc2_);
      }
      this.damage(_loc4_.targetID,_loc3_.damage,_loc3_.sdamage,this.curFireEvent.hits[0].critical);
      _loc3_.damage = 0;
      _loc3_.sdamage = 0;
   }
   function faHit(obj)
   {
      var _loc3_ = !obj.param.target ? lol.core.player.Gamer.ID : obj.param.target;
      var _loc4_ = !obj.param.dmg ? 0 : obj.param.dmg;
      var _loc5_ = !obj.param.sdmg ? 0 : obj.param.sdmg;
      var _loc6_ = Boolean(obj.param.crit);
      this.curFireEvent.hitTarget(_loc3_,_loc4_,_loc5_,_loc6_);
      var _loc8_ = this.getWalker(this.curFireEvent.gunnerID);
      _loc8_.targetID = _loc3_;
      var _loc7_ = this.getWalker(_loc3_);
      _loc7_.damageWalker(_loc4_,_loc5_);
      if(this.curFireEvent.gunnerID == lol.core.player.Gamer.ID || _loc3_ == lol.core.player.Gamer.ID)
      {
         this.dispatchEvent({type:"startExitTimer"});
      }
   }
   function faWall(obj)
   {
      var _loc2_ = obj.param.hex;
      this.curFireEvent.hitWall(_loc2_);
   }
   function faMiss(obj)
   {
      var _loc3_ = obj.param.x;
      var _loc2_ = obj.param.y;
      this.curFireEvent.miss(_loc3_,_loc2_);
   }
   function caHit(obj)
   {
      var _loc2_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc5_ = !obj.param.target ? lol.core.player.Gamer.ID : obj.param.target;
      var _loc6_ = !obj.param.dmg ? 0 : obj.param.dmg;
      var _loc7_ = !obj.param.sdmg ? 0 : obj.param.sdmg;
      var _loc8_ = Boolean(obj.param.crit);
      var _loc10_ = this.getPlayer(_loc2_).walker;
      var _loc9_ = this.getPlayer(_loc5_).walker;
      var _loc11_ = this.getDirection(_loc10_.numPos,_loc9_.numPos);
      this.aiming(_loc2_,_loc11_,1);
      this.curFireEvent = new lol.events.FireEvent();
      this.curFireEvent.gunnerID = _loc2_;
      this.curFireEvent.hitTarget(_loc5_,_loc6_,_loc7_,_loc8_);
      this.dispatchEvent(this.curFireEvent);
      this.curFireEvent = null;
      var _loc4_;
      _loc4_ = {};
      _loc4_.health_damage = _loc6_;
      _loc4_.stamina_damage = _loc7_;
      _loc4_.nickname = lol.core.Master.getInstance().getPlayer(_loc2_).playerInfo.name;
      _loc4_.nickname2 = lol.core.Master.getInstance().getPlayer(_loc5_).playerInfo.name;
      _loc4_.itemname = this.master.getPlayer(_loc2_).equipment.primaryItem;
      lol.services.GameEvents.addEvent(lol.services.GameEvents.CA_DAMAGE,_loc4_);
      this.damage(_loc5_,_loc6_,_loc7_);
      if(_loc2_ == lol.core.player.Gamer.ID || _loc5_ == lol.core.player.Gamer.ID)
      {
         this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.STRIKE,_loc2_));
         this.dispatchEvent({type:"startExitTimer"});
      }
   }
   function caMiss(obj)
   {
      var _loc2_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc3_ = obj.param.hex;
      var _loc5_ = lol.core.location.LocWalker(this.getPlayer(_loc2_).walker);
      var _loc6_ = this.getDirection(_loc5_.numPos,_loc3_);
      this.aiming(_loc2_,_loc6_,1);
      this.curFireEvent = new lol.events.FireEvent();
      this.curFireEvent.gunnerID = _loc2_;
      this.curFireEvent.hitWall(_loc3_);
      this.dispatchEvent(this.curFireEvent);
      this.curFireEvent = null;
      this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.STRIKE,_loc2_));
   }
   function heal(obj)
   {
      var _loc6_ = this.getPlayer(obj.param.id);
      var _loc2_ = this.getPlayer(obj.param.target);
      var _loc5_ = obj.param.hp;
      var _loc4_ = obj.param.sp;
      _loc2_.health = _loc5_;
      _loc2_.stamina = _loc4_;
   }
   function damage(id, dmg, sdmg, crit)
   {
      var _loc2_ = this.master.getPlayer(id);
      if(dmg)
      {
         _loc2_.damage(dmg,Boolean(crit));
      }
      if(sdmg)
      {
         _loc2_.sdamage(sdmg,Boolean(crit));
      }
   }
   function setEnemy(id)
   {
      this.playerList[id].walker.relation = "enemy";
      this.dispatchEvent({type:"enemy",player:this.playerList[id]});
   }
   function exitLocation()
   {
      this.exLocPan = lol.core.SceneShifter.openNewWindow("exitLoc");
      this.exLocPan.content.addEventListener("exitLoc",this);
   }
   function exitLoc(obj)
   {
      this.exLocPan.content.removeEventListener("exitLoc",this);
      lol.core.SceneShifter.closeWindow("exitLoc");
      obj.target.removeEventListener("exitLoc",this);
      if(obj.where == "gmap")
      {
         this.master.changeWorld();
      }
      else if(obj.where == "loc")
      {
         this.master.changeWorld(1);
      }
   }
   function ss_loot(obj)
   {
      var _loc3_ = obj.param.s_status;
      var _loc2_ = obj.param.hex;
      if(_loc3_ == 1)
      {
         this.createLootBags(_loc2_);
      }
      else
      {
         this.removeLootBags(_loc2_);
      }
   }
   function createLootBags(hex)
   {
      var _loc2_ = 0;
      while(_loc2_ < hex.length)
      {
         this.addLootBag(hex[_loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function removeLootBags(hex)
   {
      var _loc2_ = 0;
      while(_loc2_ < hex.length)
      {
         this.removeLootBag(hex[_loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function addLootBag(pos)
   {
      this.lootBagList.push(pos);
      this.dispatchEvent({type:"addBag",pos:pos});
   }
   function removeLootBag(pos)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.lootBagList.length)
      {
         if(this.lootBagList[_loc2_] == pos)
         {
            this.lootBagList.splice(_loc2_,1);
            this.dispatchEvent({type:"removeBag",pos:pos});
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function findPath(cell0, cell1)
   {
      var _loc2_ = this.findPath_old(cell0,cell1);
      return _loc2_;
   }
   function findPath_old(cell0, cell1)
   {
      var _loc13_ = cell0.gx;
      var _loc12_ = cell0.gy;
      var _loc11_ = cell1.gx;
      var _loc10_ = cell1.gy;
      var _loc17_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.PATH_FINDING);
      var _loc14_;
      var _loc15_;
      if(_loc17_)
      {
         _loc14_ = lol.core.Master.getInstance().currentLocation.locInfo.width;
         _loc15_ = lol.core.Master.getInstance().currentLocation.locInfo.height;
      }
      else
      {
         _loc14_ = 30;
         _loc15_ = 40;
      }
      var _loc9_ = Math.floor(0.5 * (_loc11_ + _loc13_ - _loc14_));
      var _loc8_ = Math.floor(0.5 * (_loc10_ + _loc12_ - _loc15_));
      _loc9_ = _loc9_ >= 0 ? _loc9_ : 0;
      _loc8_ = _loc8_ >= 0 ? _loc8_ : 0;
      _loc13_ -= _loc9_;
      _loc12_ -= _loc8_;
      _loc11_ -= _loc9_;
      _loc10_ -= _loc8_;
      var _loc21_ = this.getCellFromGrid(_loc11_,_loc10_);
      var _loc16_;
      var _loc18_;
      var _loc6_;
      var _loc7_;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      var _loc3_;
      if(Math.abs(_loc11_ - _loc13_) > _loc14_ || Math.abs(_loc10_ - _loc12_) > _loc15_)
      {
         _loc16_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc16_.label = "Cлишком далеко";
         _loc18_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
      else
      {
         _loc6_ = this.locationGrid.searchWay(_loc13_,_loc12_,_loc11_,_loc10_,_loc9_,_loc8_,_loc14_,_loc15_);
         _loc7_ = new Array();
         _loc2_ = 0;
         while(_loc2_ < _loc6_.length)
         {
            _loc5_ = _loc6_[_loc2_][0];
            _loc4_ = _loc6_[_loc2_][1];
            if(_loc5_ != undefined && _loc4_ != undefined)
            {
               _loc3_ = this.locationGrid.getCellFromGrid(_loc5_,_loc4_);
               if(_loc3_ == undefined)
               {
                  return null;
               }
               if(!this.locationGrid.isUnreachible(_loc3_))
               {
                  _loc7_.push(_loc3_);
               }
            }
            _loc2_ = _loc2_ + 1;
         }
         if(_loc7_.length > 0)
         {
            return _loc7_;
         }
         _loc16_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc16_.label = "Невозможно пройти";
         _loc18_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
   }
   function findPath_new(cell0, cell1)
   {
      var _loc13_ = cell0.gx;
      var _loc12_ = cell0.gy;
      var _loc11_ = cell1.gx;
      var _loc10_ = cell1.gy;
      var _loc21_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.PATH_FINDING);
      var _loc14_;
      var _loc15_;
      _loc14_ = 30;
      _loc15_ = 40;
      var _loc9_ = Math.floor(0.5 * (_loc11_ + _loc13_ - _loc14_));
      var _loc8_ = Math.floor(0.5 * (_loc10_ + _loc12_ - _loc15_));
      _loc9_ = _loc9_ >= 0 ? _loc9_ : 0;
      _loc8_ = _loc8_ >= 0 ? _loc8_ : 0;
      _loc13_ -= _loc9_;
      _loc12_ -= _loc8_;
      _loc11_ -= _loc9_;
      _loc10_ -= _loc8_;
      var _loc20_ = this.getCellFromGrid(_loc11_,_loc10_);
      var _loc16_;
      var _loc17_;
      var _loc6_;
      var _loc7_;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      var _loc3_;
      if(Math.abs(_loc11_ - _loc13_) > _loc14_ || Math.abs(_loc10_ - _loc12_) > _loc15_)
      {
         _loc16_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc16_.label = "Cлишком далеко";
         _loc17_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
      else
      {
         _loc6_ = this.locationGrid.searchWay(_loc13_,_loc12_,_loc11_,_loc10_,_loc9_,_loc8_,_loc14_,_loc15_);
         _loc7_ = new Array();
         _loc2_ = 0;
         while(_loc2_ < _loc6_.length)
         {
            _loc5_ = _loc6_[_loc2_][0];
            _loc4_ = _loc6_[_loc2_][1];
            if(_loc5_ != undefined && _loc4_ != undefined)
            {
               _loc3_ = this.locationGrid.getCellFromGrid(_loc5_,_loc4_);
               if(_loc3_ == undefined)
               {
                  return null;
               }
               if(!this.locationGrid.isUnreachible(_loc3_))
               {
                  _loc7_.push(_loc3_);
               }
            }
            _loc2_ = _loc2_ + 1;
         }
         if(_loc7_.length > 0)
         {
            return _loc7_;
         }
         _loc16_ = lol.core.SceneShifter.openNewAlert("topSimple");
         _loc16_.label = "Невозможно пройти";
         _loc17_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.closeAlert,2000,"topQuery");
      }
   }
   function getCellFromNumber(num)
   {
      return this.locationGrid.getCellFromNumber(num);
   }
   function getCellFromReal(rx, ry)
   {
      return this.locationGrid.getCellFromReal(rx,ry);
   }
   function getCellFromGrid(gx, gy)
   {
      return this.locationGrid.getCellFromGrid(gx,gy);
   }
   function getDirection(pos0, pos1)
   {
      return this.locationGrid.getDirection(pos0,pos1);
   }
   function getSiblings(cell)
   {
      return this.locationGrid.getSiblings(cell);
   }
   function isSiblings(cell1, cell2)
   {
      return this.locationGrid.isSiblings(cell1,cell2);
   }
   function kill()
   {
      this.XMC.removeEventListener("lch",this);
      this.XMC.removeEventListener("userMove",this);
      this.XMC.removeEventListener("breakMv",this);
      this.XMC.removeEventListener("cor_pos",this);
      this.XMC.removeEventListener("cmdAck",this);
      this.XMC.removeEventListener("fireAck",this);
      this.XMC.removeEventListener("ss_loot",this);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.moveCmdAck);
      this.master.removeEventListener("userUpdate",this);
      this.XMC.removeEventListener("lch",this);
      this.XMC.removeEventListener("prepare",this);
      this.XMC.removeEventListener("userMove",this);
      this.XMC.removeEventListener("breakMv",this);
      this.XMC.removeEventListener("faAim",this);
      this.XMC.removeEventListener("faShot",this);
      this.XMC.removeEventListener("faHit",this);
      this.XMC.removeEventListener("faWall",this);
      this.XMC.removeEventListener("faMiss",this);
      this.XMC.removeEventListener("heal",this);
      this.XMC.removeEventListener("caHit",this);
      this.XMC.removeEventListener("caMiss",this);
      for(var _loc4_ in this.playerList)
      {
         this.removePlayer(_loc4_);
      }
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.lootBagList.length)
      {
         _loc3_ = this.lootBagList[_loc2_];
         this.removeLootBag(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      delete this.locationGrid;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("Location_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function get gamer()
   {
      return this.master.gamer;
   }
   function getNum(arr, id)
   {
      var _loc1_ = 0;
      while(_loc1_ < arr.length)
      {
         if(arr[_loc1_] == id)
         {
            return _loc1_;
         }
         _loc1_ = _loc1_ + 1;
      }
   }
   function get locationName()
   {
      var _loc2_ = this.locInfo.locationName;
      var _loc3_;
      if(this.locInfo.geoID)
      {
         _loc3_ = lol.utils.LocIdToCoordinate.getValue(this.locInfo.geoID);
         _loc2_ += " " + _loc3_.x + ":" + _loc3_.y;
      }
      return _loc2_;
   }
   function get isSubLocation()
   {
      var _loc2_ = lol.utils.LocIdToCoordinate.getValue(this.locInfo.geoID);
      if(_loc2_.z == 0)
      {
         return false;
      }
      return true;
   }
   function isBGLocation()
   {
      var _loc2_ = this.locInfo.geoID;
      if((_loc2_ >> 31 & 1) > 0)
      {
         return true;
      }
      return false;
   }
}
