class lol.core.player.Entity
{
   var XMC;
   var _clanMemberInfo;
   var attributes;
   var dispatchEvent;
   var effects;
   var equipment;
   var id;
   var nameID;
   var playerInfo;
   var reputations;
   var spt;
   var spt_int;
   var walker;
   static var staticID = "Entity";
   static var MOB = 0;
   static var TRADER = 1;
   static var TEACHER = 2;
   static var UPGRADER = 3;
   static var COMMONER = 4;
   static var HEALER = 5;
   static var LESSOR = 6;
   static var AUCTIONER = 7;
   var critDamage = false;
   function Entity(ID)
   {
      this.id = ID;
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.playerInfo = new lol.core.player.PersInfo();
      this.attributes = new lol.core.player.PersAttributes();
      this._clanMemberInfo = new lol.core.clans.ClanMemberInfo();
      this.effects = new lol.core.effects.EffectManager(this.id);
      this.reputations = new lol.core.player.Reputation.PersReputations();
      this.equipment = new lol.core.player.PersEquip(this.id,this.effects);
      lol.core.quests.QuestInspector.getInstance();
      if(this.id != lol.core.player.Gamer.ID)
      {
         this.requestInfo();
      }
      this.startPC();
   }
   function requestInfo()
   {
      var _loc2_ = new lol.server.mess.CSM_P_GetInfo(1,this.id,0);
      this.XMC.Send(_loc2_);
   }
   function userInfo(obj)
   {
      var _loc3_ = obj.param.name;
      var _loc9_ = obj.param.sex;
      var _loc4_ = obj.param.res;
      var _loc10_ = obj.param.ail;
      this.playerInfo.sex = _loc9_;
      this.playerInfo.resID = _loc4_;
      this.playerInfo.ally = obj.param.ally;
      var _loc8_ = lol.core.Master.getInstance().persGen;
      var _loc7_ = _loc8_.getAvatar(_loc4_);
      this.playerInfo.avatar = _loc7_;
      this.attributes.level = obj.param.lvl;
      this.reputations.updateReputations(obj.param.rep);
      this.reputations.battleground_reputation = obj.param.bg_rep;
      this.reputations.battleground_penalty = obj.param.bg_pen;
      var _loc6_;
      var _loc5_;
      if(this instanceof lol.core.player.Player)
      {
         this.playerInfo.name = _loc3_;
         this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_INFO,this));
      }
      else
      {
         _loc6_ = lol.utils.StringCollector.getInstance();
         _loc5_ = _loc6_.getString(_loc3_);
         if(_loc5_)
         {
            this.playerInfo.name = _loc5_.string;
            this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_INFO,this));
         }
         else
         {
            this.nameID = _loc3_;
            _loc6_.addEventListener("update",this,this.stringUpdate);
         }
      }
   }
   function userInfoFailed()
   {
   }
   function stringUpdate(obj)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
      var _loc2_ = _loc3_.getString(Number(this.nameID));
      if(_loc2_)
      {
         _loc3_.removeEventListener("update",this,this.stringUpdate);
         this.playerInfo.name = _loc2_.string;
         this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_INFO,this));
      }
   }
   function userUpdate(obj)
   {
      if(obj)
      {
         this.maxHealth = !obj.param.hmax ? this.maxHealth : obj.param.hmax;
         this.maxStamina = !obj.param.smax ? this.maxStamina : obj.param.smax;
         this.health = obj.param.hcur;
         this.stamina = obj.param.scur;
      }
   }
   function damage(value, crit)
   {
      this.critDamage = Boolean(crit);
      this.health -= value;
   }
   function sdamage(value, crit)
   {
      this.critDamage = Boolean(crit);
      this.stamina -= value;
   }
   function get health()
   {
      return this.attributes.health;
   }
   function set health(h)
   {
      this.attributes.health = h;
      this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_STATE,this));
   }
   function get maxHealth()
   {
      return this.attributes.maxHealth;
   }
   function set maxHealth(h)
   {
      this.attributes.maxHealth = h;
   }
   function get stamina()
   {
      return this.attributes.stamina;
   }
   function set stamina(s)
   {
      this.attributes.stamina = s;
      this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_STATE,this));
   }
   function get maxStamina()
   {
      return this.attributes.maxStamina;
   }
   function set maxStamina(h)
   {
      this.attributes.maxStamina = h;
   }
   function get primaryItem()
   {
      return this.equipment.primaryItem;
   }
   function get clanMemberInfo()
   {
      return this._clanMemberInfo;
   }
   function set clanMemberInfo(value)
   {
      this._clanMemberInfo = value;
   }
   function startMove(VX, VY, T)
   {
      this.walker.startMove(VX,VY,T);
   }
   function createMove()
   {
      this.walker.createMove();
   }
   function breakMove()
   {
      this.walker.breakMove();
   }
   function setDefaultWeapon()
   {
      var _loc2_ = new lol.core.objects.FireArm(0,4,0);
      _loc2_._animation_type = "rifle";
      this.equipment.primaryItem = _loc2_;
   }
   function kill()
   {
      lol.server.XMLCCallStack.skipCall("userInfo",this,this.userInfo);
      this.XMC.removeEventListener("accountInfo",this);
      delete this.playerInfo;
      this.walker.removeEventListener("finishMove",this);
      this.walker.kill();
      this.equipment.kill();
      delete this.equipment;
      delete this.attributes;
      delete this.walker;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("Player_" + this.id + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
