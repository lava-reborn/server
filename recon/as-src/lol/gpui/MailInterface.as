class lol.gpui.MailInterface extends lol.gpui.StaffInterface
{
   var _xmouse;
   var _ymouse;
   var afro_txt;
   var answer_btn;
   var attachItems_mc;
   var attachItems_txt;
   var attachMoney_txt;
   var attachMovie;
   var bag_mc;
   var blockRightSide_mc;
   var body_txt;
   var buyItems_btn;
   var clanLetter_rbtn;
   var curPage;
   var curType_btn;
   var curletter_id;
   var currDDOperation;
   var currItem;
   var currMailList;
   var currSort;
   var ddOperation_arr;
   var delivery_rbtn;
   var doLater;
   var dragCont;
   var dragItemMc;
   var dragNdrop;
   var eClanLetter_rbtn;
   var eDelivery_rbtn;
   var eLetter_rbtn;
   var eTradeLetter_rbtn;
   var equipment;
   var exchangeMainSize;
   var exchangePanCost_num;
   var exchangePan_cost_mod;
   var exchangePan_showCostInGold;
   var filterPan;
   var getItems_btn;
   var gold_txt;
   var gotoAndStop;
   var heapSepItem;
   var inboxList;
   var inbox_btn;
   var inbox_txt;
   var letterPan;
   var letter_rbtn;
   var listIconPan;
   var mailInspector;
   var mailPan;
   var mailParam;
   var master;
   var moneyPan_mc;
   var nameEnabled_mc;
   var name_txt;
   var newLetter_btn;
   var onMouseMove;
   var outboxList;
   var outbox_btn;
   var outbox_txt;
   var prevAlpha;
   var priceEnabled;
   var prise_mc;
   var prise_txt;
   var refuse_btn;
   var removeLetter_btn;
   var send_btn;
   var sepItem;
   var slots;
   var sortByDate_btn;
   var sortByName_btn;
   var sortMask;
   var subj_txt;
   var tradeLetter_rbtn;
   var weightPan;
   var inbox_frame = 1;
   var outbox_frame = 1;
   var newLetter_frame = 2;
   var goldOperation_bool = false;
   var loadInboxFlag = false;
   var loadOutboxFlag = false;
   var showInboxFlag = true;
   var showOutboxFlag = true;
   var getInboxFlag = true;
   var getOutboxFlag = true;
   var ddFlag = false;
   function MailInterface()
   {
      super();
      this.master = lol.core.Master.getInstance();
      this.mailInspector = lol.core.mail.MailInspector.getInstance();
      this.equipment = this.master.gamer.equipment;
      this.doLater("init");
      this.inboxList = this.mailInspector.getInbox();
      if(!this.inboxList)
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.getInboxList);
      }
      else
      {
         this.loadInboxFlag = true;
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newInboxLetter);
      }
      this.outboxList = this.mailInspector.getOutbox();
      if(!this.outboxList)
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_OUTBOX,this,this.getOutboxList);
      }
      else
      {
         this.loadOutboxFlag = true;
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newOutboxLetter);
      }
      lol.core.SceneShifter._ref.currentScene.enabledHotKey(false);
   }
   function init()
   {
      this.inbox_btn.toggled = true;
      this.inbox_btn._enabled = false;
      this.curPage = this.inbox_btn;
      this.inbox_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      this.outbox_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      this.newLetter_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      this.gotoAndStop(this.inbox_frame);
      this.doLater("initInboxPage");
      lol.core.SceneShifter.hotKeyManager.addFilter("mail");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function kill()
   {
      this.killNewLetterPage();
      this.killInboxPage();
      this.killOutboxPage();
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newInboxLetter);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newOutboxLetter);
      this.inbox_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      this.outbox_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      this.newLetter_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectPage);
      lol.core.SceneShifter.hotKeyManager.removeFilter("mail");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function close()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function getInboxList()
   {
      this.loadInboxFlag = true;
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.getInboxList);
      this.updateBtn();
      if(!this.showInboxFlag && this.inbox_btn.toggled)
      {
         this.buildMailList("inbox");
      }
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newInboxLetter);
   }
   function getOutboxList()
   {
      this.loadOutboxFlag = true;
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_OUTBOX,this,this.getOutboxList);
      this.updateBtn();
      if(!this.showOutboxFlag && this.outbox_btn.toggled)
      {
         this.buildMailList("outbox");
      }
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.newOutboxLetter);
   }
   function selectPage(obj)
   {
      this.curPage._enabled = true;
      this.curPage.toggled = false;
      this.curPage = obj.target;
      this.curPage._enabled = false;
      this.curPage.toggled = true;
      if(this.curPage == this.inbox_btn)
      {
         this.gotoAndStop(this.inbox_frame);
         this.doLater("initInboxPage");
      }
      else if(this.curPage == this.outbox_btn)
      {
         this.gotoAndStop(this.outbox_frame);
         this.doLater("initOutboxPage");
      }
      else
      {
         this.gotoAndStop(this.newLetter_frame);
         this.doLater("initNewLetterPage");
      }
   }
   function selectPageExt(btn)
   {
      this.curPage._enabled = true;
      this.curPage.toggled = false;
      this.curPage = btn;
      this.curPage._enabled = false;
      this.curPage.toggled = true;
      if(this.curPage == this.inbox_btn)
      {
         this.gotoAndStop(this.inbox_frame);
         this.doLater("initInboxPage");
      }
      else if(this.curPage == this.outbox_btn)
      {
         this.gotoAndStop(this.outbox_frame);
         this.doLater("initOutboxPage");
      }
      else
      {
         this.gotoAndStop(this.newLetter_frame);
         this.doLater("initNewLetterPage");
      }
   }
   function updateBtn()
   {
      var _loc2_ = this.mailInspector.getInbox();
      var _loc3_ = this.mailInspector.getOutbox();
      var _loc5_ = !_loc2_ ? 0 : _loc2_.length;
      var _loc4_ = this.getUnreadLettersNumber(_loc2_);
      var _loc6_ = !_loc3_ ? 0 : _loc3_.length;
      this.inbox_txt.htmlText = "<b>Входящие (" + _loc4_ + "/" + _loc5_ + ")</b>";
      this.outbox_txt.htmlText = "<b>Отправленные (" + _loc6_ + ")</b>";
   }
   function initInboxPage()
   {
      this.killNewLetterPage();
      this.moneyPan_mc.gotoAndStop(1);
      this.gold_txt = this.moneyPan_mc.gold_txt;
      this.afro_txt = this.moneyPan_mc.afro_txt;
      this.attachItems_mc.bagPan.setSize(180,250);
      this.getItems_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getItems);
      this.buyItems_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getItems);
      this.buyItems_btn._visible = false;
      this.answer_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.answer);
      this.removeLetter_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.refuse_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.blockRightSide_mc._visible = false;
      this.buildMailList();
      if(this.loadInboxFlag)
      {
         this.buildMailList("inbox");
      }
      else
      {
         this.showInboxFlag = false;
      }
      this.sortByDate_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.sortByName_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.sortByDate_btn.data = "fullDate";
      this.sortByName_btn.data = "name";
      var _loc3_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_BY);
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_REVERSE);
      this.sortByDate_btn._alpha = 0;
      this.sortByName_btn._alpha = 0;
      if(_loc3_ == "name")
      {
         this.sortByName_btn.toggled = _loc2_;
         this.currSort = this.sortByName_btn;
         this.sortByName_btn._alpha = 100;
      }
      else
      {
         this.sortByDate_btn.toggled = _loc2_;
         this.currSort = this.sortByDate_btn;
         this.sortByDate_btn._alpha = 100;
      }
   }
   function killInboxPage()
   {
      this.getItems_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getItems);
      this.buyItems_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.getItems);
      this.answer_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.answer);
      this.removeLetter_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.refuse_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.killMailList();
   }
   function newInboxLetter(_mailEvent)
   {
      if(this.inbox_btn.toggled)
      {
         this.buildMailList();
      }
      this.updateBtn();
   }
   function newOutboxLetter(_mailEvent)
   {
      if(this.outbox_btn.toggled)
      {
         this.buildMailList();
      }
      this.updateBtn();
   }
   function buildMailList(typeFlag)
   {
      this.killMailList();
      this.updateBtn();
      this.letterPan.fillContent();
      this.attachItems_mc.removeAllItems();
      this.afro_txt.text = "";
      this.gold_txt.text = "";
      this.answer_btn.enabled = false;
      this.getItems_btn.enabled = false;
      this.buyItems_btn._visible = false;
      this.getItems_btn._visible = true;
      this.removeLetter_btn.enabled = false;
      this.refuse_btn._visible = false;
      this.removeLetter_btn._visible = true;
      this.answer_btn._visible = true;
      var _loc9_;
      if(this.inbox_btn.toggled)
      {
         _loc9_ = this.mailInspector.getInbox();
      }
      else if(this.outbox_btn.toggled)
      {
         this.buyItems_btn._visible = false;
         this.getItems_btn._visible = false;
         this.removeLetter_btn.enabled = false;
         this.refuse_btn._visible = false;
         this.answer_btn._visible = false;
         _loc9_ = this.mailInspector.getOutbox();
      }
      this.mailPan.setSize(265,340);
      var _loc6_ = this.mailPan.fillContent();
      var _loc7_ = this.sortArray(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_BY),lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_REVERSE));
      var _loc8_ = 0;
      var _loc5_ = 0;
      var _loc3_;
      var _loc2_;
      var _loc4_;
      while(_loc5_ < _loc7_.length)
      {
         _loc3_ = _loc7_[_loc5_].letterObj;
         _loc2_ = _loc6_.attachMovie("mailListItem","mailListItem" + _loc6_.getNextHighestDepth(),_loc6_.getNextHighestDepth());
         _loc2_._y = Math.round(this.getNextLowestPoint()) - 1;
         _loc2_.letterObject = _loc3_;
         _loc2_.fromto_txt.htmlText = !this.inbox_btn.toggled ? "<b><i>Кому</i></b>" : "<b><i>От кого</i></b>";
         _loc2_.name_txt.text = !this.inbox_btn.toggled ? "Кому: " + _loc3_.to : "От: " + _loc3_.from;
         _loc2_.subj_txt.text = !_loc3_.returnLetter ? _loc3_.subj : "Refuse: " + _loc3_.subj;
         _loc2_.date_txt.autoSize = true;
         _loc2_.date_txt.htmlText = _loc3_.parseDate + "<BR>" + _loc3_.time;
         if(!_loc3_.read)
         {
            _loc4_ = new TextFormat();
            _loc4_.bold = true;
            _loc2_.name_txt.setTextFormat(_loc4_);
            _loc2_.subj_txt.setTextFormat(_loc4_);
            _loc2_.date_txt.setTextFormat(_loc4_);
         }
         if(_loc3_.type == 4 || _loc3_.type == 5)
         {
            _loc2_.letterSign_mc.gotoAndStop(3);
         }
         else if(_loc3_.type == 2 || _loc3_.type == 3)
         {
            _loc2_.letterSign_mc.gotoAndStop(2);
         }
         else if(_loc3_.attachObject)
         {
            _loc2_.letterSign_mc.gotoAndStop(4);
         }
         _loc2_.bg._alpha = (_loc8_ % 2 + 1) * 50;
         this.doLater("initBg",[_loc2_.bg]);
         this.currMailList.push(_loc2_);
         _loc8_ = _loc8_ + 1;
         _loc5_ = _loc5_ + 1;
      }
      this.mailPan.chekSize();
   }
   function sortArray(type, reverse)
   {
      var _loc6_ = new Array();
      var _loc5_;
      if(this.inbox_btn.toggled)
      {
         _loc5_ = this.mailInspector.getInbox();
      }
      else if(this.outbox_btn.toggled)
      {
         _loc5_ = this.mailInspector.getOutbox();
      }
      var _loc3_ = 0;
      var _loc4_;
      var _loc2_;
      while(_loc3_ < _loc5_.length)
      {
         _loc4_ = _loc5_[_loc3_];
         _loc2_ = new Object();
         _loc2_.letterObj = _loc4_;
         _loc2_.name = _loc4_.from;
         _loc2_.fullDate = _loc4_.fullDate;
         _loc6_.push(_loc2_);
         _loc3_ = _loc3_ + 1;
      }
      _loc6_.sortOn(type);
      if(!reverse)
      {
         _loc6_.reverse();
      }
      return _loc6_;
   }
   function sortBy_func(obj)
   {
      if(this.currSort != obj.target)
      {
         this.currSort._alpha = 0;
         this.currSort.toggled = false;
         this.currSort = obj.target;
         this.currSort._alpha = 100;
      }
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_BY,this.currSort.data);
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MAIL_LIST_REVERSE,this.currSort.toggled);
      this.buildMailList();
   }
   function killMailList()
   {
      for(var _loc2_ in this.currMailList)
      {
         this.currMailList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectMember);
      }
      this.currItem = null;
      this.currMailList = new Array();
   }
   function initBg(mc)
   {
      mc.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectMember);
   }
   function selectMember(obj)
   {
      if(this.currItem != obj.target._parent)
      {
         this.currItem.bg.toggled = false;
         this.currItem.bg._alpha = this.prevAlpha;
         this.currItem = obj.target._parent;
         this.prevAlpha = this.currItem.bg._alpha;
         if(this.prevAlpha == 50)
         {
            this.currItem.bg._alpha = 100;
         }
      }
      else
      {
         this.currItem.bg.toggled = true;
      }
      var _loc2_ = this.currItem.letterObject;
      var _loc4_ = _loc2_.type;
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.doLaterShowLetterInfo);
      if(_loc2_.full)
      {
         this.showLetterInfo(_loc2_);
      }
      else
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.doLaterShowLetterInfo);
         this.mailInspector.getFullLetter(_loc2_.id);
      }
   }
   function doLaterShowLetterInfo(obj)
   {
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.doLaterShowLetterInfo);
      var _loc3_ = obj.param;
      if(_loc3_.id == this.currItem.letterObject.id)
      {
         this.showLetterInfo(_loc3_);
      }
      var _loc2_;
      if(_loc3_.read)
      {
         _loc2_ = new TextFormat();
         _loc2_.bold = false;
         this.currItem.name_txt.setTextFormat(_loc2_);
         this.currItem.subj_txt.setTextFormat(_loc2_);
         this.currItem.date_txt.setTextFormat(_loc2_);
         this.updateBtn();
      }
   }
   function showLetterInfo(letterObj)
   {
      var _loc7_ = letterObj.type;
      var _loc9_ = !letterObj.inbox ? letterObj.to : letterObj.from;
      var _loc10_ = letterObj.itemArray;
      if(_loc7_ == 2 || _loc7_ == 3)
      {
         this.blockRightSide_mc._visible = true;
      }
      else
      {
         this.blockRightSide_mc._visible = false;
      }
      this.letterPan.setSize(223,320);
      var _loc8_ = this.letterPan.fillContent();
      var _loc6_ = _loc8_.attachMovie("inboxLetter_mc","inboxLetter_mc",_loc8_.getNextHighestDepth());
      _loc6_.fromto_txt.htmlText = !this.inbox_btn.toggled ? "<b><i>Кому</i></b>" : "<b><i>От кого</i></b>";
      _loc6_.name_txt.htmlText = "<b>" + _loc9_ + "</b>";
      _loc6_.date_txt.htmlText = "<b>" + letterObj.parseDate + " " + letterObj.time + "</b>";
      _loc6_.subj_txt.autoSize = true;
      _loc6_.subj_txt.htmlText = "<b>" + letterObj.subj + "</b>";
      _loc6_.body_txt.autoSize = true;
      _loc6_.body_txt.htmlText = letterObj.body + "<BR><BR>";
      _loc6_.body_txt._y = _loc6_.subj_txt._y + _loc6_.subj_txt._height + 10;
      this.letterPan.chekSize();
      this.answer_btn.enabled = !letterObj.inbox ? false : true;
      this.removeLetter_btn.enabled = true;
      this.refuse_btn.enabled = !letterObj.inbox ? false : true;
      this.answer_btn._visible = !letterObj.inbox ? false : true;
      this.refuse_btn._visible = !letterObj.inbox ? false : true;
      this.refuse_btn._visible = (letterObj.type == 4 || letterObj.type == 5) && letterObj.attachObject && letterObj.inbox;
      this.getItems_btn._visible = !(letterObj.type == 4 || letterObj.type == 5) && letterObj.inbox;
      this.buyItems_btn._visible = (letterObj.type == 4 || letterObj.type == 5) && letterObj.inbox;
      this.getItems_btn.enabled = false;
      this.buyItems_btn.enabled = false;
      this.attachItems_mc.removeAllItems();
      var _loc5_;
      var _loc11_;
      var _loc2_;
      var _loc4_;
      if(letterObj.attachObject)
      {
         this.updateAttachObjectsInfo(_loc7_,_loc10_);
         this.afro_txt.text = String(letterObj.afro);
         this.gold_txt.text = String(letterObj.gold / 100);
         _loc5_ = letterObj.itemArray;
         _loc11_ = letterObj.itemDescriptionArr;
         if(_loc5_)
         {
            if(letterObj.inbox)
            {
               this.getItems_btn.enabled = true;
               this.buyItems_btn.enabled = true;
            }
            _loc2_ = 0;
            while(_loc2_ < _loc5_.length)
            {
               _loc4_ = _loc5_[_loc2_];
               this.attachItems_mc.addItem(_loc4_);
               _loc2_ = _loc2_ + 1;
            }
         }
      }
      else
      {
         this.afro_txt.text = "";
         this.gold_txt.text = "";
         this.updateAttachObjectsInfo(_loc7_,[]);
      }
   }
   function updateAttachObjectsInfo(type, itemsArr)
   {
      var _loc3_;
      if(type == 4 || type == 5)
      {
         _loc3_ = "Предложен";
         this.attachMoney_txt.htmlText = "<b><i>Стоимость</i></b>";
      }
      else
      {
         _loc3_ = "Прикреплен";
         this.attachMoney_txt.htmlText = "<b><i>Прикрепленные деньги</i></b>";
      }
      var _loc2_ = itemsArr.length;
      if(!itemsArr)
      {
         _loc2_ = 0;
      }
      var _loc4_;
      if(_loc2_ >= 2 && _loc2_ <= 4)
      {
         _loc4_ = _loc3_ + "о " + _loc2_ + " объекта";
      }
      if(_loc2_ == 1)
      {
         _loc4_ = _loc3_ + " " + _loc2_ + " объект";
      }
      if(_loc2_ == 0 || _loc2_ == 5)
      {
         _loc4_ = _loc3_ + "о " + _loc2_ + " объектов";
      }
      this.attachItems_txt.htmlText = "<b><i>" + _loc4_ + "</i></b>";
   }
   function answer()
   {
      var _loc2_ = this.currItem.letterObject;
      var _loc3_ = _loc2_.from;
      this.killInboxPage();
      this.gotoAndStop(this.newLetter_frame);
      this.curPage._enabled = true;
      this.curPage.toggled = false;
      this.curPage = this.newLetter_btn;
      this.curPage._enabled = false;
      this.curPage.toggled = true;
      this.doLater("initNewLetterPage",[_loc3_,_loc2_.subj]);
   }
   function getItems()
   {
      var _loc2_ = this.currItem.letterObject;
      var _loc4_;
      var _loc3_;
      if(this.master.currentLocation.locInfo.battle || this.master.currentState == lol.core.Master.GLOBAL_STATE)
      {
         this.openAlertWindow("Только в мирных локациях можно забирать посылки");
      }
      else if(_loc2_.type == 4 || _loc2_.type == 5)
      {
         _loc4_ = lol.core.SceneShifter.openNewWindow("query");
         _loc3_ = _loc4_.content;
         _loc3_.label = "Вы уверенны, что хотите купить все прикрепленные к письму предметы?";
         _loc3_.addEventListener("click",this,this._getItems);
      }
      else
      {
         this.__getItems();
      }
   }
   function _getItems(obj)
   {
      obj.target.removeEventListener("click",this,this._getItems);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this.__getItems();
      }
   }
   function checkAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.checkAnswer);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS,this,this.getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND,this,this.getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS,this,this.getItemsAck);
         this.mailInspector.getObjectsFromLetter(this.curletter_id);
      }
   }
   function __getItems()
   {
      var _loc6_ = this.currItem.letterObject;
      var _loc3_ = _loc6_.itemArray;
      var _loc4_ = 0;
      var _loc2_;
      for(var _loc5_ in _loc3_)
      {
         _loc2_ = _loc3_[_loc5_];
         _loc4_ += _loc2_.getProp("_weight");
      }
      var _loc7_;
      if(this.weightPan.getMaxWeight() < this.weightPan.getCurWeight() + _loc4_)
      {
         this.curletter_id = _loc6_.id;
         _loc7_ = lol.core.SceneShifter.openNewWindow("query");
         _loc7_.content.label = "Если вы заберете посылку сейчас, вы будете перегружены. Забрать?";
         _loc7_.content.addEventListener("click",this,this.checkAnswer);
      }
      else
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS,this,this.getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND,this,this.getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS,this,this.getItemsAck);
         this.mailInspector.getObjectsFromLetter(_loc6_.id);
      }
   }
   function getItemsAck(obj)
   {
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS,this,this.getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND,this,this.getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS,this,this.getItemsAck);
      if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS)
      {
         this.openAlertWindow("Объекты не найдены");
      }
      else if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND)
      {
         this.openAlertWindow("Письмо не найдено");
      }
      else if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS)
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_AFRO,this,this._getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_GOLD,this,this._getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_FAILED,this,this._getItemsAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS,this,this._getItemsAck);
      }
   }
   function _getItemsAck(obj)
   {
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_AFRO,this,this._getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_GOLD,this,this._getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_FAILED,this,this._getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS,this,this._getItemsAck);
      if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_FAILED)
      {
         this.openAlertWindow("Не получилось извлечь объекты из письма");
      }
      else if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_AFRO)
      {
         this.openAlertWindow("У вас не хватает денег");
      }
      else if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_YOU_HAVE_NO_GOLD)
      {
         this.openAlertWindow("У вас не хватает денег");
      }
      else if(obj.type == lol.core.mail.MailEvent.GET_OBJECTS_SUCCESS)
      {
         this.openAlertWindow("Объекты извлечены из письма");
         this.buildMailList();
      }
   }
   function removeLetter()
   {
      var _loc3_ = lol.core.SceneShifter.openNewWindow("query");
      var _loc2_ = _loc3_.content;
      _loc2_.label = "Удалить письмо?";
      _loc2_.addEventListener("click",this,this._removeLetter);
   }
   function _removeLetter(obj)
   {
      obj.target.removeEventListener("click",this,this._removeLetter);
      lol.core.SceneShifter.closeWindow("query");
      var _loc3_ = obj.success;
      var _loc4_;
      var _loc2_;
      if(_loc3_)
      {
         obj.removeEventListener("click",this,this._removeLetter);
         _loc4_ = this.currItem.letterObject;
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.REMOVE_LETTER_BAN,this,this.removeLetterAck);
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.REMOVE_INBOX_LETTER,this,this.removeLetterAck);
         _loc2_ = new Array();
         _loc2_.push(_loc4_.id);
         this.mailInspector.removeLetters(_loc2_);
      }
   }
   function removeLetterAck(obj)
   {
      if(obj.type == lol.core.mail.MailEvent.REMOVE_LETTER_BAN)
      {
         this.openAlertWindow("Недопустимое действие");
      }
      else if(obj.type == lol.core.mail.MailEvent.REMOVE_INBOX_LETTER)
      {
         this.buildMailList();
      }
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_NO_OBJECTS,this,this.getItemsAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.GET_OBJECTS_LETTER_NOT_FOUND,this,this.getItemsAck);
   }
   function initOutboxPage()
   {
      if(!this.goldOperation_bool)
      {
         this.moneyPan_mc.gotoAndStop(2);
      }
      else
      {
         this.moneyPan_mc.gotoAndStop(1);
      }
      this.gold_txt = this.moneyPan_mc.gold_txt;
      this.afro_txt = this.moneyPan_mc.afro_txt;
      this.attachItems_mc.dragEnabled = false;
      this.removeLetter_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.blockRightSide_mc._visible = false;
      this.buildMailList();
      if(this.loadOutboxFlag)
      {
         this.buildMailList("outbox");
      }
      else
      {
         this.showOutboxFlag = false;
      }
   }
   function killOutboxPage()
   {
      this.removeLetter_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeLetter);
      this.killMailList();
   }
   function initNewLetterPage(answerName, answerSubj)
   {
      if(!this.goldOperation_bool)
      {
         this.moneyPan_mc.gotoAndStop(2);
      }
      else
      {
         this.moneyPan_mc.gotoAndStop(1);
      }
      this.gold_txt = this.moneyPan_mc.gold_txt;
      this.afro_txt = this.moneyPan_mc.afro_txt;
      this.delivery_rbtn._visible = false;
      this.eDelivery_rbtn._visible = false;
      var _loc3_ = this.master.gamer.clanMemberInfo.clanInfo.reg;
      if(_loc3_ == 0)
      {
         this.clanLetter_rbtn._enabled = false;
         this.eClanLetter_rbtn._enabled = false;
         this.clanLetter_rbtn._alpha = 60;
         this.eClanLetter_rbtn._alpha = 60;
      }
      this.name_txt.tabIndex = 0;
      this.subj_txt.tabIndex = 1;
      this.body_txt.tabIndex = 2;
      this.checkSmth();
      this.nameEnabled_mc._visible = false;
      this.name_txt.text = !answerName ? "" : answerName;
      this.subj_txt.text = !answerSubj ? "" : "Re: " + answerSubj;
      this.body_txt.text = "";
      if(answerName)
      {
         Selection.setFocus(this.body_txt);
      }
      else
      {
         Selection.setFocus(this.name_txt);
      }
      this.blockHotKey();
      this.afro_txt.restrict = "0-9";
      this.gold_txt.restrict = "0-9 .";
      this.afro_txt.onChanged = mx.utils.Delegate.create(this,this.afroOnChanged);
      this.gold_txt.onChanged = mx.utils.Delegate.create(this,this.goldOnChanged);
      this.afro_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKey);
      this.gold_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKey);
      this.name_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKey);
      this.subj_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKey);
      this.body_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKey);
      this.afro_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKey);
      this.gold_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKey);
      this.name_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKey);
      this.subj_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKey);
      this.body_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKey);
      this.blockRightSide_mc._visible = false;
      this.equipment.addEventListener("addItem",this);
      this.equipment.addEventListener("removeItem",this);
      this.equipment.addEventListener("separate",this,this.separateAck);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.addEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.slots = new Array();
      this.slots.bag = this.bag_mc;
      this.slots.mail = this.attachItems_mc;
      this.bag_mc.id = "bag";
      this.bag_mc.alignEnabled = true;
      this.bag_mc.selectGroupAvailable = true;
      this.bag_mc.bagPan.setSize(180,335);
      this.bag_mc.dragEnabled = true;
      this.attachItems_mc.id = "mail";
      this.attachItems_mc.alignEnabled = false;
      this.attachItems_mc.selectGroupAvailable = true;
      this.attachItems_mc.bagPan.setSize(180,250);
      this.attachItems_mc.removeAllItems();
      this.attachItems_mc.dragEnabled = true;
      this.sortMask = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_MASK_MAIL);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.addEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.addEventListener("changeMask",this,this.changeMask);
      this.filterPan.init(this.sortMask);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.attachItems_mc.addEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.attachItems_mc.addEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.attachItems_mc.addEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.attachItems_mc.addEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.attachItems_mc.addEventListener("addItem",this,this.numberOfItems);
      this.attachItems_mc.addEventListener("removeItem",this,this.numberOfItems);
      this.listIconPan.addEventListener("changeView",this,this.changeView);
      this.typeOfList = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.TYPE_OF_LIST_MAIL);
      this.listIconPan.init(this.typeOfList);
      this.bag_mc.typeOfList = this.typeOfList;
      this.attachItems_mc.typeOfList = this.typeOfList;
      this.doLater("initBag",[this.equipment.bag]);
      this.bag_mc.firstAttaching = true;
      this.mailParam = this.mailInspector.getMailParam();
      if(!this.mailParam)
      {
         this.mailInspector.addEventListener(lol.core.mail.MailEvent.CHECK_MAIL_PARAM_UPDATE,this,this.checkMailParamUpdate);
      }
      else
      {
         this.checkMailParamUpdate();
      }
      this.letter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eLetter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.clanLetter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eClanLetter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.tradeLetter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eTradeLetter_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.delivery_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eDelivery_rbtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.send_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendLetter);
      this.letter_rbtn.toggled = true;
      this.updateLetterPrise();
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.sendLetter);
   }
   function blockHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = false;
   }
   function unBlockHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function killNewLetterPage()
   {
      this.equipment.removeEventListener("addItem",this);
      this.equipment.removeEventListener("removeItem",this);
      this.equipment.removeEventListener("separate",this,this.separateAck);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_ERROR,this,this.moveItemError);
      this.equipment.removeEventListener(lol.gpui.DDEvents.TRANSFER_SUCCESS,this,this.moveItemSuccess);
      this.bag_mc.removeEventListener("changeMask",this,this.changeMaskBag);
      this.filterPan.kill();
      this.filterPan.removeEventListener("changeMask",this,this.changeMask);
      this.listIconPan.kill();
      this.listIconPan.removeEventListener("changeView",this,this.changeView);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.CHECK_MAIL_PARAM_UPDATE,this,this.checkMailParamUpdate);
      this.letter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eLetter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.clanLetter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eClanLetter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.tradeLetter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eTradeLetter_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.delivery_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.eDelivery_rbtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.setLetterType);
      this.send_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sendLetter);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.bag_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.attachItems_mc.removeEventListener(lol.gpui.ItemContainer.DOUBLE_CLICK,this,this.doubleClick);
      this.attachItems_mc.removeEventListener(lol.gpui.ItemContainer.MOUSE_UP_ON_THIS,this,this.mouseUpOnItem);
      this.attachItems_mc.removeEventListener(lol.gpui.ItemContainer.START_DRAG_N_DROP,this,this.startDragNDrop);
      this.attachItems_mc.removeEventListener(lol.gpui.ItemContainer.DROP,this,this.dropItem);
      this.attachItems_mc.removeEventListener("addItem",this,this.numberOfItems);
      this.attachItems_mc.removeEventListener("removeItem",this,this.numberOfItems);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.sendLetter);
   }
   function afroOnChanged()
   {
      var _loc3_;
      var _loc2_;
      var _loc4_;
      if(!this.tradeLetter_rbtn.toggled && !this.eTradeLetter_rbtn.toggled)
      {
         _loc3_ = this.master.gamer.attributes.afro;
         _loc2_ = this.afro_txt.text;
         if(_loc2_.charAt(0) == "0" && _loc2_.length > 1)
         {
            _loc2_ = _loc2_.substr(1,_loc2_.length);
            this.afro_txt.text = _loc2_;
         }
         _loc4_ = _loc2_ != "" ? Number(_loc2_) : 0;
         if(_loc4_ > _loc3_)
         {
            this.afro_txt.text = String(_loc3_);
         }
      }
   }
   function goldOnChanged()
   {
      var _loc3_;
      var _loc2_;
      if(!this.tradeLetter_rbtn.toggled && !this.eTradeLetter_rbtn.toggled)
      {
         _loc3_ = this.master.gamer.attributes.gold;
         _loc2_ = this.gold_txt.text != "" ? Number(this.gold_txt.text) : 0;
         _loc2_ *= 100;
         if(_loc2_ > _loc3_)
         {
            this.gold_txt.text = String(_loc3_ / 100);
         }
      }
   }
   function setLetterType(obj)
   {
      this.curType_btn = obj.target;
      this.letter_rbtn.toggled = false;
      this.eLetter_rbtn.toggled = false;
      this.clanLetter_rbtn.toggled = false;
      this.eClanLetter_rbtn.toggled = false;
      this.tradeLetter_rbtn.toggled = false;
      this.eTradeLetter_rbtn.toggled = false;
      this.delivery_rbtn.toggled = false;
      this.eDelivery_rbtn.toggled = false;
      if(this.curType_btn == this.clanLetter_rbtn || this.curType_btn == this.eClanLetter_rbtn)
      {
         this.blockRightSide_mc._visible = true;
         this.nameEnabled_mc._visible = true;
         this.name_txt._visible = false;
      }
      else
      {
         this.blockRightSide_mc._visible = false;
         this.nameEnabled_mc._visible = false;
         this.name_txt._visible = true;
      }
      if(this.curType_btn == this.tradeLetter_rbtn || this.curType_btn == this.eTradeLetter_rbtn)
      {
         this.attachMoney_txt.htmlText = "<b><i>Стоимость</i></b>";
         this.numberOfItems();
      }
      else
      {
         this.attachMoney_txt.htmlText = "<b><i>Прикрепленные деньги</i></b>";
         this.numberOfItems();
      }
      this.curType_btn.toggled = true;
      this.updateLetterPrise();
      this.checkSmth();
   }
   function checkMailParamUpdate(obj)
   {
      obj.removeEventListener(lol.core.mail.MailEvent.CHECK_MAIL_PARAM_UPDATE,this,this.checkMailParamUpdate);
      this.mailParam = this.mailInspector.getMailParam();
      this.letter_rbtn.label_txt.autoSize = true;
      this.eLetter_rbtn.label_txt.autoSize = true;
      this.clanLetter_rbtn.label_txt.autoSize = true;
      this.eClanLetter_rbtn.label_txt.autoSize = true;
      this.tradeLetter_rbtn.label_txt.autoSize = true;
      this.eTradeLetter_rbtn.label_txt.autoSize = true;
      this.delivery_rbtn.label_txt.autoSize = true;
      this.eDelivery_rbtn.label_txt.autoSize = true;
      this.letter_rbtn.label_txt.html = true;
      this.letter_rbtn.label_txt.htmlText = "<B>Обычное письмо</B><BR>Цена: " + this.mailParam.tradeLetter_usual[0] + " А + " + this.mailParam.itemKg_usual[0] + " А за 1 кг. Время доставки: " + this.mailParam.tradeLetter_usual[1] + " мин.";
      this.eLetter_rbtn.label_txt.html = true;
      this.eLetter_rbtn.label_txt.htmlText = "<B>Срочное письмо</B><BR>Цена: " + this.mailParam.tradeLetter_express[0] + " G + " + this.mailParam.itemKg_express[0] + " G за 1 кг. Время доставки: " + this.mailParam.tradeLetter_express[1] + " мин.";
      this.clanLetter_rbtn.label_txt.html = true;
      this.clanLetter_rbtn.label_txt.htmlText = "<B>Внутриклановая рассылка</B><BR>Цена: " + this.mailParam.clanLetter_usual[0] + " А. Время доставки: " + this.mailParam.clanLetter_usual[1] + " мин.";
      this.eClanLetter_rbtn.label_txt.html = true;
      this.eClanLetter_rbtn.label_txt.htmlText = "<B>Срочная внутриклановая рассылка</B><BR>Цена: " + this.mailParam.clanLetter_express[0] + " G. Время доставки: " + this.mailParam.clanLetter_express[1] + " мин.";
      this.tradeLetter_rbtn.label_txt.html = true;
      this.tradeLetter_rbtn.label_txt.htmlText = "<B>Письмо-предложение</B><BR>Цена: " + this.mailParam.tradeLetter_usual[0] + " А + " + this.mailParam.itemKg_usual[0] + " А за 1 кг. Время доставки: " + this.mailParam.tradeLetter_usual[1] + " мин.";
      this.eTradeLetter_rbtn.label_txt.html = true;
      this.eTradeLetter_rbtn.label_txt.htmlText = "<B>Срочное письмо-предложение</B><BR>Цена: " + this.mailParam.tradeLetter_express[0] + " G + " + this.mailParam.itemKg_express[0] + " G за 1 кг. Время доставки: " + this.mailParam.tradeLetter_express[1] + " мин.";
      this.delivery_rbtn.label_txt.html = true;
      this.delivery_rbtn.label_txt.htmlText = "<B>Заказ товара</B><BR>Цена: " + this.mailParam.delivery_usual[0] + " А. Время доставки: " + this.mailParam.delivery_usual[1] + " мин.";
      this.eDelivery_rbtn.label_txt.html = true;
      this.eDelivery_rbtn.label_txt.htmlText = "<B>Срочный заказ товара</B><BR>Цена: " + this.mailParam.delivery_express[0] + " G. Время доставки: " + this.mailParam.delivery_express[1] + " мин.";
      this.updateLetterPrise();
   }
   function sendLetter()
   {
      var _loc3_;
      var _loc4_;
      var _loc2_;
      if(this.name_txt.text == this.master.gamer.playerInfo.name)
      {
         _loc3_ = this.openAlertWindow("Нельзя отправить письмо<BR>самому себе");
         _loc3_.addEventListener("click",this,this.checkName);
      }
      else if(this.name_txt.text == "" && this.name_txt._visible)
      {
         _loc3_ = this.openAlertWindow("Необходимо ввести имя");
         _loc3_.addEventListener("click",this,this.checkName);
      }
      else if(this.subj_txt.text == "")
      {
         _loc3_ = this.openAlertWindow("Необходимо ввести тему письма");
         _loc3_.addEventListener("click",this,this.checkSubj);
      }
      else if((this.tradeLetter_rbtn.toggled || this.eTradeLetter_rbtn.toggled) && this.attachItems_mc.itemList.length == 0)
      {
         this.openAlertWindow("Необходимо прикрепить к письму хотя бы один предмет");
      }
      else if((this.tradeLetter_rbtn.toggled || this.eTradeLetter_rbtn.toggled) && this.afro_txt.text == "" && this.gold_txt.text == "")
      {
         _loc4_ = lol.core.SceneShifter.openNewWindow("query");
         _loc2_ = _loc4_.content;
         _loc2_.label = "Вы не указали желаемую цену. Продолжить?";
         _loc2_.addEventListener("click",this,this._sendLetter);
      }
      else if(this.attachItems_mc.itemList.length > 0 && (this.master.currentLocation.locInfo.battle || this.master.currentState == lol.core.Master.GLOBAL_STATE))
      {
         this.openAlertWindow("Только в мирных локациях можно отправлять посылки");
      }
      else
      {
         this.__sendLetter();
      }
   }
   function _sendLetter(obj)
   {
      obj.target.removeEventListener("click",this,this._sendLetter);
      lol.core.SceneShifter.closeWindow("query");
      var _loc2_ = obj.success;
      if(_loc2_)
      {
         this.__sendLetter();
      }
      else
      {
         Selection.setFocus(this.afro_txt);
      }
   }
   function __sendLetter()
   {
      var _loc8_ = this.name_txt.text;
      var _loc4_ = this.subj_txt.text;
      _loc4_ = _loc4_.substr(0,120);
      var _loc6_ = this.body_txt.text;
      var _loc2_;
      var _loc3_ = this.attachItems_mc.itemList;
      var _loc7_ = this.afro_txt.text == "" ? 0 : Number(this.afro_txt.text);
      var _loc5_ = this.gold_txt.text == "" ? 0 : Number(this.gold_txt.text) * 100;
      _loc5_ = Math.round(_loc5_);
      if(this.letter_rbtn.toggled)
      {
         _loc2_ = 0;
      }
      else if(this.eLetter_rbtn.toggled)
      {
         _loc2_ = 1;
      }
      else if(this.clanLetter_rbtn.toggled)
      {
         _loc2_ = 2;
         _loc3_ = null;
      }
      else if(this.eClanLetter_rbtn.toggled)
      {
         _loc2_ = 3;
         _loc3_ = null;
      }
      else if(this.tradeLetter_rbtn.toggled)
      {
         _loc2_ = 4;
      }
      else if(this.eTradeLetter_rbtn.toggled)
      {
         _loc2_ = 5;
      }
      else if(this.delivery_rbtn.toggled)
      {
         _loc2_ = 6;
      }
      else if(this.eDelivery_rbtn.toggled)
      {
         _loc2_ = 7;
      }
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.SEND_LETTER_SUCCESS,this,this.sendLetterAck);
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.SEND_LETTER_USER_NOT_FOUND,this,this.sendLetterAck);
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.SEND_LETTER_OBJECT_CAN_NOT_BE_ATTACHED,this,this.sendLetterAck);
      this.mailInspector.sendLetter(_loc8_,_loc4_,_loc2_,_loc6_,_loc3_,_loc7_,_loc5_);
   }
   function sendLetterAck(obj)
   {
      var _loc2_;
      if(obj.type == lol.core.mail.MailEvent.SEND_LETTER_SUCCESS)
      {
         this.openAlertWindow("Письмо отправлено");
         this.selectPage({target:this.inbox_btn});
         this.gotoAndStop(this.inbox_frame);
         this.doLater("initInboxPage");
      }
      else if(obj.type == lol.core.mail.MailEvent.SEND_LETTER_USER_NOT_FOUND)
      {
         _loc2_ = this.openAlertWindow("Игрок &lt;" + this.name_txt.text + "&gt; не найден.<BR>Проверьте правильность ввода имени");
         _loc2_.addEventListener("click",this,this.checkName);
      }
      else if(obj.type == lol.core.mail.MailEvent.SEND_LETTER_OBJECT_CAN_NOT_BE_ATTACHED)
      {
         this.openAlertWindow("Некоторые объекты не могут быть прикреплены к письму, поэтому письмо не будет отправлено");
      }
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.SEND_LETTER_SUCCESS,this,this.sendLetterAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.SEND_LETTER_USER_NOT_FOUND,this,this.sendLetterAck);
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.SEND_LETTER_OBJECT_CAN_NOT_BE_ATTACHED,this,this.sendLetterAck);
   }
   function checkName(obj)
   {
      obj.target.removeEventListener("click",this,this.checkName);
      Selection.setFocus(this.name_txt);
      Selection.setSelection(0,this.name_txt.text.length);
   }
   function checkSubj(obj)
   {
      obj.target.removeEventListener("click",this,this.checkName);
      Selection.setFocus(this.subj_txt);
      Selection.setSelection(0,this.subj_txt.text.length);
   }
   function numberOfItems()
   {
      var _loc3_ = "Прикреплен";
      if(this.curType_btn == this.tradeLetter_rbtn || this.curType_btn == this.eTradeLetter_rbtn)
      {
         _loc3_ = "Предложен";
      }
      var _loc2_ = this.attachItems_mc.itemList.length;
      var _loc4_;
      if(_loc2_ >= 2 && _loc2_ <= 4)
      {
         _loc4_ = _loc3_ + "о " + _loc2_ + " объекта";
      }
      if(_loc2_ == 1)
      {
         _loc4_ = _loc3_ + " " + _loc2_ + " объект";
      }
      if(_loc2_ == 0 || _loc2_ == 5)
      {
         _loc4_ = _loc3_ + "о " + _loc2_ + " объектов";
      }
      this.attachItems_txt.htmlText = "<b><i>" + _loc4_ + "</i></b>";
      this.updateLetterPrise();
   }
   function changeMaskBag(obj)
   {
      this.sortMask = obj.sortMask;
      this.filterPan.sortMaskToggled(this.sortMask);
   }
   function changeMask(obj)
   {
      this.sortMask = obj.sortMask;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_MASK_MAIL,this.sortMask);
      this.bag_mc.sortMask = this.sortMask;
      this.bag_mc.resort();
   }
   function changeView(obj)
   {
      if(!this.bag_mc.attaching)
      {
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.TYPE_OF_LIST_MAIL,obj.typeOfList);
         this.typeOfList = obj.typeOfList;
         this.bag_mc.linkageItem = obj.linkageItem;
         this.bag_mc.typeOfList = obj.typeOfList;
         this.attachItems_mc.linkageItem = obj.linkageItem;
         this.attachItems_mc.typeOfList = obj.typeOfList;
         this.clearBag(this.equipment.bag);
         this.doLater("initBag",[this.equipment.bag]);
         this.bag_mc.firstAttaching = true;
      }
      else
      {
         this.listIconPan._typeOfList();
      }
   }
   function startDragNDrop(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      this.ddFlag = true;
      var _loc2_ = obj.item_arr;
      var _loc4_ = obj.target;
      for(var _loc3_ in _loc2_)
      {
         _loc2_[_loc3_].blockItem();
      }
      if(_loc2_.length > 1)
      {
         this.createDragItemMc(_loc2_[0].item,true);
      }
      else
      {
         this.createDragItemMc(_loc2_[0].item);
      }
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_[0].item,_loc4_,_loc2_[0],_loc2_);
   }
   function createDragItemMc(_item, group)
   {
      if(this.typeOfList == "icon")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("itemCont","dd",10));
         this.dragItemMc.attachIconEnabled = true;
      }
      else if(this.typeOfList == "list")
      {
         this.dragItemMc = lol.gpui.ItemContainer(this.attachMovie("listItemCont","dd",10));
         this.dragItemMc.attachIconEnabled = false;
      }
      this.dragItemMc.priceEnabled = this.priceEnabled;
      this.dragItemMc.showItemRepairMod = this.showItemRepairMod;
      this.dragItemMc.cost_mod = this.cost_mod;
      this.dragItemMc.groupItem = group;
      this.dragItemMc.item = _item;
      this.dragItemMc.attachIcon(_item);
      this.draggingItem();
      this.onMouseMove = this.draggingItem;
   }
   function draggingItem()
   {
      this.dragItemMc._x = Math.round(this._xmouse - this.dragItemMc._width / 2);
      this.dragItemMc._y = Math.round(this._ymouse - this.dragItemMc._height / 2);
   }
   function doubleClick(obj)
   {
      if(!this.ddOperation_arr)
      {
         this.ddOperation_arr = new Array();
      }
      var _loc2_ = obj.item_mc;
      _loc2_.blockItem();
      this.currDDOperation = new lol.gpui.DDOperation();
      this.currDDOperation.setFrom(_loc2_.item,obj.target,_loc2_);
      var _loc3_;
      if(obj.target == this.bag_mc)
      {
         this.currDDOperation.setTo(0,this.attachItems_mc);
         if(lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable)
         {
            _loc3_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
            _loc3_.addEventListener("exchange",this,this.exchangeDropAck);
            _loc3_.addEventListener("close",this,this.exchangeCancel);
         }
         else
         {
            this.sendTransferToServer();
         }
      }
      else
      {
         this.currDDOperation.setTo(0,this.bag_mc);
         this.sendTransferToServer();
      }
   }
   function mouseUpOnItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.item_mc;
         this.currDDOperation.setTo(_loc2_.item,obj.target,_loc2_);
      }
   }
   function dropItem(obj)
   {
      var _loc2_;
      if(this.ddFlag)
      {
         _loc2_ = obj.target;
         this.currDDOperation.setTo(0,_loc2_);
      }
   }
   function onMouseUp()
   {
      var _loc2_;
      if(this.ddFlag)
      {
         this.ddFlag = false;
         this.dragItemMc.kill();
         this.dragItemMc.removeMovieClip();
         if(this.currDDOperation.toSlot)
         {
            if(!this.currDDOperation.group && lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize > 1 && this.currDDOperation.fromItem instanceof lol.core.objects.Heapable && this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.attachItems_mc)
            {
               _loc2_ = this.createExchangePan(this.currDDOperation.fromItem,"Сколько штук положить?");
               _loc2_.addEventListener("exchange",this,this.exchangeDropAck);
               _loc2_.addEventListener("close",this,this.exchangeCancel);
            }
            else
            {
               this.sendTransferToServer();
            }
         }
         else
         {
            this.currDDOperation.failedOperation();
            delete this.currDDOperation;
         }
      }
      delete this.onMouseMove;
   }
   function sendTransferToServer()
   {
      var _loc3_ = this.currDDOperation.fromItemMc_arr;
      var _loc5_;
      var _loc4_;
      var _loc2_;
      if(_loc3_)
      {
         if(this.currDDOperation.fromSlot != this.currDDOperation.toSlot)
         {
            _loc4_ = 0;
            for(var _loc6_ in _loc3_)
            {
               _loc2_ = new lol.gpui.DDOperation();
               _loc2_.setFrom(_loc3_[_loc6_].item,this.currDDOperation.fromSlot,_loc3_[_loc6_]);
               _loc2_.setTo(this.currDDOperation.toItem,this.currDDOperation.toSlot,this.currDDOperation.toItemMc);
               if(this.checkSellItem(_loc2_.fromItem) && this.currDDOperation.toSlot == this.attachItems_mc && this.currDDOperation.fromSlot == this.bag_mc)
               {
                  _loc5_ = this.checkSellItem(_loc2_.fromItem);
                  _loc2_.failedOperation();
               }
               else if(this.currDDOperation.toSlot == this.attachItems_mc && this.currDDOperation.fromSlot == this.bag_mc && (this.attachItems_mc.itemList.length > 4 || _loc4_ > 4))
               {
                  this.moveItemError();
                  this.openAlertWindow("Вы не можете прикрепить к письму больше 5 предметов");
               }
               else
               {
                  _loc2_.toSlot.addItem(_loc2_.fromItem);
                  _loc2_.fromSlot.removeItem(_loc2_.fromItem);
                  _loc2_.successOperation();
                  _loc4_ = _loc4_ + 1;
               }
            }
         }
         else if(this.currDDOperation.fromSlot == this.bag_mc && this.currDDOperation.toSlot == this.bag_mc)
         {
            this.ddOperation_arr.push(this.currDDOperation);
            this.equipment.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
         }
         else
         {
            this.moveItemError();
         }
      }
      else if(this.checkSellItem(this.currDDOperation.fromItem) && this.currDDOperation.toSlot == this.attachItems_mc && this.currDDOperation.fromSlot == this.bag_mc)
      {
         _loc5_ = this.checkSellItem(this.currDDOperation.fromItem);
         this.currDDOperation.failedOperation();
      }
      else if(this.currDDOperation.toSlot != this.currDDOperation.fromSlot)
      {
         if(this.currDDOperation.toSlot == this.attachItems_mc && this.currDDOperation.fromSlot == this.bag_mc && this.attachItems_mc.itemList.length > 4)
         {
            this.moveItemError();
            this.openAlertWindow("Вы не можете прикрепить к письму больше 5 предметов");
         }
         else
         {
            this.currDDOperation.toSlot.addItem(this.currDDOperation.fromItem);
            this.currDDOperation.fromSlot.removeItem(this.currDDOperation.fromItem);
            this.currDDOperation.successOperation();
         }
      }
      else if(this.currDDOperation.toSlot == this.bag_mc && this.currDDOperation.fromSlot == this.bag_mc)
      {
         this.ddOperation_arr.push(this.currDDOperation);
         this.equipment.transferItem(this.currDDOperation.fromItem,this.currDDOperation.fromSlot.id,this.currDDOperation.toSlot.id,this.currDDOperation.toItem);
      }
      else
      {
         this.moveItemError();
      }
      var _loc7_;
      if(_loc5_)
      {
         _loc7_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc7_.content.label = _loc5_;
      }
      delete this.currDDOperation;
   }
   function sendHeapToServer()
   {
      this.ddOperation_arr.push(this.currDDOperation);
      this.master.gamer.equipment.separateHeap(lol.core.objects.Heapable(this.currDDOperation.fromItem),this.currDDOperation.heapNum);
      delete this.currDDOperation;
   }
   function checkSellItem(_item)
   {
      var _loc2_;
      var _loc3_ = _item.getProp("__break");
      var _loc1_ = _item.getProp("exchang");
      if(!_loc1_)
      {
         _loc2_ = "Вы не можете передать некоторые предметы";
      }
      return _loc2_;
   }
   function createExchangePan(_item, title_str)
   {
      var _loc3_ = lol.core.objects.Heapable(_item);
      var _loc4_ = lol.core.SceneShifter.openNewWindow("exchange");
      var _loc2_ = lol.gpui.ExchangePan(_loc4_.content);
      _loc2_.label = title_str;
      _loc2_.mainSize = this.exchangeMainSize;
      _loc2_.cost_num = this.exchangePanCost_num;
      _loc2_.cost_mod = this.exchangePan_cost_mod;
      _loc2_.showCostInGold = this.exchangePan_showCostInGold;
      _loc2_.maxValue = _loc3_.heapSize;
      this.dropEnabled = false;
      return _loc2_;
   }
   function exchangeDropAck(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeDropAck);
      lol.core.SceneShifter.closeWindow("exchange");
      if(lol.core.objects.Heapable(this.currDDOperation.fromItem).heapSize == obj.right)
      {
         this.sendTransferToServer();
      }
      else
      {
         this.currDDOperation.heapNum = obj.left;
         this.sendHeapToServer();
      }
   }
   function exchangeCancel(obj)
   {
      obj.target.removeEventListener("close",this,this.exchangeCancel);
      obj.target.removeEventListener("exchange",this,this.exchangeDropAck);
      lol.core.SceneShifter.closeWindow("exchange");
      this.currDDOperation.failedOperation();
      delete this.currDDOperation;
   }
   function separateAck(obj)
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      if(obj.res == 0)
      {
         _loc2_.successOperation();
         if(_loc2_.fromSlot == this.bag_mc && _loc2_.toSlot == this.attachItems_mc)
         {
            _loc2_.fromItemMc.blockItem();
            this.currDDOperation = new lol.gpui.DDOperation();
            this.currDDOperation.setFrom(_loc2_.fromItem,_loc2_.fromSlot,_loc2_.fromItemMc);
            this.currDDOperation.setTo(0,this.attachItems_mc);
            this.sendTransferToServer();
         }
      }
      else
      {
         _loc2_.failedOperation();
      }
   }
   function moveItemSuccess()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.successOperation();
   }
   function moveItemError()
   {
      var _loc2_ = lol.gpui.DDOperation(this.ddOperation_arr.shift());
      _loc2_.failedOperation();
      this.currDDOperation.fromItemMc.unblockItem();
      this.currDDOperation.failedOperation();
      delete this.currDDOperation;
   }
   function checkDropItem(item)
   {
      var _loc6_ = item.getProp("__break");
      var _loc7_ = item.getProp("max_break_cur");
      var _loc4_ = item.getProp("max_break_abs");
      var _loc9_ = item.getProp("ammo_count");
      var _loc8_ = item.getProp("clip_size");
      var _loc5_ = item.getProp("max_count");
      var _loc3_ = item.getProp("size");
      if(item instanceof lol.core.objects.Heapable && item.rootID != lol.core.objects.Item.AMMO)
      {
         if(_loc3_ == 1)
         {
            return true;
         }
         this.doLater("getOneItemFromHeap",[item,_loc3_ - 1]);
         return false;
      }
      if(item.rootID == lol.core.objects.Item.TRASH || item.rootID == lol.core.objects.Item.HEAL_ITEM)
      {
         return true;
      }
      if(item.rootID == lol.core.objects.Item.COLD_ARM || item.rootID == lol.core.objects.Item.WEAR || item.rootID == lol.core.objects.Item.FIRE_ARM || item.rootID == lol.core.objects.Item.WEAR)
      {
         if(_loc7_ == _loc4_ && _loc6_ == _loc4_)
         {
            return true;
         }
         this.openAlertWindow("Вы не можете предлагать другому игроку купить поврежденный предмет");
         return false;
      }
      if(item.rootID == lol.core.objects.Item.AMMO)
      {
         if(_loc3_ == _loc5_)
         {
            return true;
         }
         this.openAlertWindow("Количество предлагаемых патронов должно быть максимальным и равным " + _loc5_);
         return false;
      }
   }
   function getOneItemFromHeap(item, size)
   {
      this.heapSepItem = lol.core.objects.Heapable(item);
      this.sepItem = item;
      this.mailInspector.addEventListener(lol.core.mail.MailEvent.SEPARATE_ITEM,this,this.getOneItemFromHeapAck);
      this.mailInspector.separateHeap(this.heapSepItem,size);
   }
   function getOneItemFromHeapAck(_mailEvent)
   {
      this.mailInspector.removeEventListener(lol.core.mail.MailEvent.SEPARATE_ITEM,this,this.getOneItemFromHeapAck);
      if(_mailEvent.param == 0)
      {
         this.removeItem({slot:this.bag_mc,item:this.sepItem});
         this.addItem({slot:this.attachItems_mc,item:this.sepItem});
      }
   }
   function onDoubleClick()
   {
      if(this.dropEnabled)
      {
         super.onDoubleClick();
      }
   }
   function drop()
   {
      var _loc2_;
      if(this.dragON)
      {
         if(!this.dragNdrop.what[0].item.getProp("exchang"))
         {
            if(this.dragNdrop.from == this.bag_mc && this.dragNdrop.where == this.attachItems_mc)
            {
               this.openAlertWindow("Данный предмет нельзя передавать");
            }
            this.dragNdrop.where = null;
            this.__drop();
         }
         else if(!this.master.currentLocation.locInfo.battle)
         {
            if(this.checkSeparate())
            {
               this.exchangePanTitle = "Какое количество отправить?";
               _loc2_ = this.proposeSeparate(this.dragNdrop.what[0].item);
               _loc2_.addEventListener("exchange",this,this.dragSeparate);
               _loc2_.addEventListener("close",this,this.dragSeparateCancel);
               if(!_loc2_)
               {
                  this.__drop();
               }
            }
            else
            {
               this.__drop();
            }
         }
         else
         {
            if(this.dragNdrop.from == this.bag_mc && this.dragNdrop.where == this.attachItems_mc)
            {
               this.openAlertWindow("Только в мирных локациях можно посылать посылки");
            }
            this.dragNdrop.where = null;
            this.__drop();
         }
      }
   }
   function __drop()
   {
      this.dragON = false;
      var _loc2_ = this.dragNdrop.where.id;
      var _loc3_ = this.dragNdrop.from.id;
      if(_loc2_ == undefined && _loc3_ == "bag")
      {
         this.addItemInBag(this.dragNdrop.from);
      }
      else if(_loc2_ == undefined && _loc3_ == "mail")
      {
         this.addItemInBag(this.dragNdrop.from);
      }
      else if(_loc2_ == "mail")
      {
         if(this.attachItems_mc.itemList.length < 5)
         {
            this.addItemInBag(this.dragNdrop.where);
         }
         else
         {
            this.openAlertWindow("Вы не можете прикрепить к письму больше 5 предметов");
            this.addItemInBag(this.dragNdrop.from);
         }
      }
      else if(_loc2_ == "bag")
      {
         if(this.dragNdrop.hitted && _loc3_ == "bag")
         {
            this.master.gamer.equipment.joinHeap(lol.core.objects.Heapable(this.dragNdrop.what[0].item),lol.core.objects.Heapable(this.dragNdrop.hitted));
            this.master.gamer.equipment.removeItem(this.equipment.bag,this.dragNdrop.what[0].item);
         }
         else
         {
            this.addItemInBag(this.dragNdrop.where);
         }
      }
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      delete this.dragNdrop;
      delete this.dragCont.onMouseMove;
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
   }
   function addItemInBag(slot, _item)
   {
      var _loc2_ = !_item ? this.dragNdrop.what[0].item : _item;
      if(slot.id == "mail" && (this.tradeLetter_rbtn.toggled || this.eTradeLetter_rbtn.toggled))
      {
         this.addItem({slot:slot,item:_loc2_});
      }
      else
      {
         this.addItem({slot:slot,item:_loc2_});
      }
   }
   function checkSeparate()
   {
      if(lol.core.objects.Heapable(this.dragNdrop.what[0].item).heapSize > 1 && this.dragNdrop.what.length == 1 && this.dragNdrop.what[0].item instanceof lol.core.objects.Heapable && this.dragNdrop.from.id != this.dragNdrop.where.id && this.dragNdrop.where.id == "mail")
      {
         delete this.dragCont.onMouseMove;
         this.dragCont.kill();
         this.dragCont.removeMovieClip();
         return true;
      }
      return false;
   }
   function dragSeparate(obj)
   {
      obj.target.removeEventListener("close",this,this.dragSeparateCancel);
      obj.target.removeEventListener("exchange",this,this.dragSeparate);
      lol.core.SceneShifter.closeWindow("exchange");
      this.master.gamer.equipment.addEventListener("separate",this,this.dragSeparateAck);
      this.master.gamer.equipment.separateHeap(this.heapSepItem,obj.left);
   }
   function dragSeparateAck(obj)
   {
      this.attachItems_mc.addItem(this.heapSepItem);
      obj.target.removeEventListener("separate",this,this.dragSeparateAck);
      this.dropEnabled = true;
      delete this.dragCont.onMouseMove;
      this.dragCont.kill();
      this.dragCont.removeMovieClip();
      this.dragON = false;
      this.dragCont = null;
      this.heapSepItem = null;
      this.dropEnabled = true;
      delete this.dragNdrop;
   }
   function dragSeparateCancel(obj)
   {
      this.bag_mc.addItem(this.heapSepItem);
      super.dragSeparateCancel(obj);
   }
   function updateLetterPrise()
   {
      var _loc6_ = 0;
      var _loc7_ = 0;
      var _loc4_ = this.mailInspector.getMailParam();
      if(this.letter_rbtn.toggled)
      {
         _loc6_ = _loc4_.tradeLetter_usual[0];
      }
      else if(this.clanLetter_rbtn.toggled)
      {
         _loc6_ = _loc4_.clanLetter_usual[0];
      }
      else if(this.tradeLetter_rbtn.toggled)
      {
         _loc6_ = _loc4_.tradeLetter_usual[0];
      }
      else if(this.delivery_rbtn.toggled)
      {
         _loc6_ = _loc4_.delivery_usual[0];
      }
      if(this.eLetter_rbtn.toggled)
      {
         _loc7_ = _loc4_.tradeLetter_express[0];
      }
      else if(this.eClanLetter_rbtn.toggled)
      {
         _loc7_ = _loc4_.clanLetter_express[0];
      }
      else if(this.eTradeLetter_rbtn.toggled)
      {
         _loc7_ = _loc4_.tradeLetter_express[0];
      }
      else if(this.eDelivery_rbtn.toggled)
      {
         _loc7_ = _loc4_.delivery_express[0];
      }
      var _loc5_ = 0;
      var _loc3_;
      var _loc2_;
      if(!this.clanLetter_rbtn.toggled && !this.eClanLetter_rbtn.toggled)
      {
         _loc3_ = this.attachItems_mc.itemList;
         for(var _loc9_ in _loc3_)
         {
            _loc2_ = _loc3_[_loc9_].item;
            _loc5_ += _loc2_.getProp("weight");
         }
      }
      _loc5_ /= 1000;
      var _loc8_;
      if(_loc6_ != 0)
      {
         _loc8_ = Math.floor(_loc5_ * _loc4_.itemKg_usual[0]);
         _loc8_ = !_loc8_ ? 0 : _loc8_;
         this.prise_txt.htmlText = "<b>" + String(_loc6_ + _loc8_) + "</b>";
         this.prise_mc.gotoAndStop(1);
      }
      else
      {
         _loc8_ = Math.floor(_loc5_ * _loc4_.itemKg_express[0] * 100) / 100;
         _loc8_ = !_loc8_ ? 0 : _loc8_;
         this.prise_txt.htmlText = "<b>" + String(_loc7_ + _loc8_) + "</b>";
         this.prise_mc.gotoAndStop(2);
      }
   }
   function checkSmth()
   {
      if(this.clanLetter_rbtn.toggled || this.eClanLetter_rbtn.toggled)
      {
         this.nameEnabled_mc._visible = true;
         this.name_txt._visible = false;
         this.name_txt.text = "";
      }
      else
      {
         this.nameEnabled_mc._visible = false;
         this.name_txt._visible = true;
      }
   }
   function openAlertWindow(str)
   {
      var _loc1_ = lol.core.SceneShifter.openNewWindow("alert");
      _loc1_.content.label = str;
      return _loc1_.content;
   }
   function getNextLowestPoint()
   {
      return this.mailPan.cont_mc._height;
   }
   function parseDate(date_str, timeFlag)
   {
      var _loc6_ = date_str.substring(0,4);
      var _loc5_ = date_str.substring(5,7);
      var _loc4_ = date_str.substring(8,10);
      var _loc3_ = date_str.substring(11,19);
      var _loc1_ = _loc4_ + "." + _loc5_ + "." + _loc6_;
      if(timeFlag)
      {
         _loc1_ += " " + _loc3_;
      }
      else
      {
         _loc1_ += "<BR>" + _loc3_;
      }
      return _loc1_;
   }
   function getUnreadLettersNumber(arr)
   {
      var _loc4_ = 0;
      var _loc1_ = 0;
      var _loc2_;
      while(_loc1_ < arr.length)
      {
         _loc2_ = arr[_loc1_];
         if(!_loc2_.read)
         {
            _loc4_ = _loc4_ + 1;
         }
         _loc1_ = _loc1_ + 1;
      }
      return _loc4_;
   }
}
