class lol.core.player.NPC extends lol.core.player.Entity
{
   var can_banking;
   var can_repair;
   var can_set_home;
   var can_trade;
   var can_trophy;
   var equipment;
   var giveQuests;
   var helloStrArr;
   var id;
   var isNPC;
   var playerInfo;
   var questType;
   var supportList;
   var takeQuests;
   static var staticID = "NPC";
   var callCount = 0;
   function NPC(ID)
   {
      super(ID);
      this.supportList = new Array();
      this.isNPC = true;
      this.questType = undefined;
   }
   function userInfo(obj)
   {
      this.giveQuests = obj.param.give_quests;
      this.takeQuests = obj.param.take_quests;
      var _loc3_ = 0;
      while(_loc3_ < this.giveQuests.length)
      {
         lol.core.quests.QuestInspector.getInstance().addNPCQuest(this.giveQuests[_loc3_],this.id);
         _loc3_ = _loc3_ + 1;
      }
      _loc3_ = 0;
      while(_loc3_ < this.takeQuests.length)
      {
         lol.core.quests.QuestInspector.getInstance().addNPCQuest(this.takeQuests[_loc3_],this.id);
         _loc3_ = _loc3_ + 1;
      }
      super.userInfo(obj);
      this.playerInfo.persType = obj.param.res;
      this.can_set_home = Boolean(obj.param.can_set_home);
      var _loc5_;
      if(this.can_set_home)
      {
         _loc5_ = new lol.core.player.Attendance(lol.core.player.Attendance.SET_HOME,this.id);
         this.supportList.push(_loc5_);
      }
      this.can_banking = Boolean(obj.param.can_banking);
      this.can_trophy = Boolean(obj.param.can_trophy);
      this.can_repair = Boolean(obj.param.can_repair);
      this.can_trade = Boolean(obj.param.can_trade);
      this.createHelloStrings(obj);
   }
   function getGQIndex(typeID)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.giveQuests.length)
      {
         if(this.giveQuests[_loc2_] == typeID)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function hasQuests()
   {
      if(this.giveQuests.length > 0 || this.takeQuests.length > 0)
      {
         return true;
      }
      return false;
   }
   function hasQuest(typeID, type)
   {
      var _loc3_;
      if(type == "get")
      {
         _loc3_ = this.giveQuests;
      }
      else if(type == "take")
      {
         _loc3_ = this.takeQuests;
      }
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_] == typeID)
         {
            return true;
         }
         _loc2_ = _loc2_ + 1;
      }
      return false;
   }
   function getHighPriorityQuestType()
   {
      this.questType = lol.core.quests.QuestInspector.getInstance().getHighPriorityQuestType(this);
      return this.questType;
   }
   function hasAvailableQuests()
   {
      return lol.core.quests.QuestInspector.getInstance().hasAvailableQuests(this);
   }
   function setDefaultWeapon()
   {
      var _loc2_ = new lol.core.objects.Item(0,4,0);
      _loc2_._animation_type = "fist";
      this.equipment.primaryItem = _loc2_;
   }
   function get canSetHome()
   {
      return this.can_set_home;
   }
   function get canBanking()
   {
      return this.can_banking;
   }
   function get canRepair()
   {
      return this.can_repair;
   }
   function get canTrophy()
   {
      return this.can_trophy;
   }
   function get canTrade()
   {
      return this.can_trade;
   }
   function haveSupport()
   {
      return Boolean(this.supportList.length);
   }
   function getSupport()
   {
      return this.supportList;
   }
   function createHelloStrings(obj)
   {
      var _loc2_ = obj.param.m_hello;
      var _loc3_;
      if(_loc2_ && _loc2_.length > 0)
      {
         _loc3_ = lol.utils.StringCollector.getInstance();
         _loc3_.addEventListener("update",this,this.stringUpdate);
         this.updateHelloString();
      }
   }
   function updateHelloString()
   {
      var _loc4_ = lol.utils.StringCollector.getInstance();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.helloStrArr.length)
      {
         if(!isNaN(this.helloStrArr[_loc2_]))
         {
            _loc3_ = _loc4_.getString(this.helloStrArr[_loc2_]);
            if(_loc3_)
            {
               this.helloStrArr[_loc2_] = _loc3_;
               this.callCount = this.callCount + 1;
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      if(this.callCount == this.helloStrArr.length)
      {
         _loc4_.removeEventListener("update",this,this.stringUpdate);
      }
   }
   function getHello()
   {
      var _loc2_ = random(this.helloStrArr.length);
      return this.helloStrArr[_loc2_];
   }
}
