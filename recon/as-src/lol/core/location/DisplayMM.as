class lol.core.location.DisplayMM extends MovieClip
{
   var core_mc;
   var currentLocation;
   var master;
   var onMouseMove;
   var playerList;
   var tx;
   var ty;
   static var MAIN = "locMM_main";
   static var TRADER = "locMM_trader";
   static var FRIEND = "locMM_friend";
   static var NEUTRAL = "locMM_neutral";
   static var ENEMY = "locMM_enemy";
   static var MOB = "locMM_mob";
   static var NPC_HAS_QUEST = "locMM_hasQuest";
   static var NPC_CAN_GET_QUEST = "locMM_canGetQuest";
   var scaleX = 1.5;
   var scaleY = 1.5;
   function DisplayMM()
   {
      super();
      this.playerList = new Array();
      this.master = lol.core.Master.getInstance();
      this.currentLocation = this.master.currentLocation;
      this.core_mc = this;
      this.init();
   }
   function init()
   {
      this.currentLocation.addEventListener("addPlayer",this);
      this.currentLocation.addEventListener("removePlayer",this);
      this.currentLocation.addEventListener("dead",this);
      this.currentLocation.addEventListener("finishPart",this);
      this.currentLocation.addEventListener("enemy",this);
      lol.core.quests.QuestInspector.getInstance().addEventListener("update",this,this.questUpdate);
      this.makeCast();
   }
   function makeCast()
   {
      var _loc5_ = this.currentLocation.playerList;
      var _loc3_;
      var _loc2_;
      var _loc4_;
      var _loc6_;
      for(var _loc7_ in _loc5_)
      {
         _loc3_ = _loc5_[_loc7_];
         _loc2_ = _loc3_.id;
         _loc4_ = _loc3_.walker.numPos;
         if(!this.playerList[_loc2_])
         {
            _loc6_ = this.addPlayer(_loc2_,_loc4_);
         }
      }
   }
   function addPlayer()
   {
      var _loc5_;
      var _loc6_;
      if(typeof arguments[0] == "object")
      {
         _loc5_ = arguments[0].player.id;
         _loc6_ = arguments[0].player.walker.numPos;
      }
      else
      {
         _loc5_ = arguments[0];
         _loc6_ = arguments[1];
      }
      var _loc4_;
      var _loc3_;
      var _loc7_;
      if(_loc5_ == this.master.gamer.id)
      {
         _loc4_ = lol.core.location.DisplayMM.MAIN;
      }
      else
      {
         _loc3_ = this.master.getPlayer(_loc5_);
         _loc7_ = _loc3_.clanMemberInfo.clanInfo.reg;
         if(_loc3_.walker.relation == "enemy")
         {
            _loc4_ = lol.core.location.DisplayMM.ENEMY;
         }
         else if(_loc3_ instanceof lol.core.player.Mob)
         {
            if(_loc3_.playerInfo.ally)
            {
               _loc4_ = lol.core.location.DisplayMM.FRIEND;
            }
            else
            {
               _loc4_ = lol.core.location.DisplayMM.MOB;
            }
         }
         else if(this.checkQuest(_loc3_) == 2)
         {
            _loc4_ = lol.core.location.DisplayMM.NPC_CAN_GET_QUEST;
         }
         else if(this.checkQuest(_loc3_) == 3 || this.checkQuest(_loc3_) == 1)
         {
            _loc4_ = lol.core.location.DisplayMM.NPC_HAS_QUEST;
         }
         else if(_loc3_ instanceof lol.core.player.Trader || _loc3_ instanceof lol.core.player.Upgrader || _loc3_ instanceof lol.core.player.Teacher)
         {
            _loc4_ = lol.core.location.DisplayMM.TRADER;
         }
         else if(_loc7_ != 0 && lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo.reg == _loc7_)
         {
            _loc4_ = lol.core.location.DisplayMM.FRIEND;
         }
         else if(_loc3_.playerInfo.ally)
         {
            _loc4_ = lol.core.location.DisplayMM.FRIEND;
         }
         else
         {
            _loc4_ = lol.core.location.DisplayMM.NEUTRAL;
         }
      }
      var _loc8_ = this.__addPlayer(_loc5_,_loc4_,_loc6_);
      return _loc8_;
   }
   function checkQuest(player)
   {
      var _loc4_ = lol.core.player.NPC(player);
      var _loc1_;
      var _loc2_;
      if(_loc4_.hasAvailableQuests())
      {
         _loc1_ = lol.core.quests.QuestInspector.getInstance().getTQs(_loc4_);
         if(_loc1_.length > 0)
         {
            _loc2_ = false;
            for(var _loc3_ in _loc1_)
            {
               if(_loc1_[_loc3_].complete)
               {
                  _loc2_ = true;
                  break;
               }
            }
            if(_loc2_)
            {
               return 2;
            }
            return 3;
         }
         return 1;
      }
   }
   function __addPlayer(id, linkID, pos)
   {
      var _loc4_;
      var _loc3_;
      if(id != undefined)
      {
         _loc4_ = this.core_mc.getNextHighestDepth();
         _loc3_ = this.core_mc.attachMovie(linkID,"walker" + id,_loc4_);
         _loc3_.id = id;
         this.playerList[id] = _loc3_;
         this.placeWalker(id,pos);
         return _loc3_;
      }
   }
   function removePlayer()
   {
      var _loc3_;
      if(typeof arguments[0] == "object")
      {
         _loc3_ = arguments[0].player.id;
      }
      else
      {
         _loc3_ = arguments[0];
      }
      var _loc4_ = this.getWalker(_loc3_);
      _loc4_.removeMovieClip();
   }
   function dead(obj)
   {
      var _loc2_ = obj.dead;
      this.removePlayer(_loc2_);
   }
   function getWalker(id)
   {
      return this.playerList[id];
   }
   function placeWalker(id, pos)
   {
      var _loc2_ = this.currentLocation.getCellFromNumber(pos);
      var _loc5_ = _loc2_.gx;
      var _loc4_ = _loc2_.gy;
      var _loc3_ = this.getWalker(id);
      _loc3_._x = _loc5_ * this.scaleX;
      _loc3_._y = 0.5 * _loc4_ * this.scaleY;
   }
   function finishPart(obj)
   {
      var _loc2_ = obj.walker;
      var _loc3_ = _loc2_.id;
      var _loc4_ = _loc2_.numPos;
      this.placeWalker(_loc3_,_loc4_);
   }
   function enemy(obj)
   {
      var _loc2_ = obj.player.id;
      var _loc4_ = lol.core.location.DisplayMM.ENEMY;
      var _loc3_ = obj.player.walker.numPos;
      this.swapMarker(_loc2_,_loc4_,_loc3_);
   }
   function questUpdate()
   {
      this.removeAllPlayers();
      this.makeCast();
   }
   function removeAllPlayers()
   {
      for(var _loc2_ in this.playerList)
      {
         this.playerList[_loc2_].removeMovieClip();
      }
      this.playerList = new Array();
   }
   function swapMarker(id, linkID, pos)
   {
      this.removePlayer(id);
      this.__addPlayer(id,linkID,pos);
   }
   function onPress()
   {
      this.tx = this._xmouse;
      this.ty = this._ymouse;
      this.mouseMove();
      this.onMouseMove = this.mouseMove;
   }
   function onRelease()
   {
      var _loc2_;
      if(this.tx == this._xmouse && this.ty == this._ymouse && Key.isDown(16))
      {
         _loc2_ = this.currentLocation.getCellFromGrid(this.tx,this.ty);
         this.currentLocation.movePlayer(_loc2_);
      }
      delete this.onMouseMove;
   }
   function onReleaseOutside()
   {
      delete this.onMouseMove;
   }
   function mouseMove()
   {
      var _loc4_;
      var _loc3_;
      var _loc2_;
      var _loc7_;
      var _loc6_;
      var _loc8_;
      if(!Key.isDown(16))
      {
         _loc4_ = Math.floor(this._xmouse / this.scaleX);
         _loc3_ = Math.floor(this._ymouse * 2 / this.scaleY);
         _loc2_ = this.currentLocation.getCellFromGrid(_loc4_,_loc3_);
         _loc7_ = _loc2_.rx;
         _loc6_ = _loc2_.ry;
         _loc8_ = lol.core.location.LocDeclaration.abstractToReal({x:_loc2_.rx,y:_loc2_.ry});
         lol.core.SceneShifter.locationScreen.centerPoint({point:_loc8_,how:false});
      }
   }
}
