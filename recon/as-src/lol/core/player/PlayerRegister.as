class lol.core.player.PlayerRegister
{
   var XMC;
   var _gamer;
   var playerList;
   function PlayerRegister()
   {
      this.playerList = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("usrUp",this);
      this.XMC.addEventListener("userInfo",this);
      this.XMC.addEventListener("userInfo_Player",this);
      this.XMC.addEventListener("userInfo_Trader",this);
      this.XMC.addEventListener("userInfo_Upgrader",this);
      this.XMC.addEventListener("userInfo_SpecTrainer",this);
      this.XMC.addEventListener("userInfo_Commoner",this);
      this.XMC.addEventListener("userInfo_Medic",this);
      this.XMC.addEventListener("userInfo_Lessor",this);
      this.XMC.addEventListener("userInfo_Auctioneer",this);
      this.XMC.addEventListener("e_list",this);
      this.XMC.addEventListener("ss_obj_move",this);
   }
   function get gamer()
   {
      return this._gamer;
   }
   function getPlayer(id)
   {
      var _loc2_ = !id ? this.gamer : this.playerList[id];
      return _loc2_;
   }
   function getPlayerByName(name)
   {
      var _loc2_;
      for(var _loc4_ in this.playerList)
      {
         _loc2_ = this.playerList[_loc4_];
         if(_loc2_.playerInfo.name == name)
         {
            return _loc2_;
         }
      }
      return null;
   }
   function createGamer()
   {
      this.playerList = new Array();
      var _loc2_ = this.addPlayer(lol.core.player.Gamer.ID);
      this._gamer = lol.core.player.Gamer(_loc2_);
   }
   function addPlayer(id, rtype)
   {
      if(!this.playerList[id] || this.playerList[id].type == "proxy")
      {
         this.playerList[id] = this.createPlayer(id,rtype);
      }
      else if(rtype == -1)
      {
         this.playerList[id].equipment.getStuff(3,id);
      }
      return this.playerList[id];
   }
   function createPlayer(id, rtype)
   {
      var _loc1_;
      if(id == lol.core.player.Gamer.ID)
      {
         _loc1_ = new lol.core.player.Gamer(id);
      }
      else
      {
         switch(rtype)
         {
            case lol.core.player.Entity.TRADER:
               _loc1_ = new lol.core.player.Trader(id);
               break;
            case lol.core.player.Entity.MOB:
               _loc1_ = new lol.core.player.Mob(id);
               break;
            case lol.core.player.Entity.TEACHER:
               _loc1_ = new lol.core.player.Teacher(id);
               break;
            case lol.core.player.Entity.UPGRADER:
               _loc1_ = new lol.core.player.Upgrader(id);
               break;
            case lol.core.player.Entity.COMMONER:
               _loc1_ = new lol.core.player.Commoner(id);
               break;
            case lol.core.player.Entity.HEALER:
               _loc1_ = new lol.core.player.Healer(id);
               break;
            case lol.core.player.Entity.LESSOR:
               _loc1_ = new lol.core.player.Lessor(id);
               break;
            case lol.core.player.Entity.AUCTIONER:
               _loc1_ = new lol.core.player.Auctioner(id);
               break;
            default:
               _loc1_ = new lol.core.player.Player(id);
         }
      }
      return _loc1_;
   }
   function removePlayer(id)
   {
      var _loc3_ = this.playerList[id];
      var _loc4_;
      var _loc5_;
      if(!(_loc3_ instanceof lol.core.player.Player))
      {
         if(_loc3_ instanceof lol.core.player.Mob)
         {
            _loc4_ = {type:"proxy",playerInfo:_loc3_.playerInfo};
            this.__removePlayer(id);
            this.playerList[id] = _loc4_;
            _loc5_ = new lol.utils.Timeout(this,this.__removeProxyPlayer,1000,id);
         }
         else
         {
            this.__removePlayer(id);
         }
      }
   }
   function __removePlayer(id)
   {
      var _loc2_ = this.playerList[id];
      _loc2_.kill();
      this.playerList[id] = null;
   }
   function __removeProxyPlayer(id)
   {
      if(this.playerList[id].type == "proxy")
      {
         this.playerList[id] = null;
      }
   }
   function clearPlayerList()
   {
      var _loc2_;
      for(var _loc3_ in this.playerList)
      {
         _loc2_ = this.playerList[_loc3_];
         this.removePlayer(_loc2_.id);
      }
      this.playerList = null;
   }
   function usrUp(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = this.getPlayer(_loc2_);
      _loc3_.userUpdate(obj);
   }
   function userUpdate(obj)
   {
      var _loc1_ = obj.target;
   }
   function userInfo(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Mob(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_Player(obj)
   {
      var _loc3_ = obj.param.id;
      var _loc4_ = lol.core.player.Player(this.getPlayer(_loc3_));
      if(obj.param.name == "")
      {
         obj.param.name = "Солдат СА";
      }
      _loc4_.userInfo(obj);
   }
   function userInfo_Trader(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Trader(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_SpecTrainer(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Teacher(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_Upgrader(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Upgrader(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function e_list(obj)
   {
      var _loc3_ = obj.param.mobi_id;
      var _loc2_ = this.getPlayer(_loc3_);
      if(_loc2_)
      {
         _loc2_.effects.e_list(obj);
      }
   }
   function userInfo_Commoner(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Commoner(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_Lessor(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Lessor(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_Auctioneer(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Auctioner(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function userInfo_Medic(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = lol.core.player.Healer(this.getPlayer(_loc2_));
      _loc3_.userInfo(obj);
   }
   function ss_obj_move(obj)
   {
      var _loc2_ = !obj.param.id ? lol.core.player.Gamer.ID : obj.param.id;
      var _loc4_ = this.getPlayer(_loc2_);
      if(_loc2_ != lol.core.player.Gamer.ID)
      {
         _loc4_.equipment.ss_obj_move(obj);
      }
   }
   function kill()
   {
      this.XMC.removeEventListener("usrUp",this);
      this.XMC.removeEventListener("userInfo",this);
      this.XMC.removeEventListener("userInfo_Player",this);
      this.XMC.removeEventListener("userInfo_Trader",this);
      this.XMC.removeEventListener("userInfo_Upgrader",this);
      this.XMC.removeEventListener("userInfo_SpecTrainer",this);
      this.XMC.removeEventListener("userInfo_Commoner",this);
      this.XMC.removeEventListener("userInfo_Medic",this);
   }
}
