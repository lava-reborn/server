class lol.gpui.QuestInfoInterface extends lol.gpui.GPUIObject
{
   var annotation;
   var attachMovie;
   var availableDailyQuests;
   var cancelQuest_btn;
   var closePlanshet_btn;
   var currentItem;
   var currentQuestTask;
   var infoCont;
   var infoPan;
   var listCont;
   var listPan;
   var questInspector;
   var questItemList;
   var questList_btn;
   var questsArr;
   function QuestInfoInterface()
   {
      super();
      this.doLater("init");
      this.questInspector = lol.core.quests.QuestInspector.getInstance();
   }
   function init()
   {
      this.questList_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.gotoQuestInfoInterface);
      this.cancelQuest_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancelQuest);
      lol.core.SceneShifter.hotKeyManager.addFilter("questInfo");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.questInspector.addEventListener("update",this,this.questsUpdate);
      this.cancelQuest_btn.enabled = false;
      this.buildQuestList();
      this.closePlanshet_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter._ref.currentScene.enabledHotKey(false);
   }
   function kill()
   {
      this.questList_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.gotoQuestInfoInterface);
      this.cancelQuest_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancelQuest);
      lol.core.SceneShifter.hotKeyManager.removeFilter("questInfo");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      this.questInspector.removeEventListener("update",this,this.questsUpdate);
      this.closePlanshet_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter._ref.currentScene.enabledHotKey(true);
   }
   function close()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function buildQuestList()
   {
      this.questsArr = this.questInspector.getCurrentQuests();
      this.listPan.setSize(240,380);
      this.listCont = this.listPan.fillContent();
      var _loc3_;
      var _loc2_;
      if(this.questsArr.length != 0)
      {
         _loc3_ = 0;
         for(var _loc4_ in this.questsArr)
         {
            _loc2_ = this.listCont.attachMovie("currentQuestItem","currentQuestItem" + this.listCont.getNextHighestDepth(),this.listCont.getNextHighestDepth());
            _loc2_._y = Math.round(_loc3_ * _loc2_._height);
            _loc2_.id = _loc3_;
            _loc2_.data = this.questsArr[_loc4_];
            _loc2_.title_txt.html = true;
            _loc2_.title_txt.htmlText = this.parseString(this.questsArr[_loc4_].quest.name);
            _loc2_.bg._alpha = (_loc3_ % 2 + 1) * 50;
            this.doLater("initBg",[_loc2_.bg]);
            this.questItemList.push(_loc2_);
            _loc3_ = _loc3_ + 1;
         }
      }
      this.availableDailyQuests.text = "Сейчас вам доступно " + this.questInspector.DailyQuestCountAvailable + " ежедневных квестов";
      this.listPan.chekSize();
   }
   function initBg(mc)
   {
      mc.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectQuest);
   }
   function selectQuest(obj)
   {
      if(this.currentItem != obj.target)
      {
         this.currentItem.toggled = false;
         this.currentItem._alpha = (this.currentItem._parent.id % 2 + 1) * 50;
         this.currentItem = obj.target;
         this.currentItem._alpha = 100;
         this.showQuestDescription(this.currentItem._parent.data);
      }
      else
      {
         this.currentItem.toggled = true;
      }
   }
   function showQuestDescription(questTask)
   {
      this.cancelQuest_btn.enabled = true;
      this.currentQuestTask = questTask;
      this.infoPan.setSize(420,380);
      this.infoCont = this.infoPan.fillContent();
      var _loc9_ = this.infoCont.attachMovie("questGroupTitle","questGroupTitle" + this.infoCont.getNextHighestDepth(),this.infoCont.getNextHighestDepth());
      _loc9_.title_txt.html = true;
      _loc9_.title_txt.htmlText = this.parseString(questTask.quest.name);
      var _loc10_ = this.infoCont._height;
      var _loc2_ = this.infoCont.attachMovie("questdescriptionText","questdescriptionText" + this.infoCont.getNextHighestDepth(),this.infoCont.getNextHighestDepth());
      _loc2_.description_txt.autoSize = true;
      _loc2_.description_txt.wordWrap = true;
      _loc2_.description_txt.multiline = true;
      _loc2_.description_txt.html = true;
      _loc2_.description_txt.htmlText = "<br>" + this.parseString(questTask.quest.start_desc);
      _loc2_._y = _loc10_;
      if(questTask.quest.repeatable)
      {
         _loc2_.description_txt.htmlText += "<b>Задание является повторяемым.</b> ";
      }
      if(questTask.quest.party_size != 0)
      {
         _loc2_.description_txt.htmlText += "<b>Количество человек, на которых рассчитано задание:</b> " + questTask.quest.party_size + " шт.";
      }
      var _loc12_ = lol.core.Master.getInstance().gamer.attributes;
      var _loc4_ = _loc12_.skillArray;
      var _loc5_ = true;
      for(var _loc6_ in _loc4_)
      {
         if(_loc4_[_loc6_].level >= questTask.quest.level)
         {
            _loc5_ = false;
         }
      }
      if(_loc5_ && questTask.quest.level != 0)
      {
         _loc2_.description_txt.htmlText += "<b>Необходимый уровень для выполнения задания:</b> " + questTask.quest.level;
      }
      if(questTask.quest.rew_loc)
      {
         _loc2_.description_txt.htmlText += "<b>Внимание: после выполнения задания Вас переместят в другое место.</b> ";
      }
      var _loc8_ = this.currentQuestTask.quest.getMissionStatus();
      if(_loc8_ != "")
      {
         _loc2_.description_txt.htmlText += "<br><b>Статус выполнения задания:</b> " + _loc8_;
      }
      var _loc7_ = this.currentQuestTask.quest.getRewardItems();
      var _loc11_ = this.currentQuestTask.quest.num_rew_obj;
      if(_loc7_.length != 0)
      {
         this.buildRewardItems(_loc7_,_loc11_);
      }
      _loc2_ = this.createDescriptionText();
      _loc2_._y = this.getNextLowestPoint() + 10;
      if(this.currentQuestTask.quest.rew_afro)
      {
         _loc2_.description_txt.htmlText += "<br><b>За это задание вы также получите " + this.currentQuestTask.quest.rew_afro + " афро</b> ";
      }
      if(this.currentQuestTask.quest.rew_gold)
      {
         _loc2_.description_txt.htmlText += "<br><b>За это задание вы также получите " + Number(this.currentQuestTask.quest.rew_gold) / 100 + " унций золота</b> ";
      }
      this.infoPan.chekSize();
   }
   function buildRewardItems(objArr, num_objArr, type)
   {
      var _loc9_ = this.createDescriptionText();
      if(objArr.length > 1)
      {
         _loc9_.description_txt.htmlText += "<b>Вы сможете выбрать одну из следующих наград:</b> ";
      }
      else
      {
         _loc9_.description_txt.htmlText += "<b>Вы получите:</b> ";
      }
      var _loc6_ = this.infoPan.content;
      _loc9_._y = this.getNextLowestPoint();
      var _loc3_ = 0;
      var _loc4_;
      var _loc5_;
      var _loc2_;
      while(_loc3_ < objArr.length)
      {
         _loc4_ = objArr[_loc3_];
         _loc5_ = _loc6_.getNextHighestDepth();
         _loc2_ = _loc6_.attachMovie("extItemCont","item" + _loc3_,_loc5_);
         _loc2_.attachIconEnabled = true;
         _loc2_.showHeapCount = true;
         _loc4_.setProp("size",num_objArr[_loc3_]);
         _loc2_.attachIcon(_loc4_);
         _loc2_.priceEnabled = false;
         _loc2_.id = _loc3_;
         _loc2_.item = _loc4_;
         if(_loc3_ % 2 == 0)
         {
            _loc2_._y = this.getNextLowestPoint() + 10;
         }
         else
         {
            _loc2_._y = this.getNextLowestPoint() - _loc2_._height;
            _loc2_._x = _loc2_._width + 30;
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function _onPressAnnotation(obj)
   {
      var _loc1_ = obj.target.item;
      var _loc5_ = obj.target;
      var _loc3_ = lol.core.SceneShifter.openNewWindow("annotation",undefined,undefined,_loc1_.id);
      var _loc2_ = _loc3_.content;
      _loc2_.showInfo(_loc1_);
   }
   function _onMouseOver(obj)
   {
      var _loc6_ = obj.target.item;
      var _loc3_ = obj.target;
      var _loc2_ = this.attachMovie("annotation","annotation",2000);
      var _loc5_ = _loc3_._x + _loc3_._width + 10 + this.infoPan._x + this.infoPan.cont_mc._x;
      var _loc4_ = _loc3_._y + this.infoPan._y + this.infoPan.cont_mc._y;
      _loc2_._x = _loc5_;
      _loc2_._y = _loc4_;
      _loc2_.showInfo(_loc6_);
   }
   function _onMouseOut(obj)
   {
      if(this.currentItem == obj.target)
      {
         this.currentItem.toggled_frame = true;
      }
      this.annotation.removeMovieClip();
   }
   function cancelQuest()
   {
      var _loc3_ = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = _loc3_.content;
      _loc2_.label = "Отказаться от выполнения задания?";
      _loc2_.addEventListener("click",this,this.cancelQuestAck);
   }
   function cancelQuestAck(obj)
   {
      obj.target.removeEventListener("click",this,this.cancelQuestAck);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this.questInspector.cancelQuest(this.currentQuestTask);
      }
   }
   function questsUpdate()
   {
      for(var _loc2_ in this.questItemList)
      {
         this.questItemList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectQuest);
      }
      this.infoCont = this.infoPan.fillContent();
      this.buildQuestList();
      this.cancelQuest_btn.enabled = false;
      this.currentItem = null;
      delete this.currentItem;
   }
   function parseString(strIn)
   {
      var _loc1_ = lol.utils.ParseString.replaceAll(strIn,"\\","");
      return lol.utils.ParseString.replaceAll(_loc1_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
   }
   function gotoQuestInfoInterface()
   {
      var _loc2_ = lol.core.SceneShifter._sl.getWindow("charInterface").content;
      _loc2_.charPers_btn._enabled = true;
      this.questList_btn._enabled = false;
      lol.core.SceneShifter.openSlideWindow("questInfoInterface");
   }
   function createDescriptionText()
   {
      var _loc3_ = this.infoPan.content;
      var _loc4_ = _loc3_.attachMovie("questdescriptionText","questdescriptionText" + _loc3_.getNextHighestDepth(),_loc3_.getNextHighestDepth());
      var _loc2_ = _loc4_.description_txt;
      _loc2_.autoSize = true;
      _loc2_.wordWrap = true;
      _loc2_.multiline = true;
      _loc2_.html = true;
      return _loc4_;
   }
   function getNextLowestPoint()
   {
      return Math.round(this.infoPan.content._height);
   }
}
