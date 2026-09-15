class lol.core.location.DisplayLocScene extends MovieClip
{
   var areaInterval;
   var bg_mc;
   var core_mc;
   var currentLocation;
   var cursorManager;
   var depthManager;
   var dispatchEvent;
   var displayList;
   var fireAckReport;
   var helperObjects;
   var helpers_mc;
   var lBuilder;
   var lootBagList;
   var master;
   var missFlag;
   var obst_mc;
   var playerList;
   var roof_mc;
   var spt;
   var spt_int;
   var viewArea;
   var leftRightIndention = 50;
   var topBottomIndention = 100;
   function DisplayLocScene()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.master = lol.core.Master.getInstance();
      this.currentLocation = this.master.currentLocation;
      lol.core.SceneShifter._ref.addEventListener("sceneEnabled",this);
      this.locLoaded();
   }
   function init()
   {
      this.currentLocation.addEventListener("addPlayer",this);
      this.currentLocation.addEventListener("removePlayer",this);
      this.currentLocation.addEventListener("position",this);
      this.currentLocation.addEventListener("finishPart",this);
      this.currentLocation.addEventListener("finishMove",this);
      this.master.addEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.userStateUpdate);
      this.currentLocation.addEventListener("aim",this);
      this.currentLocation.addEventListener("fireAck",this);
      this.currentLocation.addEventListener("dead",this);
      this.currentLocation.addEventListener("enemy",this);
      this.currentLocation.addEventListener("addBag",this);
      this.currentLocation.addEventListener("removeBag",this);
      var _loc2_ = this.master.gamer;
      _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.gamerUpdate);
      _loc2_.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.gamerUpdate);
      this.bg_mc = lol.core.location.DisplayLocBackground(lol.utils.MCFabric.create(lol.core.location.DisplayLocBackground,this,"bg_mc",0));
      this.core_mc = this.createEmptyMovieClip("core_mc",1);
      this.roof_mc = this.createEmptyMovieClip("roof_mc",2);
      this.obst_mc = this.createEmptyMovieClip("obst_mc",3);
      this.helpers_mc = this.createEmptyMovieClip("helpers_mc",4);
      this.cursorManager = new lol.core.location.CursorManager(this);
      this.cursorManager.activate(true);
      this.displayList = new Array();
      this.playerList = new Array();
      this.helperObjects = new Array();
      this.master = lol.core.Master.getInstance();
      this.master.chat.addEventListener("refresh",this,this.chatRefreshed);
      this.setViewArea();
      this.areaInterval = setInterval(this,"showArea",100);
   }
   function chatRefreshed(disObj)
   {
      var _loc4_;
      var _loc5_;
      var _loc3_;
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_MSGS_UNDER_HEAD))
      {
         _loc4_ = disObj.logArr[disObj.logArr.length - 1].fromID;
         _loc5_ = disObj.logArr[disObj.logArr.length - 1].mess;
         if(_loc4_ != undefined)
         {
            _loc3_ = this.helperObjects[_loc4_];
            if(_loc3_ != undefined)
            {
               _loc3_.showPhrase(_loc5_);
            }
         }
      }
   }
   function locLoaded()
   {
      this.init();
      this.lBuilder = new lol.core.location.LocBuilder(this);
      this.lBuilder.buildScene();
      this.depthManager = new lol.core.location.LDepthManager(this);
      this.depthManager.zSort();
      this.makeCast();
      this.initBags();
   }
   function makeCast()
   {
      var _loc6_ = this.currentLocation.playerList;
      var _loc2_;
      var _loc3_;
      var _loc5_;
      var _loc4_;
      var _loc7_;
      for(var _loc8_ in _loc6_)
      {
         _loc2_ = _loc6_[_loc8_];
         _loc3_ = _loc2_.id;
         _loc5_ = _loc2_.walker.numPos;
         if(!this.playerList[_loc3_])
         {
            _loc4_ = this.addPlayer(_loc3_,_loc5_);
            if(_loc2_ == this.master.gamer)
            {
               _loc7_ = new lol.utils.Timeout(this,this.centerWalker,50,_loc4_,false);
               this.master.gamer.equipment.addEventListener("changePrimary",this);
            }
         }
      }
   }
   function addPlayer()
   {
      var _loc9_;
      var _loc4_;
      var _loc5_;
      if(typeof arguments[0] == "object")
      {
         _loc9_ = arguments[0].player;
         _loc4_ = arguments[0].player.id;
         _loc5_ = arguments[0].player.walker.numPos;
      }
      else
      {
         _loc4_ = arguments[0];
         _loc5_ = arguments[1];
         _loc9_ = this.master.getPlayer(_loc4_);
      }
      var _loc8_ = this.getCellFromNumber(_loc5_);
      var _loc7_ = this.core_mc.getNextHighestDepth();
      var _loc3_ = lol.core.location.Char(this.core_mc.attachMovie("testLocChar","walker" + _loc4_,_loc7_));
      _loc3_.id = _loc4_;
      this.cursorManager.addFocus(_loc3_,_loc3_.cont_mc,true);
      this.playerList[_loc4_] = _loc3_;
      this.addNick(_loc4_,_loc5_);
      if(_loc9_.walker.relation == "enemy")
      {
         this.enemy({player:_loc9_});
      }
      var _loc6_ = new lol.core.location.SceneObject("dynamic");
      _loc6_.sprite = _loc3_;
      _loc6_.type = "dynamic";
      this.displayList.push(_loc6_);
      _loc3_.scObj = _loc6_;
      this.placeSceneObject(_loc3_,_loc5_);
      return _loc3_;
   }
   function addNick(id)
   {
      var _loc4_ = this.helpers_mc.getNextHighestDepth();
      var _loc2_ = lol.core.location.CharInfo(this.helpers_mc.attachMovie("charInfo","ci" + id,_loc4_));
      this.helperObjects[id] = _loc2_;
      _loc2_.setNick(id);
   }
   function removePlayer()
   {
      var _loc3_;
      var _loc5_;
      if(typeof arguments[0] == "object")
      {
         _loc3_ = arguments[0].player.id;
         _loc5_ = arguments[0].player.numPos;
      }
      else
      {
         _loc3_ = arguments[0];
         _loc5_ = this.playerList[_loc3_].pos;
      }
      var _loc4_ = this.getWalker(_loc3_);
      var _loc6_ = this.playerList[_loc3_].cell;
      _loc6_.outFromCell(_loc4_);
      this.cursorManager.removeFocus(_loc4_);
      this.depthManager.removeObject(_loc4_);
      this.helperObjects[_loc3_].kill();
      this.helperObjects[_loc3_].removeMovieClip();
      this.helperObjects[_loc3_] = null;
      var _loc7_;
      if(_loc4_.behavior == lol.core.location.Char.DIE && _loc3_ != lol.core.player.Gamer.ID)
      {
         _loc7_ = new lol.utils.Timeout(_loc4_,_loc4_.fadeDie,2000);
      }
      else
      {
         _loc4_.fadeDie();
      }
   }
   function getWalker(id)
   {
      return this.playerList[id];
   }
   function placeSceneObject(obj_mc, pos)
   {
      var _loc2_ = this.getCellFromNumber(pos);
      this.placeWalker(obj_mc,_loc2_.rx,_loc2_.ry);
      var _loc3_ = obj_mc.scObj;
      this.depthManager.moveObject(_loc3_,_loc2_);
      this.depthManager.sortDisplayList(_loc3_);
      this.alwaysShowNPC(obj_mc,_loc2_);
   }
   function moveSceneObject(obj_mc, pos)
   {
      var _loc2_ = this.getCellFromNumber(pos);
      this.placeWalker(obj_mc,_loc2_.rx,_loc2_.ry);
      var _loc4_ = obj_mc.scObj;
      this.depthManager.moveObject(_loc4_,_loc2_);
      var _loc8_ = - this._parent._x;
      var _loc6_ = - this._parent._y;
      var _loc9_ = this.viewArea.width;
      var _loc7_ = this.viewArea.height;
      var _loc5_ = new flash.geom.Rectangle(_loc8_,_loc6_,_loc9_,_loc7_);
      if(_loc5_.contains(obj_mc._x,obj_mc._y))
      {
         this.depthManager.sortDisplayList(_loc4_);
      }
      this.alwaysShowNPC(obj_mc,_loc2_);
   }
   function alwaysShowNPC(mc, cell)
   {
      var _loc4_ = true;
      var _loc3_ = this.currentLocation.getPlayer(mc.id);
      if(mc instanceof lol.core.location.Char && !(_loc3_ instanceof lol.core.player.NPC))
      {
         if(cell.alwaysBusy)
         {
            lol.core.location.Char(mc).activate(false);
            lol.core.location.Char(mc).locked = true;
            this.cursorManager.activateFocus(mc,false);
         }
         else
         {
            lol.core.location.Char(mc).locked = false;
            lol.core.location.Char(mc).activate(true);
            this.cursorManager.activateFocus(mc,true);
         }
      }
   }
   function placeWalker(walker_mc, x, y)
   {
      this.placeObject(walker_mc,x,y);
      var _loc2_ = walker_mc.id;
      this.helperObjects[_loc2_]._x = walker_mc._x;
      this.helperObjects[_loc2_]._y = walker_mc._y - 100;
   }
   function placeObject(obj_mc, ax, ay)
   {
      var _loc1_ = lol.core.location.LocDeclaration.abstractToReal({x:ax,y:ay});
      obj_mc._x = _loc1_.x;
      obj_mc._y = _loc1_.y;
   }
   function movePlayer(c)
   {
      var _loc2_ = c;
      if(!_loc2_)
      {
         _loc2_ = this.getCellFromReal(this._xmouse,this._ymouse);
      }
      this.currentLocation.movePlayer(_loc2_);
   }
   function position(obj)
   {
      var _loc2_ = obj.walker;
      var _loc4_ = _loc2_.id;
      var _loc6_ = _loc2_.x;
      var _loc5_ = _loc2_.y;
      var _loc3_ = this.getWalker(_loc4_);
      this.placeWalker(_loc3_,_loc6_,_loc5_);
      _loc3_.direction = _loc2_.direction;
      _loc3_.behavior = lol.core.location.Char.RUN;
   }
   function finishPart(obj)
   {
      var _loc2_ = obj.walker;
      var _loc3_ = _loc2_.id;
      var _loc4_ = _loc2_.numPos;
      var _loc5_ = this.getWalker(_loc3_);
      this.checkCollision(_loc3_);
      this.moveSceneObject(_loc5_,_loc4_);
      if(_loc2_ == this.currentLocation.gamer.walker)
      {
      }
      var _loc6_ = this.helperObjects[_loc3_];
   }
   function finishMove(obj)
   {
      var _loc2_ = obj.walker;
      var _loc3_ = _loc2_.id;
      var _loc5_ = _loc2_.pos;
      var _loc4_ = this.getWalker(_loc3_);
      _loc4_.behavior = lol.core.location.Char.STAND;
      if(_loc2_ == this.currentLocation.gamer.walker)
      {
      }
   }
   function aim(obj)
   {
      var _loc3_ = obj.aim;
      var _loc2_ = this.getWalker(_loc3_);
      var _loc5_ = !obj.ang ? _loc2_.direction : obj.ang;
      _loc2_.direction = _loc5_;
      var _loc6_ = this.master.getPlayer(_loc3_).walker;
      _loc6_.direction = _loc5_;
      _loc2_.fireCount = obj.num_shots;
      _loc2_.behavior = lol.core.location.Char.FIRE_IN;
   }
   function fireAck(fireEvt)
   {
      var _loc7_ = fireEvt.access;
      var _loc2_ = this.getWalker(fireEvt.gunnerID);
      var _loc3_;
      var _loc5_;
      var _loc6_;
      if(_loc7_)
      {
         _loc2_.burstArr.push(fireEvt);
         this.addFireAckReport(fireEvt);
         if(_loc2_.burstArr.length >= _loc2_.fireCount)
         {
            _loc3_ = this.master.getPlayer(_loc2_.id).equipment.primaryItem;
            if(_loc3_ instanceof lol.core.objects.FireArm)
            {
               _loc5_ = lol.core.objects.FireArm(_loc3_);
               _loc6_ = _loc5_.getProp("weapon_type");
               if(_loc6_ == lol.core.objects.FireArm.SHOTGUN)
               {
                  _loc2_.fireCount = 1;
                  _loc2_.addEventListener("finalFrame",this,this.shotgunFireAck);
               }
               else
               {
                  _loc2_.addEventListener("finalFrame",this,this.busrtFireAck);
               }
            }
            else
            {
               _loc2_.addEventListener("finalFrame",this,this.busrtFireAck);
            }
            _loc2_.behavior = lol.core.location.Char.FIRE;
            _loc2_.fireCount = 1;
         }
      }
      else
      {
         _loc2_.behavior = lol.core.location.Char.FIRE_OUT;
      }
   }
   function shotgunFireAck(obj)
   {
      var _loc3_ = obj.target;
      var _loc4_;
      var _loc2_;
      if(obj.data == lol.core.location.Char.FIRE)
      {
         _loc3_.removeEventListener("finalFrame",this,this.shotgunFireAck);
         _loc2_ = 0;
         while(_loc2_ < _loc3_.burstArr.length)
         {
            _loc4_ = _loc3_.burstArr[_loc2_];
            this.applyFireAck(_loc4_);
            _loc2_ = _loc2_ + 1;
         }
         _loc3_.burstArr = new Array();
         this.showFireAckReport();
         lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.SHOTGUN_FIRE);
      }
      else
      {
         _loc3_.removeEventListener("finalFrame",this,this.shotgunFireAck);
         _loc3_.burstArr = new Array();
      }
   }
   function busrtFireAck(obj)
   {
      var _loc2_ = obj.target;
      var _loc5_;
      var _loc4_;
      var _loc3_;
      var _loc6_;
      var _loc7_;
      if(obj.data == lol.core.location.Char.FIRE)
      {
         _loc5_ = _loc2_.burstArr.shift();
         _loc4_ = lol.events.FireEvent(_loc5_);
         this.applyFireAck(_loc4_);
         _loc3_ = this.master.getPlayer(_loc2_.id).equipment.primaryItem;
         if(_loc3_ instanceof lol.core.objects.FireArm)
         {
            _loc6_ = lol.core.objects.FireArm(_loc3_);
            _loc7_ = _loc6_.getProp("weapon_type");
            switch(_loc7_)
            {
               case lol.core.objects.FireArm.PISTOL:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.PISTOL_FIRE);
                  break;
               case lol.core.objects.FireArm.RIFLE:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.RIFLE_FIRE);
                  break;
               case lol.core.objects.FireArm.SHOTGUN:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.SHOTGUN_FIRE);
                  break;
               case lol.core.objects.FireArm.SMG:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.SMG_FIRE);
                  break;
               case lol.core.objects.FireArm.MACHINEGUN:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.MACHINEGUN_FIRE);
                  break;
               case lol.core.objects.FireArm.ASSAULT:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.ASSAULT_FIRE);
                  break;
               default:
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.FIREARM_FIRE);
            }
         }
         else if(_loc3_ instanceof lol.core.objects.MeleeWeapon)
         {
            if(_loc3_.animation_type == "fist")
            {
               if(_loc4_.successful)
               {
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.FIST_HIT);
               }
               else
               {
                  lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.FIST_MISS);
               }
            }
            else if(_loc4_.successful)
            {
               lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.KNIFE_OK);
            }
            else
            {
               lol.sound.SoundManager.getInstance().playEventSound(lol.sound.SoundEvent.KNIFE_MISS);
            }
         }
         if(_loc2_.burstArr.length == 0)
         {
            _loc2_.removeEventListener("finalFrame",this,this.busrtFireAck);
            _loc2_.burstArr = new Array();
            this.showFireAckReport();
         }
      }
      else
      {
         _loc2_.removeEventListener("finalFrame",this,this.busrtFireAck);
         _loc2_.burstArr = new Array();
      }
   }
   function applyFireAck(fireEvt)
   {
      var _loc5_;
      var _loc2_;
      var _loc3_;
      while(fireEvt.hits.length)
      {
         _loc5_ = fireEvt.hits.shift();
         _loc2_ = lol.core.location.FireAck(_loc5_);
         if(_loc2_.type == lol.core.location.FireAck.POINT)
         {
            _loc3_ = this.hitPoint(_loc2_);
         }
         else if(_loc2_.type == lol.core.location.FireAck.WALL)
         {
            _loc3_ = this.hitWall(_loc2_);
         }
         else if(_loc2_.type == lol.core.location.FireAck.TARGET)
         {
            _loc3_ = this.hitTarget(_loc2_);
         }
      }
      if(fireEvt.shot)
      {
         this.traceShot(fireEvt.gunnerID,_loc3_);
      }
   }
   function hitPoint(fAck)
   {
      var _loc3_ = this.helpers_mc.getNextHighestDepth();
      var _loc2_ = this.helpers_mc.attachMovie("bum","bum" + _loc3_,_loc3_);
      var _loc5_ = 0.4330127018922193;
      var _loc4_ = lol.core.location.LocationGrid.cellW;
      var _loc7_ = _loc4_ * fAck.x;
      var _loc6_ = _loc4_ * fAck.y * 20 / 46;
      _loc2_._x = _loc7_;
      _loc2_._y = _loc6_;
      return {x:_loc2_._x,y:_loc2_._y};
   }
   function hitWall(fAck)
   {
      var _loc3_ = this.helpers_mc.getNextHighestDepth();
      var _loc2_ = this.helpers_mc.attachMovie("bum","bum" + _loc3_,_loc3_);
      var _loc4_ = this.getCellFromNumber(fAck.hex);
      this.placeObject(_loc2_,_loc4_.rx,_loc4_.ry);
      return {x:_loc2_._x,y:_loc2_._y};
   }
   function hitTarget(fAck)
   {
      var _loc2_ = this.getWalker(fAck.targetID);
      _loc2_.behavior = lol.core.location.Char.DAMAGE;
      var _loc5_ = this.helperObjects[fAck.targetID];
      var _loc4_ = _loc2_._x;
      var _loc3_ = _loc2_._y - 50;
      return {x:_loc4_,y:_loc3_};
   }
   function traceShot(gunnerID, fPos)
   {
      var _loc2_ = this.getWalker(gunnerID);
      var _loc5_ = fPos.x + Math.random() * 20 - 10;
      var _loc4_ = fPos.y + Math.random() * 20 - 10;
      var _loc3_ = new lol.fx.ShotTrace();
      _loc3_.traceShot(this.helpers_mc,{x:_loc2_._x,y:_loc2_._y - 50},{x:_loc5_,y:_loc4_});
   }
   function addFireAckReport(fireEvt)
   {
      if(!this.fireAckReport)
      {
         this.fireAckReport = new Array();
      }
      var _loc6_ = fireEvt.gunnerID;
      var _loc3_;
      var _loc8_ = fireEvt.hits.length;
      var _loc2_;
      var _loc4_;
      _loc3_ = 0;
      while(_loc3_ < _loc8_)
      {
         _loc2_ = new Object();
         _loc4_ = fireEvt.hits[_loc3_];
         if(_loc4_.type == lol.core.location.FireAck.POINT)
         {
            if(!this.missFlag && !fireEvt.successful)
            {
               this.missFlag = true;
               _loc2_.id = lol.services.GameEvents.MISS;
               _loc2_.param = {nickname:lol.core.Master.getInstance().getPlayer(_loc6_).playerInfo.name};
               this.fireAckReport.push(_loc2_);
            }
         }
         else if(_loc4_.type == lol.core.location.FireAck.WALL)
         {
            if(!this.missFlag && !fireEvt.successful)
            {
               this.missFlag = true;
               _loc2_.id = lol.services.GameEvents.MISS;
               _loc2_.param = {nickname:lol.core.Master.getInstance().getPlayer(_loc6_).playerInfo.name};
               this.fireAckReport.push(_loc2_);
            }
         }
         else if(_loc4_.type == lol.core.location.FireAck.TARGET)
         {
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function showFireAckReport()
   {
      var _loc2_;
      var _loc4_ = this.fireAckReport.length;
      _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_)
      {
         _loc3_ = this.fireAckReport[_loc2_];
         lol.services.GameEvents.addEvent(_loc3_.id,_loc3_.param);
         _loc2_ = _loc2_ + 1;
      }
      this.missFlag = false;
      this.fireAckReport = null;
   }
   function dead(obj)
   {
      var _loc2_ = obj.dead;
      this.helperObjects[_loc2_].kill();
      this.helperObjects[_loc2_].removeMovieClip();
      this.helperObjects[_loc2_] = null;
      var _loc3_ = !_loc2_ ? this.gamer_mc : this.getWalker(_loc2_);
      _loc3_.behavior = lol.core.location.Char.DIE;
      var _loc4_ = this.cursorManager.sfManager.getFocus(_loc3_);
      _loc4_.flare(false);
      if(_loc2_ != lol.core.player.Gamer.ID)
      {
      }
   }
   function userStateUpdate(obj)
   {
      var _loc2_ = obj.player;
      var _loc5_ = _loc2_.id;
      var _loc4_ = 100 * _loc2_.health / _loc2_.maxHealth;
      var _loc6_ = 100 * _loc2_.stamina / _loc2_.maxStamina;
      var _loc3_ = this.helperObjects[_loc5_];
      _loc3_.showHealth(_loc4_,_loc2_.health);
      _loc3_.showStamina(_loc6_,_loc2_.stamina);
   }
   function gamerUpdate(obj)
   {
      var _loc2_ = this.master.gamer;
      var _loc5_ = _loc2_.id;
      var _loc4_ = 100 * _loc2_.health / _loc2_.maxHealth;
      var _loc6_ = 100 * _loc2_.stamina / _loc2_.maxStamina;
      var _loc3_ = this.helperObjects[_loc5_];
      _loc3_.showHealth(_loc4_,_loc2_.health);
      _loc3_.showStamina(_loc6_,_loc2_.stamina);
   }
   function centerWalker(walker, how)
   {
      var _loc4_ = new Object();
      _loc4_.x = walker._x;
      _loc4_.y = walker._y;
      this.dispatchEvent({type:"centerPoint",point:_loc4_,how:how});
   }
   function checkCollision(id)
   {
      var _loc2_ = this.getWalker(id);
      var _loc4_ = _loc2_._x;
      var _loc3_ = _loc2_._y;
      this.showCollision(_loc4_,_loc3_,_loc2_);
   }
   function showCollision(X, Y, walker_mc)
   {
   }
   function enemy(obj)
   {
      var _loc2_ = obj.player.id;
      var _loc3_ = this.getWalker(_loc2_);
      this.cursorManager.sfManager.setColor(_loc3_,"enemy");
      var _loc4_ = this.helperObjects[_loc2_];
      _loc4_.relation = "enemy";
   }
   function changePrimary(obj)
   {
   }
   function initBags()
   {
      this.lootBagList = new Array();
      var _loc3_ = this.currentLocation.lootBagList;
      var _loc2_ = 0;
      var _loc4_;
      while(_loc2_ < _loc3_.length)
      {
         _loc4_ = _loc3_[_loc2_];
         this.addBag({pos:_loc4_});
         _loc2_ = _loc2_ + 1;
      }
   }
   function addBag(obj)
   {
      var _loc3_ = obj.pos;
      var _loc7_ = this.getCellFromNumber(_loc3_);
      var _loc5_ = this.core_mc.getNextHighestDepth();
      var _loc2_ = this.core_mc.attachMovie("lootBag_mc","lootBag_" + _loc3_,_loc5_);
      _loc2_.pos = _loc3_;
      var _loc6_ = new lol.core.location.LootBag(_loc3_);
      _loc2_.driver = _loc6_;
      this.lootBagList.push(_loc2_);
      this.cursorManager.addFocus(_loc2_,_loc2_.cont_mc,false);
      this.cursorManager.sfManager.setColor(_loc2_);
      var _loc4_ = new lol.core.location.SceneObject("dynamic");
      _loc4_.sprite = _loc2_;
      _loc4_.type = "dynamic";
      this.displayList.push(_loc4_);
      _loc2_.scObj = _loc4_;
      this.placeSceneObject(_loc2_,_loc7_.num);
   }
   function removeBag(obj)
   {
      var _loc4_ = obj.pos;
      var _loc3_;
      var _loc2_ = 0;
      while(_loc2_ < this.lootBagList.length)
      {
         if(this.lootBagList[_loc2_].pos == _loc4_)
         {
            _loc3_ = this.lootBagList[_loc2_];
            this.depthManager.removeObject(_loc3_);
            this.cursorManager.removeFocus(_loc3_);
            _loc3_.removeMovieClip();
            this.lootBagList.splice(_loc2_,1);
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getCellFromNumber(num)
   {
      return this.currentLocation.getCellFromNumber(num);
   }
   function getCellFromReal(rx, ry)
   {
      return this.currentLocation.getCellFromReal(rx,ry);
   }
   function getCellFromGrid(gx, gy)
   {
      return this.currentLocation.getCellFromGrid(gx,gy);
   }
   function getDirection(pos0, pos1)
   {
      return this.currentLocation.getDirection(pos0,pos1);
   }
   function getSiblings(cell)
   {
      return this.currentLocation.getSiblings(cell);
   }
   function isSiblings(cell1, cell2)
   {
      return this.currentLocation.isSiblings(cell1,cell2);
   }
   function setViewArea(w, h)
   {
      this.viewArea = new Object();
      this.viewArea.width = !w ? 1000 : w;
      this.viewArea.height = !h ? 700 : h;
   }
   function drawViewArea()
   {
      this.helpers_mc.clear();
      var _loc4_ = - this._parent._x;
      var _loc2_ = - this._parent._y;
      var _loc5_ = this.viewArea.width;
      var _loc3_ = this.viewArea.height;
      lol.utils.Draw.drawFillRect(this.helpers_mc,_loc4_,_loc2_,_loc5_,_loc3_,1,0,0,16711680,30);
   }
   function showArea()
   {
      var _loc13_ = getTimer();
      var _loc11_ = - this._parent._x;
      var _loc9_ = - this._parent._y;
      var _loc12_ = this.viewArea.width + this.leftRightIndention;
      var _loc10_ = this.viewArea.height + this.topBottomIndention;
      var _loc7_ = new flash.geom.Rectangle(_loc11_,_loc9_,_loc12_,_loc10_);
      var _loc2_;
      var _loc6_;
      var _loc5_;
      var _loc3_;
      var _loc4_;
      for(var _loc8_ in this.playerList)
      {
         _loc2_ = this.getWalker(_loc8_);
         _loc6_ = _loc2_._x;
         _loc5_ = _loc2_._y;
         _loc3_ = _loc7_.contains(_loc6_,_loc5_);
         _loc2_.activate(_loc3_);
         _loc4_ = this.helperObjects[_loc8_];
         _loc4_._visible = _loc3_;
      }
   }
   function get gamer_mc()
   {
      return this.getWalker(lol.core.player.Gamer.ID);
   }
   function sceneEnabled(obj)
   {
      var _loc2_ = !obj.status;
      this.cursorManager.activate(_loc2_);
   }
   function onEnterFrame()
   {
      this.dispatchEvent({type:"enterFrame"});
   }
   function kill()
   {
      this.master = lol.core.Master.getInstance();
      this.master.chat.removeEventListener("refresh",this,this.chatRefreshed);
      this.cursorManager.kill();
      this.cursorManager = null;
      this.lBuilder.kill();
      this.lBuilder = null;
      this.depthManager.kill();
      this.depthManager = null;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("displayLoc_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
