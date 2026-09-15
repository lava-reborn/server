class lol.core.quests.Quest
{
   var dispatchEvent;
   var finish_desc;
   var finish_descStrID;
   var finish_loc;
   var initialized;
   var level;
   var loc;
   var missionStatus;
   var name;
   var nameStrID;
   var needQuest;
   var notfinish_desc;
   var notfinish_descStrID;
   var num_rew_obj;
   var party_size;
   var q_type;
   var repeatable;
   var rew_afro;
   var rew_gold;
   var rew_loc;
   var rew_obj;
   var rewardItems;
   var start_desc;
   var start_descStrID;
   var typeID;
   static var KILL_MOB = "KILL_MOB";
   static var GET_OBJECT = "GET_OBJECT";
   static var DEL_OBJECT = "DEL_OBJECT";
   static var COMPLETE = "DEL_OBJECT";
   var cStatus = 0;
   var _available = false;
   function Quest(_typeID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.typeID = _typeID;
      this.initialized = false;
   }
   function initialize(obj)
   {
      this.typeID = obj.param.type;
      this.repeatable = obj.param.repeatable;
      this.party_size = obj.param.party_size;
      this.loc = obj.param.loc;
      this.finish_loc = obj.param.finish_loc;
      this.level = obj.param.level;
      this.rew_obj = obj.param.rew_obj;
      this.rew_afro = obj.param.rew_afro;
      this.rew_gold = obj.param.rew_gold;
      this.rew_loc = obj.param.rew_loc;
      this.num_rew_obj = obj.param.num_rew_obj;
      this.needQuest = obj.param.need_quest;
      this.q_type = obj.param.q_type;
      this.createRewardItems(this.rew_obj);
      this.initGDSLStringData(obj);
      this.initialized = true;
      this.dispatchEvent({type:"questLoaded",quest:this});
   }
   function setName(str)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
      var _loc2_ = _loc3_.getString(Number(str));
      if(_loc2_)
      {
         this.name = this.parseString(_loc2_.string);
         this.dispatchEvent({type:"questUpdate"});
      }
      else
      {
         this.nameStrID = Number(str);
         _loc3_.addEventListener("update",this,this.nameUpdate);
      }
   }
   function nameUpdate(obj)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
      var _loc2_ = _loc3_.getString(Number(this.nameStrID));
      if(_loc2_)
      {
         this.name = this.parseString(_loc2_.string);
         this.dispatchEvent({type:"questUpdate"});
      }
   }
   function initGDSLStringData(obj)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
      this.nameStrID = Number(obj.param.name);
      this.start_descStrID = obj.param.start_desc == "" ? null : Number(obj.param.start_desc);
      this.notfinish_descStrID = obj.param.notfinish_desc == "" ? null : Number(obj.param.notfinish_desc);
      this.finish_descStrID = obj.param.finish_desc == "" ? null : Number(obj.param.finish_desc);
      this.stringUpdate();
   }
   function stringUpdate(obj)
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      var _loc5_ = _loc2_.getString(this.nameStrID);
      var _loc7_ = this.start_descStrID == null ? new lol.utils.SCString(0,"") : _loc2_.getString(this.start_descStrID);
      var _loc4_ = this.notfinish_descStrID == null ? new lol.utils.SCString(0,"") : _loc2_.getString(this.notfinish_descStrID);
      var _loc6_ = this.finish_descStrID == null ? new lol.utils.SCString(0,"") : _loc2_.getString(this.finish_descStrID);
      var _loc3_;
      if(_loc5_ && _loc7_ && _loc4_ && _loc6_)
      {
         _loc2_.removeEventListener("update",this,this.stringUpdate);
         this.name = _loc5_.string;
         this.start_desc = _loc7_.string;
         this.notfinish_desc = _loc4_.string;
         this.finish_desc = _loc6_.string;
         _loc3_ = Number(!lol.core.Master.getInstance().gamer.playerInfo.boolSex);
         this.name = lol.utils.ParseString.replaceParametrically(this.name,lol.utils.ParseString.SEX,_loc3_);
         this.start_desc = lol.utils.ParseString.replaceParametrically(this.start_desc,lol.utils.ParseString.SEX,_loc3_);
         this.notfinish_desc = lol.utils.ParseString.replaceParametrically(this.notfinish_desc,lol.utils.ParseString.SEX,_loc3_);
         this.finish_desc = lol.utils.ParseString.replaceParametrically(this.finish_desc,lol.utils.ParseString.SEX,_loc3_);
         this.name = this.parseString(this.name);
         this.start_desc = this.parseString(this.start_desc);
         this.notfinish_desc = this.parseString(this.notfinish_desc);
         this.finish_desc = this.parseString(this.finish_desc);
         this.dispatchEvent({type:"questUpdate"});
      }
      else
      {
         _loc2_.addEventListener("update",this,this.stringUpdate);
      }
   }
   function getMissionStatus()
   {
      return this.missionStatus.getMissionStatus();
   }
   function createRewardItems(arr)
   {
      this.rewardItems = new Array();
      var _loc2_;
      var _loc3_;
      for(var _loc5_ in arr)
      {
         _loc2_ = arr[_loc5_];
         _loc3_ = lol.core.objects.ItemFactory.createPrototype(_loc2_);
         this.rewardItems.push(_loc3_);
      }
   }
   function getRewardItems()
   {
      return this.rewardItems;
   }
   function set available(a)
   {
      if(a != this._available)
      {
         this.cStatus = this.cStatus + 1;
      }
      else
      {
         this.cStatus = this.cStatus - 1;
      }
      if(this.cStatus <= 0)
      {
         this.cStatus = 0;
      }
      this._available = a;
   }
   function get available()
   {
      return this._available;
   }
   function get statusChanged()
   {
      return Boolean(this.cStatus);
   }
   function parseString(strIn)
   {
      var _loc1_ = lol.utils.ParseString.replaceAll(strIn,"\\","");
      var _loc3_ = "<u><a href=\"" + lol.core.SceneShifter._ref.getProfileUrl() + "\" target=\"_blank\">";
      var _loc2_ = "</a></u>";
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"%startPutGold%",_loc3_);
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"%endPutGold%",_loc2_);
      _loc3_ = "<u><a href=\"" + lol.core.SceneShifter._ref.getProfileUrl() + "\" target=\"_blank\">";
      _loc2_ = "</a></u>";
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"%startProfile%",_loc3_);
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"%endProfile%",_loc2_);
      return lol.utils.ParseString.replaceAll(_loc1_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
   }
}
