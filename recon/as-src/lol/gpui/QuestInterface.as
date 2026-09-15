class lol.gpui.QuestInterface extends lol.gpui.GPUIObject
{
   var annotation;
   var attachMovie;
   var back_btn;
   var button_Shine;
   var close_btn;
   var cont;
   var currentItem;
   var currentList;
   var currentQuest;
   var currentQuestTask;
   var currentStatus;
   var currentType;
   var dispatchEvent;
   var getQuestName;
   var getQuest_btn;
   var loadingAnimation;
   var questGArr;
   var questInspector;
   var questPan;
   var questTArr;
   var takeQuestName;
   var takeQuest_btn;
   function QuestInterface()
   {
      super();
      this.doLater("init");
      this.questInspector = lol.core.quests.QuestInspector.getInstance();
      this.getQuest_btn._visible = false;
      this.button_Shine._visible = false;
      this.takeQuest_btn._visible = false;
      this.back_btn._visible = false;
      lol.core.SceneShifter.locationScreen.centerChar();
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.getQuest_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getQuest);
      this.takeQuest_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeQuest);
      this.back_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.back);
      this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
      this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE_STATUS,this,this.questsStatusUpdate);
      lol.core.SceneShifter.hotKeyManager.addFilter("quest");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.getTakeQuest);
      this.questGArr = this.questInspector.getGQs();
      this.questTArr = this.questInspector.getTQs();
      this.turnButtonShine();
      if(this.questGArr.length == 1 && this.questTArr.length == 0)
      {
         this.openDescription(this.questGArr[0],"get");
      }
      else if(this.questGArr.length == 0 && this.questTArr.length == 1)
      {
         this.openDescription(this.questTArr[0],"take");
      }
      else
      {
         this.buildQuestList();
      }
   }
   function turnButtonShine()
   {
      if(lol.core.Master.getInstance().gamer.attributes.level == 0)
      {
         this.button_Shine._visible = true;
      }
      else
      {
         this.button_Shine._visible = false;
      }
   }
   function close()
   {
      var _loc2_ = lol.core.Master.getInstance();
      var _loc5_ = _loc2_.gamer.trade;
      var _loc3_ = _loc2_.gamer.upgrade;
      var _loc4_ = _loc2_.gamer.training;
      _loc5_.close();
      _loc3_.close();
      _loc4_.close();
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.killQuestButtons();
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.getQuest_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getQuest);
      this.takeQuest_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeQuest);
      this.back_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.back);
      this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
      this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE_STATUS,this,this.questsStatusUpdate);
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.hotKeyManager.removeFilter("quest");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.getTakeQuest);
   }
   function killQuestButtons()
   {
      for(var _loc2_ in this.currentList)
      {
         this.currentList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectQuest);
      }
   }
   function rebuildQuestList()
   {
      this.killQuestButtons();
      this.buildQuestList();
   }
   function buildQuestList()
   {
      this.currentStatus = "list";
      this.currentList = new Array();
      this.getQuest_btn._visible = false;
      this.button_Shine._visible = false;
      this.takeQuest_btn._visible = false;
      this.back_btn._visible = false;
      this.questGArr = this.questInspector.getGQs();
      this.questTArr = this.questInspector.getTQs();
      this.questPan.setSize(414,380);
      this.cont = this.questPan.fillContent();
      var _loc9_ = lol.core.Master.getInstance();
      if(this.questGArr.length == 0 && this.questTArr.length == 0)
      {
         this.cont.attachMovie("noquest_mc","noquest_mc" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
      }
      var _loc8_;
      var _loc6_;
      var _loc4_;
      var _loc2_;
      if(this.questGArr.length != 0)
      {
         _loc8_ = this.cont.attachMovie("questGroupTitle","questGroupTitle" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
         _loc8_.title_txt.text = "Доступные задания";
         _loc8_._y = 0;
         _loc6_ = this.getNextLowestPoint();
         _loc4_ = 0;
         for(var _loc7_ in this.questGArr)
         {
            _loc2_ = this.cont.attachMovie("questItem","questItem" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
            _loc2_._y = Math.round(_loc4_ * _loc2_._height + _loc6_);
            _loc2_.id = _loc4_;
            _loc2_.data = this.questGArr[_loc7_];
            _loc2_.type = "get";
            _loc2_.title_txt.html = true;
            _loc2_.title_txt.htmlText = "• " + this.parseString(this.questGArr[_loc7_].name);
            _loc2_.bg._alpha = (_loc4_ % 2 + 1) * 50;
            this.doLater("initBg",[_loc2_.bg]);
            this.currentList.push(_loc2_);
            _loc4_ = _loc4_ + 1;
         }
      }
      var _loc3_;
      var _loc5_;
      if(this.questTArr.length != 0)
      {
         _loc6_ = this.getNextLowestPoint();
         _loc4_ = 0;
         for(_loc7_ in this.questTArr)
         {
            if(this.questTArr[_loc7_].complete)
            {
               if(!_loc3_)
               {
                  _loc3_ = new Array();
               }
               _loc3_.push(this.questTArr[_loc7_]);
            }
            else
            {
               if(!_loc5_)
               {
                  _loc5_ = this.cont.attachMovie("questGroupTitle","questGroupTitle" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
                  _loc5_.title_txt.text = "Незавершенные задания";
                  _loc5_._y = _loc6_;
                  _loc6_ = this.getNextLowestPoint();
               }
               _loc2_ = this.cont.attachMovie("questItem","questItem" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
               _loc2_._y = Math.round(_loc4_ * _loc2_._height + _loc6_);
               _loc2_.id = _loc4_;
               _loc2_.data = this.questTArr[_loc7_];
               _loc2_.type = "take";
               _loc2_.title_txt.text = "• " + this.parseString(this.questTArr[_loc7_].quest.name);
               _loc2_.bg._alpha = (_loc4_ % 2 + 1) * 50;
               this.doLater("initBg",[_loc2_.bg]);
               this.currentList.push(_loc2_);
               _loc4_ = _loc4_ + 1;
            }
         }
      }
      if(_loc3_)
      {
         _loc6_ = this.getNextLowestPoint();
         _loc8_ = this.cont.attachMovie("questGroupTitle","questGroupTitle" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
         _loc8_.title_txt.text = "Завершенные задания";
         _loc8_._y = _loc6_;
         _loc6_ = this.getNextLowestPoint();
         _loc4_ = 0;
         for(_loc7_ in _loc3_)
         {
            _loc2_ = this.cont.attachMovie("questItem","questItem" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
            _loc2_._y = Math.round(_loc4_ * _loc2_._height + _loc6_);
            _loc2_.id = _loc4_;
            _loc2_.data = _loc3_[_loc7_];
            _loc2_.type = "take";
            _loc2_.title_txt.text = "• " + this.parseString(_loc3_[_loc7_].quest.name);
            _loc2_.bg._alpha = (_loc4_ % 2 + 1) * 50;
            this.doLater("initBg",[_loc2_.bg]);
            this.currentList.push(_loc2_);
            _loc4_ = _loc4_ + 1;
         }
      }
      this.questPan.chekSize();
   }
   function initBg(mc)
   {
      mc.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectQuest);
   }
   function selectQuest(obj)
   {
      var _loc2_ = obj.target._parent;
      this.openDescription(_loc2_.data,_loc2_.type);
   }
   function ReopenDescription(obj)
   {
      var _loc2_ = obj.quest;
      if(_loc2_)
      {
         _loc2_.removeEventListener("questLoaded",this,this.ReopenDescription);
         this.loadingAnimation.removeMovieClip();
         this.openDescription(_loc2_,this.currentType);
      }
   }
   function openDescription(data, type)
   {
      this.currentStatus = "description";
      if(type)
      {
         this.currentType = type;
      }
      if(data instanceof lol.core.quests.Quest)
      {
         this.currentQuest = data;
      }
      else if(data instanceof lol.core.quests.QuestTask)
      {
         this.currentQuest = data.quest;
      }
      this.killQuestButtons();
      this.questPan.setSize(418,380);
      this.cont = this.questPan.fillContent();
      if(!this.currentQuest.initialized)
      {
         this.questInspector.loadUnknownQuest(this.currentQuest);
         this.currentQuest.addEventListener("questLoaded",this,this.ReopenDescription);
         this.createLoadingScreen();
         this.questPan.chekSize();
         return undefined;
      }
      this.currentQuestTask = data;
      this[type + "Quest_btn"]._visible = true;
      this.turnButtonShine();
      if(this.questGArr.length > 1 || this.questTArr.length > 0)
      {
         this.back_btn._visible = true;
      }
      var _loc7_ = this.cont.attachMovie("questGroupTitle","questGroupTitle" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
      var _loc12_ = this.currentQuest.name;
      _loc7_.title_txt.html = true;
      _loc7_.title_txt.htmlText = this.parseString(_loc12_);
      _loc7_._y = 0;
      var _loc2_ = this.createDescriptionText();
      _loc2_._y = this.getNextLowestPoint();
      if(type == "get")
      {
         _loc2_.description_txt.htmlText = this.parseString(this.currentQuest.start_desc);
      }
      else if(data.complete)
      {
         _loc2_.description_txt.htmlText = this.parseString(this.currentQuest.finish_desc);
         this.takeQuest_btn._visible = true;
         this.turnButtonShine();
      }
      else
      {
         _loc2_.description_txt.htmlText = this.parseString(this.currentQuest.notfinish_desc);
         this.takeQuest_btn._visible = false;
         this.button_Shine._visible = false;
      }
      var _loc11_;
      var _loc3_;
      var _loc4_;
      var _loc9_;
      var _loc10_;
      if(_loc2_.description_txt.htmlText == "undefined")
      {
         _loc2_.description_txt.htmlText = "Загружается описание...";
      }
      else
      {
         if(this.currentQuest.repeatable)
         {
            _loc2_.description_txt.htmlText += "<br>Задание является <b>повторяемым.</b> ";
         }
         if(this.currentQuest.party_size != 0)
         {
            _loc2_.description_txt.htmlText += "<br><b>Количество человек, на которых рассчитано задание:</b> " + this.currentQuest.party_size + " шт.";
         }
         _loc11_ = lol.core.Master.getInstance().gamer.attributes;
         _loc3_ = _loc11_.skillArray;
         _loc4_ = true;
         for(var _loc6_ in _loc3_)
         {
            if(_loc3_[_loc6_].level >= this.currentQuest.level)
            {
               _loc4_ = false;
            }
         }
         if(_loc4_ && this.currentQuest.level != 0)
         {
            _loc2_.description_txt.htmlText += "<br><b>Необходимый уровень для выполнения задания:</b> " + this.currentQuest.level;
         }
         _loc9_ = this.currentQuest.getRewardItems();
         _loc10_ = this.currentQuest.num_rew_obj;
         if(_loc9_.length != 0)
         {
            this.buildRewardItems(_loc9_,_loc10_,type);
         }
         _loc2_ = this.createDescriptionText();
         _loc2_._y = this.getNextLowestPoint();
         if(this.currentQuest.rew_loc)
         {
            _loc2_.description_txt.htmlText = "<br><b>Внимание:</b> после выполнения задания Вас переместят в другое место.";
         }
         if(this.currentQuest.rew_afro)
         {
            _loc2_.description_txt.htmlText += "<br><b>За это задание вы также получите " + this.currentQuest.rew_afro + " афро</b> ";
         }
         if(this.currentQuest.rew_gold)
         {
            _loc2_.description_txt.htmlText += "<br><b>За это задание вы также получите " + Number(this.currentQuest.rew_gold) / 100 + " унций золота</b> ";
         }
      }
      this.questPan.chekSize();
   }
   function buildRewardItems(objArr, num_objArr, type)
   {
      var _loc7_ = this.createDescriptionText();
      if(objArr.length > 1)
      {
         if(type == "take" && this.currentQuestTask.complete)
         {
            _loc7_.description_txt.htmlText += "<b>Вы можете выбрать одну из следующих наград:</b> ";
         }
         else
         {
            _loc7_.description_txt.htmlText += "<b>Вы сможете выбрать одну из следующих наград:</b> ";
         }
      }
      else
      {
         _loc7_.description_txt.htmlText += "<b>Вы получите:</b> ";
      }
      _loc7_._y = this.getNextLowestPoint();
      var _loc3_;
      var _loc6_;
      var _loc2_;
      for(var _loc8_ in objArr)
      {
         _loc3_ = objArr[_loc8_];
         _loc6_ = this.cont.getNextHighestDepth();
         _loc2_ = this.cont.attachMovie("extItemCont","item" + _loc8_,_loc6_);
         _loc2_.attachIconEnabled = true;
         _loc2_.showNumOfObject = num_objArr[_loc8_];
         _loc2_.showHeapCount = true;
         _loc3_.sellnum = num_objArr[_loc8_];
         _loc3_.setProp("size",num_objArr[_loc8_]);
         _loc2_.attachIcon(_loc3_);
         _loc2_.priceEnabled = false;
         _loc2_.id = objArr.length - Number(_loc8_) - 1;
         _loc2_.item = _loc3_;
         _loc2_.showHeapCount = true;
         if(objArr.length > 1)
         {
            _loc2_.addEventListener(lol.gpui.ItemContainer.SELECT,this,this.selectRewItem);
         }
         _loc2_.addEventListener("_onRollOutAnnotation",this,this._onMouseOut);
         _loc2_.addEventListener("_onMouseOut",this,this._onMouseOut);
         if(_loc2_.id % 2 == 0)
         {
            _loc2_._y = this.getNextLowestPoint() + 10;
         }
         else
         {
            _loc2_._y = this.getNextLowestPoint() - _loc2_._height;
            _loc2_._x = _loc2_._width + 30;
         }
      }
      this.currentItem = null;
   }
   function selectRewItem(obj)
   {
      if(this.currentItem != obj.target)
      {
         this.currentItem.toggled_frame = false;
         this.currentItem = obj.target;
      }
      else
      {
         this.currentItem.toggled_frame = true;
      }
   }
   function _onMouseOut(obj)
   {
      if(this.currentItem == obj.target)
      {
         this.currentItem.toggled_frame = true;
      }
   }
   function _onPressAnnotation(obj)
   {
      var _loc2_ = obj.target.item;
      var _loc6_ = obj.target;
      var _loc5_ = lol.core.SceneShifter.openNewWindow("annotation",undefined,undefined,_loc2_.id);
      var _loc3_ = _loc5_.content;
      this.annotation.questRewardSize = obj.target.showNumOfObject;
      _loc3_.showInfo(_loc2_);
   }
   function _onMouseOver(obj)
   {
      var _loc7_ = obj.target.item;
      var _loc3_ = obj.target;
      var _loc2_ = this.attachMovie("annotation","annotation",2000);
      var _loc6_ = _loc3_._x + _loc3_._width + 10 + this.questPan._x + this.questPan.cont_mc._x;
      var _loc5_ = _loc3_._y + this.questPan._y + this.questPan.cont_mc._y;
      _loc2_._x = _loc6_;
      _loc2_._y = _loc5_;
      _loc2_.questRewardSize = obj.target.showNumOfObject;
      _loc2_.showInfo(_loc7_);
   }
   function getTakeQuest()
   {
      if(this.currentStatus == "description")
      {
         if(this.currentType == "get")
         {
            this.getQuest();
         }
         else if(this.currentType == "take")
         {
            this.takeQuest();
         }
      }
   }
   function getQuest(obj)
   {
      var _loc2_;
      if(this.currentQuest)
      {
         if(this.questInspector.getCurrentQuestLength() >= lol.core.GConstatns.getMaxNumberOfQuests())
         {
            _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
            _loc2_.content.label = lol.MessageString.MAX_NUMBER_OF_QUESTS;
         }
         else
         {
            this.button_Shine._visible = false;
            this.getQuestName = this.currentQuest.name;
            this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
            this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.getAck);
            this.questInspector.getQuest(this.currentQuest);
         }
      }
   }
   function getAck(obj)
   {
      var _loc2_ = "Получено новое задание &lt;" + this.getQuestName + "&gt;";
      var _loc3_ = lol.core.SceneShifter.newServiceMessage(_loc2_,lol.gpui.ServiceMessage.QUEST_MESSAGE);
      obj.target.removeEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.getAck);
      this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
      this.rebuildQuestList();
   }
   function takeQuest(obj)
   {
      var _loc3_;
      var _loc2_;
      if(this.currentQuestTask)
      {
         if(this.currentItem.id == undefined && this.currentQuest.getRewardItems().length > 1)
         {
            _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
            _loc3_.content.label = "Выберите награду,\rпрежде чем завершить задание";
         }
         else
         {
            this.takeQuestName = this.currentQuestTask.quest.name;
            this.questInspector.removeEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
            this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.takeAck);
            _loc2_ = this.currentItem.id == undefined ? 0 : this.currentItem.id;
            this.questInspector.takeQuest(this.currentQuestTask,_loc2_);
         }
      }
   }
   function takeAck(obj)
   {
      var _loc2_;
      var _loc3_;
      if(this.takeQuestName != undefined)
      {
         _loc2_ = "Задание &lt;" + this.takeQuestName + "&gt; завершено";
         _loc3_ = lol.core.SceneShifter.newServiceMessage(_loc2_,lol.gpui.ServiceMessage.QUEST_MESSAGE_COMPLETE);
      }
      obj.target.removeEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.takeAck);
      this.questInspector.addEventListener(lol.core.quests.QuestEvent.UPDATE,this,this.questsUpdate);
      this.rebuildQuestList();
   }
   function back(obj)
   {
      this.getQuest_btn._visible = false;
      this.button_Shine._visible = false;
      this.takeQuest_btn._visible = false;
      this.back_btn._visible = false;
      this.buildQuestList();
   }
   function questsUpdate(obj)
   {
      if(this.currentStatus == "list" && !obj.quest)
      {
         this.rebuildQuestList();
      }
      else if(this.currentStatus == "description" && obj.quest && obj.quest.typeID == this.currentQuest.typeID)
      {
         if(this.currentType == "get")
         {
            this.openDescription(this.currentQuest,this.currentType);
         }
         else
         {
            this.openDescription(this.currentQuestTask,this.currentType);
         }
      }
   }
   function parseString(strIn)
   {
      var _loc1_ = lol.utils.ParseString.replaceAll(strIn,"\\","");
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"<hint>","<font color=\"#315d07\">");
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"</hint>","</font>");
      return lol.utils.ParseString.replaceAll(_loc1_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
   }
   function questsStatusUpdate(obj)
   {
      var _loc2_ = obj.quests;
      var _loc4_;
      var _loc5_;
      var _loc3_;
      if(_loc2_.length > 1)
      {
         this.rebuildQuestList();
      }
      else if(_loc2_.length == 1)
      {
         _loc4_ = _loc2_[0].quest;
         _loc5_ = _loc2_[0].type;
         this.openDescription(_loc4_,_loc5_);
      }
      else
      {
         _loc3_ = lol.core.Master.getInstance();
         this.questGArr = this.questInspector.getGQs();
         this.questTArr = this.questInspector.getTQs();
         if(!_loc3_.gamer.trade && !_loc3_.gamer.upgrade && !_loc3_.gamer.training && this.questGArr.length == 0 && this.questTArr.length == 0)
         {
            this.close();
         }
      }
   }
   function createLoadingScreen()
   {
      var _loc2_ = this.questPan.content;
      this.loadingAnimation = _loc2_.attachMovie("loadingAnimation","loadingAnimation" + _loc2_.getNextHighestDepth(),_loc2_.getNextHighestDepth());
      this.loadingAnimation._x = 200;
      this.loadingAnimation._visible = true;
   }
   function createDescriptionText()
   {
      var _loc3_ = this.questPan.content;
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
      return Math.round(this.questPan.content._height);
   }
}
