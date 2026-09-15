class lol.core.quests.QuestInspector
{
   var TimerForResetDailyes;
   var XMC;
   var checkedNPC;
   var checkedQuests;
   var closedQuest;
   var cqList;
   var currentQuests;
   var daily_quest_count_available;
   var dispatchEvent;
   var gived_quest;
   var questCollection;
   var questStatusList;
   var quester;
   var requested;
   var rewardItemArr;
   var statusCount;
   var updateNPCList;
   var updateTimerID;
   static var callStack;
   static var sInstance;
   static var singleCreation;
   var lockUpdate = false;
   static var callCount = 0;
   static var packageLength = 1;
   function QuestInspector()
   {
      if(!lol.core.quests.QuestInspector.singleCreation)
      {
         trace("New QuestInspector error! Use getInstance method.");
      }
      else
      {
         this.init();
      }
   }
   static function getInstance()
   {
      if(!lol.core.quests.QuestInspector.sInstance)
      {
         lol.core.quests.QuestInspector.singleCreation = true;
         lol.core.quests.QuestInspector.sInstance = new lol.core.quests.QuestInspector();
         lol.core.quests.QuestInspector.singleCreation = false;
      }
      return lol.core.quests.QuestInspector.sInstance;
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("q_list",this);
      this.XMC.addEventListener("q_sys",this);
      this.XMC.addEventListener("q_status",this,this.questStatus);
      this.XMC.addEventListener("q_si_kill_mobs",this);
      this.XMC.addEventListener("q_si_bring_l_obj",this);
      this.XMC.addEventListener("q_si_del_obj",this);
      this.XMC.addEventListener("q_di_kill_mobs",this);
      this.XMC.addEventListener("q_di_bring_l_obj",this);
      this.XMC.addEventListener("q_di_del_obj",this);
      this.questCollection = new Array();
      this.currentQuests = new Array();
      this.checkedQuests = new Array();
      this.checkedNPC = new Array();
      this.closedQuest = undefined;
      lol.core.quests.QuestInspector.callStack = new Array();
      this.lockUpdate = false;
   }
   function addCall(mess)
   {
      lol.core.quests.QuestInspector.callStack.push(mess);
      if(lol.core.quests.QuestInspector.callCount < lol.core.quests.QuestInspector.packageLength)
      {
         this.sendCall();
      }
   }
   function sendCall()
   {
      var _loc2_;
      if(lol.core.quests.QuestInspector.callStack.length > 0)
      {
         lol.core.quests.QuestInspector.callCount++;
         _loc2_ = lol.core.quests.QuestInspector.callStack.shift();
         this.XMC.Send(_loc2_);
      }
   }
   function updateCall()
   {
      lol.core.quests.QuestInspector.callCount--;
      if(lol.core.quests.QuestInspector.callCount <= lol.core.quests.QuestInspector.packageLength)
      {
         this.sendCall();
      }
   }
   function addNPCQuest(typeID, npcID)
   {
      this.checkQStatus(typeID,npcID);
   }
   function checkQStatus(typeID, npcID)
   {
      var _loc3_;
      if(!this.checkedQuests[typeID] || !this.checkedNPC[npcID] && npcID)
      {
         this.checkedQuests[typeID] = true;
         if(npcID)
         {
            this.checkedNPC[npcID] = true;
         }
         this.lockUpdate = true;
         _loc3_ = new lol.server.mess.CSM_QStatus(typeID);
         this.addCall(_loc3_);
      }
   }
   function questStatus(obj)
   {
      var _loc7_ = obj.param.type;
      var _loc9_ = obj.param.status;
      var _loc6_ = obj.param.name;
      var _loc8_ = obj.param.q_type;
      var _loc3_ = this.createQuest(_loc7_);
      _loc3_.addEventListener("questUpdate",this,this.questNameUpdateHandler);
      _loc3_.q_type = _loc8_;
      if(_loc9_)
      {
         _loc3_.available = true;
         _loc3_.setName(_loc6_);
      }
      else
      {
         _loc3_.available = false;
         this.questUpdate();
      }
      this.statusCount = this.statusCount + 1;
      this.updateCall();
      var _loc2_ = 0;
      for(var _loc4_ in this.checkedQuests)
      {
         _loc2_ = _loc2_ + 1;
      }
      if(this.statusCount == _loc2_)
      {
         this.checkStatusChanged();
      }
      this.lockUpdate = false;
   }
   function loadUnknownQuest(quest)
   {
      if(!quest.initialized)
      {
         this.requestSI(quest.typeID);
      }
   }
   function checkStatusChanged()
   {
      var _loc6_ = new Array();
      var _loc3_;
      var _loc2_;
      var _loc5_;
      var _loc4_;
      for(var _loc8_ in this.questStatusList)
      {
         _loc3_ = this.questStatusList[_loc8_].typeID;
         _loc2_ = this.questStatusList[_loc8_].type;
         _loc5_ = this.questCollection[_loc3_];
         if(_loc5_.statusChanged && _loc5_.available)
         {
            if(_loc2_ == "get" && this.quester.hasQuest(_loc3_,_loc2_))
            {
               _loc6_.push({quest:_loc5_,type:_loc2_});
            }
            else
            {
               for(var _loc7_ in this.currentQuests)
               {
                  _loc4_ = this.currentQuests[_loc7_];
                  if(_loc4_.typeID == _loc3_ && this.quester.hasQuest(_loc3_,_loc2_))
                  {
                     _loc6_.push({quest:_loc4_,type:_loc2_});
                     break;
                  }
               }
            }
         }
      }
      this.dispatchEvent({type:lol.core.quests.QuestEvent.UPDATE_STATUS,quests:_loc6_});
   }
   function createQuest(typeID)
   {
      var _loc3_;
      if(!this.questCollection[typeID])
      {
         _loc3_ = new lol.core.quests.Quest(typeID);
         this.questCollection[typeID] = _loc3_;
      }
      return this.questCollection[typeID];
   }
   function questNameUpdateHandler()
   {
      this.questUpdate();
   }
   function getGQs(_npc)
   {
      var _loc7_ = new Array();
      var _loc10_ = !_npc ? this.quester : _npc;
      var _loc8_ = _loc10_.giveQuests;
      var _loc9_ = _loc8_.length;
      var _loc4_;
      var _loc3_;
      var _loc5_;
      var _loc2_ = 0;
      while(_loc2_ < _loc9_)
      {
         _loc4_ = _loc8_[_loc2_];
         _loc5_ = this.questCollection[_loc4_];
         _loc3_ = false;
         for(var _loc6_ in this.currentQuests)
         {
            if(this.currentQuests[_loc6_].typeID == _loc4_)
            {
               _loc3_ = true;
               break;
            }
         }
         if(!_loc3_ && _loc5_.available)
         {
            _loc7_.push(_loc5_);
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc7_;
   }
   function getTQs(_npc)
   {
      var _loc5_ = new Array();
      var _loc10_ = !_npc ? this.quester : _npc;
      var _loc8_ = _loc10_.takeQuests;
      var _loc9_ = _loc8_.length;
      var _loc6_;
      var _loc3_;
      var _loc2_;
      var _loc4_ = 0;
      while(_loc4_ < _loc9_)
      {
         _loc6_ = _loc8_[_loc4_];
         _loc3_ = this.questCollection[_loc6_];
         for(var _loc7_ in this.currentQuests)
         {
            _loc2_ = this.currentQuests[_loc7_];
            if(_loc3_.typeID == _loc2_.typeID && _loc3_.available)
            {
               _loc5_.push(_loc2_);
            }
         }
         _loc4_ = _loc4_ + 1;
      }
      return _loc5_;
   }
   function getHighPriorityQuestType(_npc)
   {
      var _loc10_ = !_npc ? this.quester : _npc;
      var _loc9_ = _loc10_.giveQuests;
      var _loc8_ = _loc9_.length;
      var _loc5_;
      var _loc3_;
      var _loc4_;
      var _loc6_ = 100000;
      var _loc2_ = 0;
      while(_loc2_ < _loc8_)
      {
         _loc5_ = _loc9_[_loc2_];
         _loc4_ = this.questCollection[_loc5_];
         _loc3_ = false;
         for(var _loc7_ in this.currentQuests)
         {
            if(this.currentQuests[_loc7_].typeID == _loc5_)
            {
               _loc3_ = true;
               break;
            }
         }
         if(!_loc3_ && _loc4_.available)
         {
            if(_loc6_ > _loc4_.q_type)
            {
               _loc6_ = _loc4_.q_type;
            }
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc8_ > 0 && _loc6_ == 100000)
      {
         _loc6_ = 0;
      }
      return _loc6_;
   }
   function hasAvailableQuests(_npc)
   {
      var _loc10_ = !_npc ? this.quester : _npc;
      var _loc8_ = _loc10_.giveQuests;
      var _loc6_ = _loc8_.length;
      var _loc3_;
      var _loc5_;
      var _loc2_;
      var _loc4_ = 0;
      while(_loc4_ < _loc6_)
      {
         _loc3_ = _loc8_[_loc4_];
         _loc2_ = this.questCollection[_loc3_];
         _loc5_ = false;
         for(var _loc7_ in this.currentQuests)
         {
            if(this.currentQuests[_loc7_].typeID == _loc3_)
            {
               _loc5_ = true;
               break;
            }
         }
         if(!_loc5_ && _loc2_.available)
         {
            return true;
         }
         _loc4_ = _loc4_ + 1;
      }
      var _loc9_ = _loc10_.takeQuests;
      _loc6_ = _loc9_.length;
      _loc4_ = 0;
      var _loc7_;
      var _loc0_;
      loop1:
      while(_loc4_ < _loc6_)
      {
         _loc3_ = _loc9_[_loc4_];
         _loc2_ = this.questCollection[_loc3_];
         §§enumerate(this.currentQuests);
         do
         {
            if((_loc0_ = §§enumeration()) != null)
            {
               continue;
            }
            _loc4_ = _loc4_ + 1;
            continue loop1;
         }
         while(_loc7_ = _loc0_, !(_loc2_.typeID == this.currentQuests[_loc7_].typeID && _loc2_.available));
         return true;
      }
      return false;
   }
   function requestCurrentQuests()
   {
      var _loc2_;
      if(!this.requested)
      {
         _loc2_ = new lol.server.mess.CSM_QCurrentQuests();
         this.XMC.Send(_loc2_);
      }
   }
   function q_sys(obj)
   {
      this.daily_quest_count_available = obj.param.daily_available;
      var _loc3_ = new Date();
      var _loc2_ = _loc3_.getUTCHours() * 60 + _loc3_.getUTCMinutes();
      var _loc4_;
      if(_loc2_ < lol.core.GConstatns.daily_reset_time)
      {
         _loc4_ = lol.core.GConstatns.daily_reset_time - _loc2_;
      }
      else
      {
         _loc4_ = lol.core.GConstatns.daily_reset_time + 1440 - _loc2_;
      }
      this.TimerForResetDailyes = setInterval(this,"ResetDailyQuestAvailableCount",_loc4_ * 60 * 1000);
   }
   function ResetDailyQuestAvailableCount()
   {
      this.daily_quest_count_available = lol.core.GConstatns.daily_max;
      clearInterval(this.TimerForResetDailyes);
   }
   function get DailyQuestCountAvailable()
   {
      return this.daily_quest_count_available;
   }
   function q_list(obj)
   {
      this.requested = true;
      var _loc6_ = obj.param.q_id;
      var _loc8_ = obj.param.q_types;
      var _loc7_ = _loc6_.length;
      var _loc4_;
      var _loc3_;
      this.cqList = new Array();
      var _loc2_ = 0;
      var _loc5_;
      while(_loc2_ < _loc7_)
      {
         _loc4_ = _loc6_[_loc2_];
         _loc3_ = _loc8_[_loc2_];
         _loc5_ = this.createQuest(_loc3_);
         if(!_loc5_.initialized)
         {
            this.requestSI(_loc3_);
         }
         else
         {
            this.requestDI(_loc4_);
         }
         this.cqList[_loc3_] = _loc4_;
         _loc2_ = _loc2_ + 1;
      }
   }
   function getCurrentQuests()
   {
      return this.currentQuests;
   }
   function getQuest(quest)
   {
      var _loc4_ = quest.typeID;
      this.gived_quest = quest.name;
      var _loc3_ = this.quester.getGQIndex(_loc4_);
      var _loc2_ = new lol.server.mess.CSM_QGetQuest(_loc3_,this.quester.id);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.getAck);
      }
   }
   function getAck(obj)
   {
      var _loc2_ = obj.param.res;
      if(_loc2_ == 0)
      {
         if(this.gived_quest != undefined)
         {
            lol.core.SceneShifter.newQuestGameHelpMessage(this.gived_quest);
         }
         this.questUpdate();
      }
   }
   function takeQuest(questTask, objIdx)
   {
      var _loc3_ = !objIdx ? 0 : objIdx;
      var _loc2_ = new lol.server.mess.CSM_QTakeQuest(questTask.qID,this.quester.id,_loc3_);
      if(this.XMC.Send(_loc2_))
      {
         this.rewardItemArr = new Array();
         lol.core.Master.getInstance().gamer.equipment.addEventListener("addItem",this,this.getRewardItem);
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.takeAck,questTask.qID);
      }
   }
   function takeAck(obj)
   {
      var _loc4_ = obj.param.res;
      lol.core.Master.getInstance().gamer.equipment.removeEventListener("addItem",this,this.getRewardItem);
      var _loc2_;
      var _loc3_;
      if(_loc4_ == 0)
      {
         _loc2_ = obj.data;
         _loc3_ = this.currentQuests[_loc2_].typeID;
         this.currentQuests[_loc2_] = null;
         delete this.currentQuests[_loc2_];
         this.checkedQuests[_loc3_] = null;
         this.closedQuest = _loc3_;
         this.questUpdate();
         this.requestAllNPC();
      }
      else
      {
         lol.utils.ErrorReport.callReport(0,44);
         this.closedQuest = undefined;
      }
      this.showRewardMessage();
   }
   function getRewardItem(obj)
   {
      var _loc5_ = obj.item;
      var _loc2_;
      for(var _loc3_ in this.rewardItemArr)
      {
         if(this.rewardItemArr[_loc3_].item.typeID == _loc5_.typeID)
         {
            _loc2_ = Number(_loc3_);
            break;
         }
      }
      if(_loc2_ != undefined)
      {
         this.rewardItemArr[_loc2_].num++;
      }
      else
      {
         this.rewardItemArr.push({item:_loc5_,num:1});
      }
   }
   function rewardItemUpdate(obj)
   {
      obj.target.removeEventListener("itemUpdate",this,this.rewardItemUpdate);
      this.showRewardMessage();
   }
   function showRewardMessage()
   {
      var _loc2_ = "";
      for(var _loc3_ in this.rewardItemArr)
      {
         if(!this.rewardItemArr[_loc3_].item.getProp("name"))
         {
            this.rewardItemArr[_loc3_].item.addEventListener("itemUpdate",this,this.rewardItemUpdate);
            return undefined;
         }
         _loc2_ += "\r&lt;" + this.rewardItemArr[_loc3_].item.getProp("name") + "&gt;";
         if(this.rewardItemArr[_loc3_].num > 1)
         {
            _loc2_ += ", " + this.rewardItemArr[_loc3_].num + " шт";
         }
      }
      var _loc4_;
      if(_loc2_ != "")
      {
         _loc2_ = "Вы получили:" + _loc2_;
         _loc4_ = lol.core.SceneShifter.newServiceMessage(_loc2_,lol.gpui.ServiceMessage.QUEST_MESSAGE);
      }
   }
   function cancelQuest(questTask)
   {
      var _loc2_ = new lol.server.mess.CSM_QCancelQuest(questTask.qID);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cancelAck,questTask.qID);
      }
   }
   function cancelAck(obj)
   {
      var _loc3_ = obj.param.res;
      var _loc2_;
      if(_loc3_ == 0)
      {
         trace("cancelAck 1");
         _loc2_ = obj.data;
         this.currentQuests[_loc2_] = null;
         delete this.currentQuests[_loc2_];
         this.closedQuest = _loc2_;
         trace("cancelAck 2");
         this.questUpdate();
         trace("cancelAck 3");
         this.requestAllNPC();
         trace("cancelAck 4");
      }
   }
   function getCurrentQuestLength()
   {
      var _loc2_ = 0;
      for(var _loc3_ in this.currentQuests)
      {
         if(this.currentQuests[_loc3_])
         {
            _loc2_ = _loc2_ + 1;
         }
      }
      return _loc2_;
   }
   function createQuestTask(q_id, type_id)
   {
      var _loc2_;
      if(!this.currentQuests[q_id])
      {
         _loc2_ = new lol.core.quests.QuestTask(type_id,q_id);
         _loc2_.quest = this.questCollection[type_id];
         this.currentQuests[q_id] = _loc2_;
      }
      return this.currentQuests[q_id];
   }
   function requestSI(typeID)
   {
      var _loc2_ = new lol.server.mess.CSM_QStatInfo(typeID);
      this.addCall(_loc2_);
   }
   function q_si_kill_mobs(obj)
   {
      var _loc2_ = new lol.core.quests.KillMobQuest();
      var _loc3_ = this.initQuest(obj,_loc2_);
   }
   function q_si_bring_l_obj(obj)
   {
      var _loc2_ = new lol.core.quests.BringObjQuest();
      var _loc3_ = this.initQuest(obj,_loc2_);
   }
   function q_si_del_obj(obj)
   {
      var _loc2_ = new lol.core.quests.DeliverObjQuest();
      var _loc3_ = this.initQuest(obj,_loc2_);
   }
   function initQuest(obj, mission)
   {
      var _loc3_ = obj.param.type;
      var _loc2_ = lol.core.quests.Quest(this.questCollection[_loc3_]);
      _loc2_.addEventListener("questUpdate",this,this.questUpdateHandler);
      _loc2_.initialize(obj);
      mission.initialize(obj);
      _loc2_.missionStatus = mission;
      var _loc5_;
      if(this.cqList[_loc3_] != undefined)
      {
         _loc5_ = this.cqList[_loc3_];
         this.requestDI(_loc5_);
      }
      this.updateCall();
      return _loc2_;
   }
   function requestDI(q_id)
   {
      var _loc2_ = new lol.server.mess.CSM_QDynInfo(q_id);
      this.addCall(_loc2_);
   }
   function q_di_kill_mobs(obj)
   {
      var _loc8_ = obj.param.q_id;
      var _loc5_ = obj.param.q_type;
      var _loc9_ = obj.param.kill_num;
      var _loc6_ = obj.param.complete;
      var _loc3_ = this.createQuestTask(_loc8_,_loc5_);
      _loc3_.complete = obj.param.complete;
      var _loc7_ = _loc3_.quest.missionStatus.getDIFlag();
      var _loc10_ = _loc3_.quest.missionStatus.update(obj);
      this.questUpdate();
      this.updateCall();
      var _loc4_ = this.questCollection[_loc5_];
      if(_loc7_)
      {
         _loc10_.questName = _loc4_.name;
         this.dispatchEvent({type:lol.core.quests.Quest.KILL_MOB,changes:_loc10_});
         if(_loc6_)
         {
            this.dispatchEvent({type:lol.core.quests.Quest.COMPLETE,questName:_loc4_.name});
         }
      }
   }
   function q_di_bring_l_obj(obj)
   {
      var _loc8_ = obj.param.q_id;
      var _loc5_ = obj.param.q_type;
      var _loc9_ = obj.param.obj_num;
      var _loc6_ = obj.param.complete;
      var _loc3_ = this.createQuestTask(_loc8_,_loc5_);
      _loc3_.complete = obj.param.complete;
      var _loc7_ = _loc3_.quest.missionStatus.getDIFlag();
      var _loc10_ = _loc3_.quest.missionStatus.update(obj);
      this.questUpdate();
      this.updateCall();
      var _loc4_ = this.questCollection[_loc5_];
      if(_loc7_)
      {
         _loc10_.questName = _loc4_.name;
         this.dispatchEvent({type:lol.core.quests.Quest.GET_OBJECT,changes:_loc10_});
         if(_loc6_)
         {
            this.dispatchEvent({type:lol.core.quests.Quest.COMPLETE,questName:_loc4_.name});
         }
      }
   }
   function q_di_del_obj(obj)
   {
      var _loc8_ = obj.param.q_id;
      var _loc5_ = obj.param.q_type;
      var _loc10_ = obj.param.obj;
      var _loc6_ = obj.param.complete;
      var _loc3_ = this.createQuestTask(_loc8_,_loc5_);
      _loc3_.complete = obj.param.complete;
      var _loc7_ = _loc3_.quest.missionStatus.getDIFlag();
      var _loc9_ = _loc3_.quest.missionStatus.update(obj);
      this.questUpdate();
      this.updateCall();
      var _loc4_ = this.questCollection[_loc5_];
      if(_loc7_)
      {
         _loc9_.questName = _loc4_.name;
         this.dispatchEvent({type:lol.core.quests.Quest.DEL_OBJECT,changes:_loc9_});
         if(_loc6_ && _loc9_.finded != undefined)
         {
            this.dispatchEvent({type:lol.core.quests.Quest.COMPLETE,questName:_loc4_.name});
         }
      }
   }
   function questUpdateHandler(obj)
   {
      var _loc2_ = obj.target;
      this.questUpdate(_loc2_);
   }
   function requestAllNPC()
   {
      this.checkedQuests = new Array();
      this.checkedNPC = new Array();
      this.statusCount = 0;
      this.updateNPCList = this.getNPCList();
      this.updateTimerID = setInterval(this,"requestNPC",300);
   }
   function requestNPC()
   {
      if(this.lockUpdate == true)
      {
         return undefined;
      }
      if(this.updateNPCList.length <= 0)
      {
         clearInterval(this.updateTimerID);
         return undefined;
      }
      var _loc5_ = lol.core.player.NPC(this.updateNPCList.shift());
      if(_loc5_ == this.quester)
      {
         this.questStatusList = new Array();
      }
      var _loc6_ = _loc5_.giveQuests;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc6_.length)
      {
         _loc3_ = _loc6_[_loc2_];
         this.checkQStatus(_loc3_);
         if(_loc5_ == this.quester)
         {
            this.questStatusList[_loc3_] = {typeID:_loc3_,type:"get"};
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc7_ = _loc5_.takeQuests;
      _loc2_ = 0;
      while(_loc2_ < _loc7_.length)
      {
         _loc3_ = _loc7_[_loc2_];
         this.checkQStatus(_loc3_);
         if(_loc5_ == this.quester)
         {
            for(var _loc8_ in this.currentQuests)
            {
               if(this.currentQuests[_loc8_].typeID == _loc3_)
               {
                  this.questStatusList[_loc3_] = {typeID:_loc3_,type:"take"};
                  break;
               }
            }
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function getNPCList()
   {
      var _loc4_ = new Array();
      var _loc6_ = lol.core.Master.getInstance();
      var _loc7_ = _loc6_.currentLocation;
      var _loc3_ = _loc7_.playerList;
      var _loc5_ = _loc3_.length;
      var _loc1_ = 0;
      var _loc2_;
      while(_loc1_ < _loc5_)
      {
         _loc2_ = _loc3_[_loc1_];
         if(_loc2_ instanceof lol.core.player.NPC)
         {
            _loc4_.push(_loc2_);
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc4_;
   }
   function setQuestNPC(npcPlayer)
   {
      this.quester = npcPlayer;
   }
   function questUpdate(quest)
   {
      var _loc2_ = new Object();
      _loc2_.type = "update";
      if(quest)
      {
         _loc2_.quest = quest;
      }
      this.dispatchEvent(_loc2_);
   }
   function clear()
   {
      this.requested = false;
      this.currentQuests = new Array();
   }
}
