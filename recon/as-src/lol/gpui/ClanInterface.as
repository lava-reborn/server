class lol.gpui.ClanInterface extends lol.gpui.GPUIObject
{
   var acceptNewBaseMembers;
   var acceptNewMiddleMembers;
   var addItemsToClanStorage;
   var addMember_btn;
   var afro;
   var afro_txt;
   var allRights;
   var askStanding_btn;
   var back_btn;
   var cancel_btn;
   var changeRights_btn;
   var changeStandings;
   var chatAndViewStandings;
   var clanAfro;
   var clanGold;
   var clanInspector;
   var clanName_btn;
   var clanPan;
   var cost_txt;
   var createClan_btn;
   var curClanMemberInfo;
   var curStanding;
   var currItem;
   var currMemberList;
   var currSort;
   var currStandingList;
   var descMember_btn;
   var description_txt;
   var diplomatia_btn;
   var downStanding_btn;
   var down_txt;
   var fireBaseMembers;
   var getAfroFromClanBank;
   var getGoldFromClanBank;
   var getItemsFromClanStorage;
   var gold;
   var gold_txt;
   var gotoAndStop;
   var infoPutAfro_txt;
   var infoPutGold_txt;
   var infoTakeAfro_txt;
   var infoTakeGold_txt;
   var info_txt;
   var lastGame_btn;
   var leaveClan_btn;
   var master;
   var memberList;
   var moneyPan_mc;
   var money_btn;
   var myRights_btn;
   var nameMember_btn;
   var nick_txt;
   var online_checkBox;
   var operationInfo;
   var ourStanding_btn;
   var parseMemberList;
   var prevAlpha;
   var putAfro_btn;
   var putAfro_txt;
   var putGold_btn;
   var putGold_txt;
   var removeMember_btn;
   var standingList;
   var takeAfro_btn;
   var takeAfro_txt;
   var takeGold_btn;
   var takeGold_txt;
   var tempClanName;
   var title_txt;
   var underNick_mc;
   var underTakeAfro;
   var underTakeGold;
   var upStanding_btn;
   var up_txt;
   var createClan_frame = 1;
   var membersList_frame = 2;
   var addMember_frame = 3;
   var changeRights_frame = 4;
   var money_frame = 5;
   var myRights_frame = 6;
   var standing_frame = 7;
   var goldOperation_bool = false;
   var sortBy = "name";
   var operationSuccess = false;
   function ClanInterface()
   {
      super();
      this.clanInspector = lol.core.clans.ClanInspector.getInstance();
      this.master = lol.core.Master.getInstance();
      this.memberList = this.clanInspector.getClanMemberList();
      var _loc3_ = this.master.gamer.clanMemberInfo.clanReg;
      if(_loc3_ != 0 && _loc3_ != 16777215)
      {
         this.gotoAndStop(this.membersList_frame);
         this.doLater("initClanMembersPage");
      }
      else
      {
         this.doLater("initCreatePage");
      }
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,lol.core.SceneShifter,lol.core.SceneShifter._ref.kickedFromClan);
      lol.core.SceneShifter.hotKeyManager.addFilter("clan");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function initCreatePage()
   {
      this.createClan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.createClan);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_NO_MONEY,this,this.noMoney);
      this.title_txt.tabIndex = 1;
      this.description_txt.tabIndex = 2;
      this.title_txt.text = "";
      this.description_txt.text = "";
      this.title_txt.maxChars = 40;
      this.description_txt.maxChars = 127;
      this.title_txt.onChanged = mx.utils.Delegate.create(this,this.checkText);
      this.description_txt.onChanged = mx.utils.Delegate.create(this,this.checkText);
      this.title_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.title_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.description_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.description_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.checkText();
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_COST,this,this.showCostClanCreation);
      var _loc2_ = this.clanInspector.getClanCreationCost();
      if(_loc2_ != undefined)
      {
         this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_COST,this,this.showCostClanCreation);
         this.cost_txt.text = String(Number(_loc2_) / 100);
      }
   }
   function showCostClanCreation(obj)
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_COST,this,this.showCostClanCreation);
      this.cost_txt.text = String(Number(obj.body) / 100);
   }
   function noMoney()
   {
      var _loc1_ = lol.core.SceneShifter.openNewWindow("alert").content;
      _loc1_.alert_txt.text = "Недостаточно средств";
   }
   function killCreatePage()
   {
      this.createClan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.createClan);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_ERROR_NO_MONEY,this,this.noMoney);
   }
   function blockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = false;
   }
   function unblockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function checkText()
   {
      if(this.title_txt.text != "" && this.description_txt.text != "")
      {
         this.createClan_btn.enabled = true;
      }
      else
      {
         this.createClan_btn.enabled = false;
      }
   }
   function createClan()
   {
      if(this.title_txt.text != "" && this.description_txt.text != "")
      {
         this.clanInspector.createClan(this.title_txt.text,this.description_txt.text);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_SUCCES,this,this.createClanOk);
      }
   }
   function createClanOk(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_CREATION_SUCCES,this,this.createClanOk);
      this.gotoAndStop(this.membersList_frame);
      this.killCreatePage();
      var _loc2_ = new lol.utils.Timeout(this,this.initClanMembersPage,500);
      lol.core.SceneShifter.chat.initClanChannel();
   }
   function initClanMembersPage()
   {
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.NEW_CLAN_MEMBER_ADDED,this,this.buildClanList);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.updateMemberList);
      this.nameMember_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.nameMember_btn.data = "name";
      this.descMember_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.descMember_btn.data = "description";
      this.lastGame_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.lastGame_btn.data = "date";
      this.online_checkBox.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.ONLY_ONLINE_MEMBERS);
      this.online_checkBox.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.onlineMembers);
      this.addMember_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToAddMemberPage);
      this.changeRights_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToChangeRightsPage);
      this.removeMember_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeMember);
      this.leaveClan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.leaveClan);
      this.money_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.money);
      this.myRights_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showMyRights);
      this.diplomatia_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showStanding);
      var _loc5_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc4_ = _loc5_.rights;
      this.addMember_btn.enabled = _loc4_.allowAcceptNewBaseMembers;
      this.removeMember_btn.enabled = false;
      this.changeRights_btn.enabled = false;
      this.nameMember_btn._alpha = 0;
      this.descMember_btn._alpha = 0;
      this.lastGame_btn._alpha = 0;
      var _loc3_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_BY);
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_REVERSE);
      if(_loc3_ == "name")
      {
         this.nameMember_btn.toggled = _loc2_;
         this.currSort = this.nameMember_btn;
         this.nameMember_btn._alpha = 100;
      }
      else if(_loc3_ == "description")
      {
         this.descMember_btn.toggled = _loc2_;
         this.currSort = this.descMember_btn;
         this.descMember_btn._alpha = 100;
      }
      else if(_loc3_ == "date")
      {
         this.lastGame_btn.toggled = _loc2_;
         this.currSort = this.lastGame_btn;
         this.lastGame_btn._alpha = 100;
      }
      this.buildClanList(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_BY),lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_REVERSE));
   }
   function killClanMembersPage()
   {
      this.nameMember_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.descMember_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.lastGame_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortBy_func);
      this.online_checkBox.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.onlineMembers);
      this.addMember_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToAddMemberPage);
      this.changeRights_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToChangeRightsPage);
      this.removeMember_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.removeMember);
      this.leaveClan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.leaveClan);
      this.money_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.money);
      this.myRights_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showMyRights);
   }
   function showMyRights()
   {
      var _loc2_ = lol.core.SceneShifter.locationScreen;
      if(_loc2_.canLeavelocation)
      {
         this.killClanMembersPage();
         this.gotoAndStop(this.myRights_frame);
         this.doLater("initMyRightsPage");
      }
      else
      {
         this.openAlertWindow("Ваш персонаж слишком занят");
      }
   }
   function showStanding()
   {
      var _loc2_ = lol.core.SceneShifter.locationScreen;
      if(_loc2_.canLeavelocation)
      {
         this.killClanMembersPage();
         this.gotoAndStop(this.standing_frame);
         this.doLater("initStandingPage");
      }
      else
      {
         this.openAlertWindow("Ваш персонаж слишком занят");
      }
   }
   function updateMemberList()
   {
      this.buildClanList();
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      this.addMember_btn.enabled = _loc2_.allowAcceptNewBaseMembers;
   }
   function buildClanList()
   {
      this.killClanList();
      this.memberList = this.clanInspector.getClanMemberList();
      this.currMemberList = new Array();
      this.clanPan.setSize(734,305);
      var _loc6_ = this.clanPan.fillContent();
      var _loc3_ = this.sortArray(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_BY),lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_REVERSE));
      var _loc5_ = new TextFormat();
      _loc5_.bold = true;
      var _loc7_ = 0;
      var _loc8_ = 0;
      var _loc2_ = 0;
      var _loc4_;
      var _loc9_;
      while(_loc2_ < _loc3_.length)
      {
         if(this.online_checkBox.toggled)
         {
            if(_loc3_[_loc2_].online != 0 || _loc3_[_loc2_].name == this.master.gamer.playerInfo.name)
            {
               _loc4_ = _loc6_.attachMovie("clanMemberItem","clanMemberItem" + _loc6_.getNextHighestDepth(),_loc6_.getNextHighestDepth());
               _loc4_._y = Math.round(this.getNextLowestPoint() + 2);
               _loc4_.clanMemberInfo = _loc3_[_loc2_].clanMemberInfo;
               _loc4_.description_txt.text = _loc3_[_loc2_].description;
               _loc9_ = this.master.getPlayer(_loc3_[_loc2_].online).attributes.level;
               _loc4_.name_txt.text = _loc3_[_loc2_].name;
               _loc4_.date_txt.text = _loc3_[_loc2_].parseDate;
               _loc4_.name_txt.setTextFormat(_loc5_);
               _loc4_.description_txt.setTextFormat(_loc5_);
               _loc4_.date_txt.setTextFormat(_loc5_);
               _loc4_.bg._alpha = (_loc7_ % 2 + 1) * 50;
               this.doLater("initBg",[_loc4_.bg]);
               this.currMemberList.push(_loc4_);
            }
         }
         else
         {
            _loc4_ = _loc6_.attachMovie("clanMemberItem","clanMemberItem" + _loc6_.getNextHighestDepth(),_loc6_.getNextHighestDepth());
            _loc4_._y = Math.round(this.getNextLowestPoint() + 2);
            _loc4_.clanMemberInfo = _loc3_[_loc2_].clanMemberInfo;
            _loc4_.name_txt.text = _loc3_[_loc2_].name;
            _loc4_.description_txt.text = _loc3_[_loc2_].description;
            _loc4_.date_txt.text = _loc3_[_loc2_].parseDate;
            if(_loc3_[_loc2_].online != 0)
            {
               _loc4_.name_txt.setTextFormat(_loc5_);
               _loc4_.description_txt.setTextFormat(_loc5_);
               _loc4_.date_txt.setTextFormat(_loc5_);
            }
            _loc4_.bg._alpha = (_loc8_ % 2 + 1) * 50;
            this.doLater("initBg",[_loc4_.bg]);
            this.currMemberList.push(_loc4_);
         }
         if(_loc3_[_loc2_].online != 0 || _loc3_[_loc2_].name == this.master.gamer.playerInfo.name)
         {
            _loc7_ = _loc7_ + 1;
         }
         _loc8_ = _loc8_ + 1;
         _loc2_ = _loc2_ + 1;
      }
      this.info_txt.html = true;
      this.info_txt.htmlText = "Всего в клане <b>" + this.memberList.length + "</b> человек" + this.selectionOfEnding(this.memberList.length) + ", из них <b>" + _loc7_ + "</b> человек" + this.selectionOfEnding(_loc7_) + " в игре";
      this.clanPan.chekSize();
   }
   function killClanList()
   {
      for(var _loc2_ in this.currMemberList)
      {
         this.currMemberList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectMember);
         this.currMemberList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.DOUBLE_CLICK,this,this.doubleClick);
      }
      this.currItem = null;
   }
   function initBg(mc)
   {
      mc.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectMember);
      mc.addEventListener(lol.gpui.controls.GPUIButton.DOUBLE_CLICK,this,this.doubleClick);
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
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      this.removeMember_btn.enabled = false;
      this.changeRights_btn.enabled = false;
      if(this.currItem.clanMemberInfo.name == this.master.gamer.playerInfo.name || this.currItem.clanMemberInfo.rights.allowAllOtherRights)
      {
         this.removeMember_btn.enabled = false;
         this.changeRights_btn.enabled = false;
      }
      else
      {
         if(_loc2_.allowFireBaseMembers && this.rankDetection(_loc2_) > this.rankDetection(this.currItem.clanMemberInfo.rights))
         {
            this.removeMember_btn.enabled = true;
         }
         if((_loc2_.allowAcceptNewMiddleMembers || _loc2_.allowAcceptNewBaseMembers) && this.rankDetection(_loc2_) > this.rankDetection(this.currItem.clanMemberInfo.rights))
         {
            this.changeRights_btn.enabled = true;
         }
      }
   }
   function doubleClick()
   {
      if(this.currItem)
      {
         this.goToChangeRightsPage();
      }
   }
   function sortArray(type, reverse)
   {
      this.parseMemberList = new Array();
      this.memberList = this.clanInspector.getClanMemberList();
      var _loc4_ = 0;
      var _loc3_;
      var _loc2_;
      while(_loc4_ < this.memberList.length)
      {
         _loc3_ = this.memberList[_loc4_];
         _loc2_ = new Object();
         _loc2_.clanMemberInfo = _loc3_;
         _loc2_.name = _loc3_.name;
         _loc2_.description = _loc3_.memberPost;
         _loc2_.date = _loc3_.date;
         _loc2_.online = _loc3_.online;
         _loc2_.parseDate = this.parseDate(_loc3_.date);
         this.parseMemberList.push(_loc2_);
         _loc4_ = _loc4_ + 1;
      }
      this.parseMemberList.sortOn(type);
      if(!reverse)
      {
         this.parseMemberList.reverse();
      }
      if(type == "date")
      {
         this.parseMemberList.reverse();
      }
      return this.parseMemberList;
   }
   function parseDate(data_str)
   {
      var _loc6_ = data_str.substring(0,4);
      var _loc5_ = data_str.substring(5,7);
      var _loc2_ = data_str.substring(8,10);
      var _loc3_ = data_str.substring(11,19);
      var _loc4_ = _loc2_ + "." + _loc5_ + "." + _loc6_ + " " + _loc3_;
      return _loc4_;
   }
   function goToAddMemberPage()
   {
      var _loc2_ = lol.core.SceneShifter.locationScreen;
      if(_loc2_.canLeavelocation)
      {
         this.killClanMembersPage();
         this.gotoAndStop(this.addMember_frame);
         this.doLater("initAddMemberPage");
      }
      else
      {
         this.openAlertWindow("Ваш персонаж слишком занят");
      }
   }
   function onlineMembers(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.ONLY_ONLINE_MEMBERS,obj.target.toggled);
      this.buildClanList();
   }
   function goToChangeRightsPage()
   {
      var _loc5_ = lol.core.SceneShifter.locationScreen;
      var _loc2_;
      var _loc3_;
      var _loc4_;
      if(_loc5_.canLeavelocation)
      {
         _loc2_ = this.currItem.clanMemberInfo;
         _loc3_ = this.master.gamer.clanMemberInfo.rights;
         _loc4_ = _loc2_.rights;
         if(_loc2_.name != this.master.gamer.playerInfo.name && (_loc3_.allowAcceptNewMiddleMembers || _loc3_.allowAcceptNewBaseMembers) && !_loc4_.allowAllOtherRights && this.rankDetection(_loc3_) > this.rankDetection(_loc4_))
         {
            this.killClanMembersPage();
            this.gotoAndStop(this.changeRights_frame);
            this.doLater("initChangeRightsPage",[_loc2_]);
         }
      }
      else
      {
         this.openAlertWindow("Ваш персонаж слишком занят");
      }
   }
   function money()
   {
      this.killClanMembersPage();
      this.gotoAndStop(this.money_frame);
      this.doLater("initMoneyPage");
   }
   function removeMember(obj)
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("query").content;
      _loc2_.addEventListener("click",this,this.removeClanPan);
      var _loc3_ = this.currItem.clanMemberInfo.name;
      _loc2_.alert_txt.text = "Удалить персонажа " + _loc3_ + " из клана?";
   }
   function removeClanPan(obj)
   {
      obj.target.removeEventListener("click",this,this.removeClanPan);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.KICK_MEMBER_SUCCES,this,this.removeClanAck);
         this.clanInspector.kickClanMember(this.currItem.clanMemberInfo);
      }
   }
   function removeClanAck(obj)
   {
      var _loc2_ = this.currItem.clanMemberInfo.name;
      this.openAlertWindow("Персонаж удален");
      obj.target.removeEventListener(lol.core.clans.ClanEvent.KICK_MEMBER_SUCCES,this,this.removeClanAck);
      this.buildClanList();
   }
   function leaveClan()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("query").content;
      _loc2_.addEventListener("click",this,this.leaveClanPan);
      _loc2_.alert_txt.text = "Выйти из клана?";
   }
   function leaveClanPan(obj)
   {
      obj.target.removeEventListener("click",this,this.leaveClanPan);
      lol.core.SceneShifter.closeWindow("query");
      if(obj.success)
      {
         lol.core.SceneShifter._ref.leaveClan = true;
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.leaveClanAck);
         this.clanInspector.leaveClan();
      }
   }
   function leaveClanAck(obj)
   {
      lol.core.SceneShifter._ref.currentScene.openClanInterface();
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.leaveClanAck);
      this.killClanMembersPage();
      lol.core.SceneShifter.chat.removeClanChannel();
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
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_BY,this.currSort.data);
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_CLAN_LIST_REVERSE,this.currSort.toggled);
      this.buildClanList();
   }
   function initAddMemberPage()
   {
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      this.enabledCheckBox(_loc2_);
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.addMember_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addMember);
      this.allRights.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectAllRights);
      this.nick_txt.tabIndex = 0;
      this.description_txt.tabIndex = 1;
      this.nick_txt.text = "";
      this.description_txt.text = "";
      Selection.setFocus("nick_txt");
      this.nick_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.nick_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.description_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.description_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.description_txt.maxChars = 20;
      this.nick_txt.onChanged = mx.utils.Delegate.create(this,this.nickOnChanged);
      this.addMember_btn.enabled = false;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_BAN_ERROR);
   }
   function killAddMemberPage()
   {
      this.cancel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.addMember_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addMember);
   }
   function nickOnChanged()
   {
      this.addMember_btn.enabled = this.nick_txt.text != "";
   }
   function selectAllRights(obj)
   {
      var _loc2_ = obj.target.toggled;
      this.chatAndViewStandings.toggled = _loc2_;
      this.acceptNewMiddleMembers.toggled = _loc2_;
      this.addItemsToClanStorage.toggled = _loc2_;
      this.changeStandings.toggled = _loc2_;
      this.chatAndViewStandings.toggled = _loc2_;
      this.fireBaseMembers.toggled = _loc2_;
      this.getAfroFromClanBank.toggled = _loc2_;
      this.getGoldFromClanBank.toggled = _loc2_;
      this.getItemsFromClanStorage.toggled = _loc2_;
      this.acceptNewBaseMembers.toggled = _loc2_;
      var _loc3_ = this.master.gamer.clanMemberInfo.rights;
      this.unselectionOutRightsCheckBox(_loc3_);
   }
   function cancel()
   {
      this.killAddMemberPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
   }
   function close()
   {
      lol.core.SceneShifter._sl.closeWinBtn_func();
   }
   function addMember()
   {
      var _loc4_ = false;
      var _loc2_ = 0;
      while(_loc2_ < this.memberList.length)
      {
         if(this.nick_txt.text == this.memberList[_loc2_].name)
         {
            _loc4_ = true;
            this.openAlertWindow("Персонаж уже состоит\rв вашем клане");
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc3_;
      if(this.nick_txt.text != "" && !_loc4_)
      {
         _loc3_ = new lol.core.clans.Rights();
         _loc3_.allowAcceptNewBaseMembers = this.acceptNewBaseMembers.toggled;
         _loc3_.allowAcceptNewMiddleMembers = this.acceptNewMiddleMembers.toggled;
         _loc3_.allowAddItemsToClanStorage = this.addItemsToClanStorage.toggled;
         _loc3_.allowChangeStandings = this.changeStandings.toggled;
         _loc3_.allowChatAndViewStandings = this.chatAndViewStandings.toggled;
         _loc3_.allowFireBaseMembers = this.fireBaseMembers.toggled;
         _loc3_.allowGetAfroFromClanBank = this.getAfroFromClanBank.toggled;
         _loc3_.allowGetGoldFromClanBank = this.getGoldFromClanBank.toggled;
         _loc3_.allowGetItemsFromClanStorage = this.getItemsFromClanStorage.toggled;
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_SUCCES,this,this.addMemberAck);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_FOUND_ERROR,this,this.notFoundError);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_ONLINE_ERROR,this,this.notOnlineError);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_PLAYER_IN_OTHER_CLAN_ERROR,this,this.inOtherClanError);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_STRING_TO_LONG_ERROR,this,this.tooLongError);
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_BAN_ERROR,this,this.banError);
         this.clanInspector.inviteToClan(this.nick_txt.text,_loc3_,this.description_txt.text);
      }
   }
   function addMemberAck(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_SUCCES,this,this.addMemberAck);
      this.killAddMemberPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
      this.openAlertWindow("Приглашение отправлено");
   }
   function notOnlineError(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_ONLINE_ERROR,this,this.notOnlineError);
      this.openAlertWindow("Персонажа с таким именем\rне существует");
   }
   function notFoundError(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_NOT_FOUND_ERROR,this,this.notFoundError);
      this.openAlertWindow("Персонаж находится в офлайне");
   }
   function inOtherClanError(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_PLAYER_IN_OTHER_CLAN_ERROR,this,this.inOtherClanError);
      this.openAlertWindow("Персонаж уже состоит\rв другом клане");
   }
   function tooLongError(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_STRING_TO_LONG_ERROR,this,this.tooLongError);
      this.openAlertWindow("Слишком длинное имя персонажа");
   }
   function banError(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CLAN_ADMIT_BAN_ERROR,this,this.banError);
      this.openAlertWindow("Вы забанены");
   }
   function initChangeRightsPage(_clanMemberInfo)
   {
      this.curClanMemberInfo = _clanMemberInfo;
      this.cancel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.changeRights_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.changeRights);
      this.title_txt.text = "Изменить права персонажу " + this.curClanMemberInfo.name;
      this.description_txt.text = this.curClanMemberInfo.memberPost;
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      this.setRightsCheckBox(this.curClanMemberInfo.rights);
      if((this.acceptNewBaseMembers.toggled || !this.acceptNewBaseMembers.enabled) && (this.acceptNewMiddleMembers.toggled || !this.acceptNewMiddleMembers.enabled) && (this.addItemsToClanStorage.toggled || !this.addItemsToClanStorage.enabled) && (this.changeStandings.toggled || !this.changeStandings.enabled) && (this.chatAndViewStandings.toggled || !this.chatAndViewStandings.enabled) && (this.fireBaseMembers.toggled || !this.fireBaseMembers.enabled) && (this.getAfroFromClanBank.toggled || !this.getAfroFromClanBank.enabled) && (this.getGoldFromClanBank.toggled || !this.getGoldFromClanBank.enabled) && (this.getItemsFromClanStorage.toggled || !this.getItemsFromClanStorage.enabled))
      {
         this.allRights.toggled = true;
      }
      this.enabledCheckBox(_loc2_);
      this.allRights.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectAllRights);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CHANGE_RIGHTS_FAILED_NOT_ENOUGH_RIGHTS,this,this.failedSubordination);
      this.description_txt.maxChars = 20;
      this.description_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.description_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
   }
   function killChangeRightsPage()
   {
      this.cancel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cancel);
      this.changeRights_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.changeRights);
      this.allRights.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectAllRights);
   }
   function failedSubordination()
   {
      this.openAlertWindow("Вам нельзя этого делать");
   }
   function changeRights()
   {
      var _loc2_ = new lol.core.clans.Rights();
      _loc2_.allowAcceptNewBaseMembers = this.acceptNewBaseMembers.toggled;
      _loc2_.allowAcceptNewMiddleMembers = this.acceptNewMiddleMembers.toggled;
      _loc2_.allowAddItemsToClanStorage = this.addItemsToClanStorage.toggled;
      _loc2_.allowChangeStandings = this.changeStandings.toggled;
      _loc2_.allowChatAndViewStandings = this.chatAndViewStandings.toggled;
      _loc2_.allowFireBaseMembers = this.fireBaseMembers.toggled;
      _loc2_.allowGetAfroFromClanBank = this.getAfroFromClanBank.toggled;
      _loc2_.allowGetGoldFromClanBank = this.getGoldFromClanBank.toggled;
      _loc2_.allowGetItemsFromClanStorage = this.getItemsFromClanStorage.toggled;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CHANGE_RIGHTS_SUCCES,this,this.changeRightsAck);
      this.clanInspector.changeRights(this.curClanMemberInfo,_loc2_,this.description_txt.text);
   }
   function changeRightsAck(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CHANGE_RIGHTS_SUCCES,this,this.changeRightsAck);
      this.killAddMemberPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
   }
   function initMyRightsPage()
   {
      this.back_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.myRightsBack);
      var _loc4_ = this.master.gamer.clanMemberInfo;
      var _loc2_ = _loc4_.rights;
      var _loc3_ = _loc4_.memberPost;
      this.description_txt.text = _loc3_ != undefined ? _loc3_ : "нет описания";
      this.chatAndViewStandings._enabled = false;
      this.addItemsToClanStorage._enabled = false;
      this.getItemsFromClanStorage._enabled = false;
      this.acceptNewBaseMembers._enabled = false;
      this.fireBaseMembers._enabled = false;
      this.acceptNewMiddleMembers._enabled = false;
      this.getAfroFromClanBank._enabled = false;
      this.getGoldFromClanBank._enabled = false;
      this.changeStandings._enabled = false;
      this.acceptNewBaseMembers.toggled = _loc2_._allowAcceptNewBaseMembers;
      this.acceptNewMiddleMembers.toggled = _loc2_.allowAcceptNewMiddleMembers;
      this.addItemsToClanStorage.toggled = _loc2_.allowAddItemsToClanStorage;
      this.changeStandings.toggled = _loc2_.allowChangeStandings;
      this.chatAndViewStandings.toggled = _loc2_.allowChatAndViewStandings;
      this.fireBaseMembers.toggled = _loc2_.allowFireBaseMembers;
      this.getAfroFromClanBank.toggled = _loc2_.allowGetAfroFromClanBank;
      this.getGoldFromClanBank.toggled = _loc2_.allowGetGoldFromClanBank;
      this.getItemsFromClanStorage.toggled = _loc2_.allowGetItemsFromClanStorage;
      if(!_loc2_.allowAllOtherRights)
      {
         this.underNick_mc._visible = false;
         this.description_txt.type = "dynamic";
         this.description_txt.selectable = false;
      }
      this.description_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.description_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.description_txt.maxChars = 20;
   }
   function killMyRightsPage()
   {
      this.back_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.myRightsBack);
   }
   function myRightsBack()
   {
      var _loc2_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc4_ = _loc2_.memberPost;
      var _loc3_ = _loc2_.rights;
      if(_loc3_.allowAllOtherRights && _loc4_ != this.description_txt.text)
      {
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CHANGE_RIGHTS_SUCCES,this,this.changeMyRightsAck);
         this.clanInspector.changeRights(_loc2_,_loc3_,this.description_txt.text);
      }
      else
      {
         this.killMyRightsPage();
         this.gotoAndStop(this.membersList_frame);
         this.doLater("initClanMembersPage");
      }
   }
   function changeMyRightsAck(obj)
   {
      obj.target.removeEventListener(lol.core.clans.ClanEvent.CHANGE_RIGHTS_SUCCES,this,this.changeMyRightsAck);
      this.killMyRightsPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
   }
   function initMoneyPage()
   {
      if(!this.goldOperation_bool)
      {
         this.moneyPan_mc.gotoAndStop(2);
      }
      this.gold_txt = this.moneyPan_mc.gold_txt;
      this.putGold_txt = this.moneyPan_mc.putGold_txt;
      this.infoPutGold_txt = this.moneyPan_mc.infoPutGold_txt;
      this.putGold_btn = this.moneyPan_mc.putGold_btn;
      this.takeGold_txt = this.moneyPan_mc.takeGold_txt;
      this.infoTakeGold_txt = this.moneyPan_mc.infoTakeGold_txt;
      this.takeGold_btn = this.moneyPan_mc.takeGold_btn;
      this.afro_txt = this.moneyPan_mc.afro_txt;
      this.putAfro_txt = this.moneyPan_mc.putAfro_txt;
      this.infoPutAfro_txt = this.moneyPan_mc.infoPutAfro_txt;
      this.putAfro_btn = this.moneyPan_mc.putAfro_btn;
      this.takeAfro_txt = this.moneyPan_mc.takeAfro_txt;
      this.infoTakeAfro_txt = this.moneyPan_mc.infoTakeAfro_txt;
      this.takeAfro_btn = this.moneyPan_mc.takeAfro_btn;
      Key.addListener(this);
      Selection.setFocus(this.putAfro_txt);
      this.infoPutAfro_txt.autoSize = true;
      this.infoPutGold_txt.autoSize = true;
      this.infoTakeAfro_txt.autoSize = true;
      this.infoTakeGold_txt.autoSize = true;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.updateMoneyPan);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.ADD_MONEY_TO_CLAN_AMMOUNT_SUCCES,this,this.refreshMoney);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.WITHDRAW_MONEY_FROM_CLAN_AMMOUNT_SUCCES,this,this.refreshMoney);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ACCOUNT_AFRO_AMMOUNT,this,this.refreshAfroAck);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_ACCOUNT_GOLD_AMMOUNT,this,this.refreshGoldAck);
      this.back_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.backFunc);
      this.putAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.putAfro);
      this.takeAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeAfro);
      this.putGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.putGold);
      this.takeGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeGold);
      this.takeAfro_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.takeAfro_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.takeGold_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.takeGold_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.putAfro_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.putAfro_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      this.putGold_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.putGold_txt.onKillFocus = mx.utils.Delegate.create(this,this.unblockHotKeys);
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      this.takeAfro_btn.enabled = _loc2_.allowGetAfroFromClanBank;
      this.takeGold_btn.enabled = _loc2_.allowGetGoldFromClanBank;
      this.takeAfro_txt._visible = true;
      this.underTakeAfro.gotoAndStop(1);
      if(!_loc2_.allowGetAfroFromClanBank)
      {
         this.infoTakeAfro_txt.htmlText = "У вас нет права снимать Афро\rс кланового счета";
         this.underTakeAfro.gotoAndStop(2);
         this.takeAfro_txt._visible = false;
      }
      this.takeGold_txt._visible = true;
      this.underTakeGold.gotoAndStop(1);
      if(!_loc2_.allowGetGoldFromClanBank)
      {
         this.infoTakeGold_txt.htmlText = "У вас нет права снимать Голд\rс кланового счета";
         this.underTakeGold.gotoAndStop(2);
         this.takeGold_txt._visible = false;
      }
      this.refreshMoney();
      this.putAfro_txt.onChanged = mx.utils.Delegate.create(this,this.putAfroChanges);
      this.putGold_txt.onChanged = mx.utils.Delegate.create(this,this.putGoldChanges);
      this.takeAfro_txt.onChanged = mx.utils.Delegate.create(this,this.takeAfroChanges);
      this.takeGold_txt.onChanged = mx.utils.Delegate.create(this,this.takeGoldChanges);
      this.putAfro_txt.tabIndex = 0;
      this.putGold_txt.tabIndex = 1;
      this.takeAfro_txt.tabIndex = 2;
      this.takeGold_txt.tabIndex = 3;
      this.putAfro_txt.restrict = "0-9";
      this.putGold_txt.restrict = "0-9 . ,";
      this.takeAfro_txt.restrict = "0-9";
      this.takeGold_txt.restrict = "0-9 . ,";
      this.putAfro_txt.maxChars = 6;
      this.putGold_txt.maxChars = 6;
      this.takeAfro_txt.maxChars = 6;
      this.takeGold_txt.maxChars = 6;
   }
   function updateMoneyPan()
   {
      this.killMoneyPage();
      this.doLater("initMoneyPage");
   }
   function killMoneyPage()
   {
      Key.removeListener(this);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.updateMoneyPan);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.ADD_MONEY_TO_CLAN_AMMOUNT_SUCCES,this,this.refreshMoney);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.WITHDRAW_MONEY_FROM_CLAN_AMMOUNT_SUCCES,this,this.refreshMoney);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_ACCOUNT_AFRO_AMMOUNT,this,this.refreshAfroAck);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_ACCOUNT_GOLD_AMMOUNT,this,this.refreshGoldAck);
      this.back_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.backFunc);
      this.putAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.putAfro);
      this.takeAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeAfro);
      this.putGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.putGold);
      this.takeGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.takeGold);
   }
   function putAfroChanges()
   {
      this.clearInfoTxt();
      var _loc2_ = Number(this.putAfro_txt.text);
      if(_loc2_ > this.afro)
      {
         this.putAfro_btn.enabled = false;
         this.infoPutAfro_txt.htmlText = "Недостаточно средств";
      }
      else
      {
         this.putAfro_btn.enabled = true;
         this.infoPutAfro_txt.htmlText = "";
      }
   }
   function putGoldChanges()
   {
      this.clearInfoTxt();
      var _loc2_ = this.checkNum(this.putGold_txt.text);
      this.infoPutGold_txt.htmlText = _loc2_.info;
      this.putGold_txt.text = _loc2_.str;
      var _loc3_ = Number(this.putGold_txt.text);
      if(_loc2_.info == "")
      {
         if(_loc3_ > this.gold)
         {
            this.putGold_btn.enabled = false;
            this.infoPutGold_txt.htmlText = "Недостаточно средств";
         }
         else
         {
            this.putGold_btn.enabled = true;
            this.infoPutGold_txt.htmlText = "";
         }
      }
   }
   function takeAfroChanges()
   {
      this.clearInfoTxt();
      var _loc2_ = Number(this.takeAfro_txt.text);
      if(_loc2_ > this.clanAfro)
      {
         this.takeAfro_btn.enabled = false;
         this.infoTakeAfro_txt.htmlText = "Недостаточно средств";
      }
      else
      {
         this.takeAfro_btn.enabled = true;
         this.infoTakeAfro_txt.htmlText = "";
      }
   }
   function takeGoldChanges()
   {
      this.clearInfoTxt();
      var _loc2_ = this.checkNum(this.takeGold_txt.text);
      this.infoTakeGold_txt.htmlText = _loc2_.info;
      this.takeGold_txt.text = _loc2_.str;
      var _loc3_ = Number(this.takeGold_txt.text);
      if(_loc2_.info == "")
      {
         if(_loc3_ > this.clanGold)
         {
            this.takeGold_btn.enabled = false;
            this.infoTakeGold_txt.htmlText = "Недостаточно средств";
         }
         else
         {
            this.takeGold_btn.enabled = true;
            this.infoTakeGold_txt.htmlText = "";
         }
      }
   }
   function checkNum(str)
   {
      var _loc2_ = new Object();
      _loc2_.info = "";
      str = lol.utils.ParseString.replaceAll(str,",",".");
      var _loc3_ = str.indexOf(".",0);
      var _loc4_;
      if(_loc3_ != -1)
      {
         _loc4_ = str.substring(_loc3_ + 1,str.length);
      }
      if(_loc4_.length > 2)
      {
         str = str.substring(0,_loc3_ + 3);
      }
      if(String(Number(str)) == "NaN")
      {
         _loc2_.info = "Сумма введена неправильно";
      }
      _loc2_.str = str;
      return _loc2_;
   }
   function refreshMoney()
   {
      this.afro = this.master.gamer.attributes.afro;
      this.gold = this.master.gamer.attributes.gold / 100;
      var _loc3_ = this.master.playerRegister.gamer.clanMemberInfo;
      var _loc2_ = _loc3_.rights;
      if(_loc2_.allowGetAfroFromClanBank)
      {
         this.clanInspector.getClanAccauntAfroAmmount();
      }
      else
      {
         this.afro_txt.html = true;
         this.afro_txt.autoSize = true;
         this.afro_txt.htmlText = "у вас недостаточно прав\rдля просмотра счета";
         if(this.operationSuccess)
         {
            this.operationInfo.htmlText = "Операция прошла успешно";
            this.operationSuccess = false;
         }
      }
      if(_loc2_.allowGetGoldFromClanBank)
      {
         this.clanInspector.getClanAccauntGoldAmmount();
      }
      else
      {
         this.gold_txt.html = true;
         this.gold_txt.autoSize = true;
         this.gold_txt.htmlText = "у вас недостаточно прав\rдля просмотра счета";
         if(this.operationSuccess)
         {
            this.operationInfo.htmlText = "Операция прошла успешно";
            this.operationSuccess = false;
         }
      }
   }
   function refreshAfroAck(obj)
   {
      this.clanAfro = obj.body;
      if(this.operationSuccess)
      {
         this.operationInfo.htmlText = "Операция прошла успешно";
         this.operationSuccess = false;
      }
      this.afro_txt.text = this.clanAfro;
   }
   function refreshGoldAck(obj)
   {
      this.clanGold = obj.body / 100;
      if(this.operationSuccess)
      {
         this.operationInfo.htmlText = "Операция прошла успешно";
         this.operationSuccess = false;
      }
      this.gold_txt.text = this.clanGold;
   }
   function backFunc()
   {
      this.killMoneyPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
   }
   function clearInfoTxt()
   {
      this.infoPutAfro_txt.text = "";
      this.infoPutGold_txt.text = "";
      this.infoTakeAfro_txt.text = "";
      this.infoTakeGold_txt.text = "";
   }
   function takeAfro()
   {
      var _loc2_;
      if(this.takeAfro_txt.text != "" && this.takeAfro_txt.text != "0" && Number(this.takeAfro_txt.text) > 0)
      {
         _loc2_ = Number(this.takeAfro_txt.text);
         this.clanInspector.withdrawMoneyFromClanAccount("AFRO",_loc2_);
         this.takeAfro_txt.text = "";
         this.operationSuccess = true;
         this.operationInfo = this.infoTakeAfro_txt;
      }
   }
   function putAfro()
   {
      var _loc2_;
      if(this.putAfro_txt.text != "" && this.putAfro_txt.text != "0" && Number(this.putAfro_txt.text) > 0)
      {
         _loc2_ = Number(this.putAfro_txt.text);
         this.clanInspector.addMoneyToClanAccount("AFRO",_loc2_);
         this.putAfro_txt.text = "";
         this.operationSuccess = true;
         this.operationInfo = this.infoPutAfro_txt;
      }
   }
   function takeGold()
   {
      var _loc2_;
      var _loc3_;
      if(this.takeGold_txt.text != "" && this.takeGold_txt.text != "0")
      {
         _loc2_ = this.takeGold_txt.text;
         _loc2_ = lol.utils.ParseString.replaceAll(_loc2_,",",".");
         _loc3_ = Number(_loc2_) * 100;
         if(String(_loc3_) != "NaN")
         {
            this.clanInspector.withdrawMoneyFromClanAccount("GOLD",_loc3_);
            this.takeGold_txt.text = "";
            this.infoTakeGold_txt.htmlText = "";
            this.operationSuccess = true;
            this.operationInfo = this.infoTakeGold_txt;
         }
         else
         {
            this.infoTakeGold_txt.htmlText = "Сумма введена неправильно";
         }
      }
   }
   function putGold()
   {
      var _loc2_;
      var _loc3_;
      if(this.putGold_txt.text != "" && this.putGold_txt.text != "0")
      {
         _loc2_ = this.putGold_txt.text;
         _loc2_ = lol.utils.ParseString.replaceAll(_loc2_,",",".");
         _loc3_ = Number(_loc2_) * 100;
         if(String(_loc3_) != "NaN")
         {
            this.clanInspector.addMoneyToClanAccount("GOLD",_loc3_);
            this.putGold_txt.text = "";
            this.infoPutGold_txt.htmlText = "";
            this.operationSuccess = true;
            this.operationInfo = this.infoPutGold_txt;
         }
         else
         {
            this.infoPutGold_txt.htmlText = "Сумма введена неправильно";
         }
      }
   }
   function onKeyDown()
   {
      var _loc2_;
      if(Key.getCode() == 13)
      {
         _loc2_ = Selection.getFocus();
         if(_loc2_ == String(this.putAfro_txt))
         {
            this.putAfro();
         }
         else if(_loc2_ == String(this.putGold_txt))
         {
            this.putGold();
         }
         else if(_loc2_ == String(this.takeAfro_txt))
         {
            this.takeAfro();
         }
         else if(_loc2_ == String(this.takeGold_txt))
         {
            this.takeGold();
         }
      }
   }
   function initStandingPage()
   {
      this.currSort = null;
      this.clanName_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortStandingBy_func);
      this.clanName_btn.data = "name";
      this.ourStanding_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortStandingBy_func);
      this.ourStanding_btn.data = "parseStat";
      this.clanName_btn._alpha = 0;
      this.ourStanding_btn._alpha = 0;
      var _loc4_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_BY);
      var _loc3_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_REVERSE);
      if(_loc4_ == "name")
      {
         this.clanName_btn.toggled = _loc3_;
         this.currSort = this.clanName_btn;
         this.clanName_btn._alpha = 100;
      }
      else if(_loc4_ == "parseStat")
      {
         this.ourStanding_btn.toggled = _loc3_;
         this.currSort = this.ourStanding_btn;
         this.ourStanding_btn._alpha = 100;
      }
      this.back_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.standingBackFunc);
      this.askStanding_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.askStanding);
      this.upStanding_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.upStanding);
      this.downStanding_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.downStanding);
      this.askStanding_btn.enabled = false;
      this.upStanding_btn.enabled = false;
      this.downStanding_btn.enabled = false;
      this.standingList = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo.standingArray;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE,this,this.buildStandingList);
      var _loc5_ = this.clanInspector.upStandingCost;
      var _loc2_ = this.clanInspector.downStandingCost;
      if(_loc5_ != undefined && _loc2_ != undefined)
      {
         this.up_txt.text = _loc5_;
         this.down_txt.text = _loc2_;
      }
      else
      {
         this.clanInspector.addEventListener(lol.core.clans.ClanEvent.STANDING_COST,this,this.standingCost);
         this.clanInspector.getStandingCost();
      }
      this.buildStandingList();
   }
   function standingCost()
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.STANDING_COST,this,this.standingCost);
      var _loc3_ = this.clanInspector.upStandingCost;
      var _loc2_ = this.clanInspector.downStandingCost;
      this.up_txt.text = _loc3_;
      this.down_txt.text = _loc2_;
   }
   function killStandingPage()
   {
      this.clanName_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortStandingBy_func);
      this.ourStanding_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.sortStandingBy_func);
      this.back_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.standingBackFunc);
      this.askStanding_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.askStanding);
      this.upStanding_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.upStanding);
      this.downStanding_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.downStanding);
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.CLAN_STANDING_UPDATE,this,this.buildStandingList);
   }
   function sortStandingBy_func(obj)
   {
      if(this.currSort != obj.target)
      {
         this.currSort._alpha = 0;
         this.currSort.toggled = false;
         this.currSort = obj.target;
         this.currSort._alpha = 100;
      }
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_BY,this.currSort.data);
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_REVERSE,this.currSort.toggled);
      this.buildStandingList();
   }
   function standingBackFunc()
   {
      this.killStandingPage();
      this.gotoAndStop(this.membersList_frame);
      this.doLater("initClanMembersPage");
   }
   function buildStandingList()
   {
      this.killStandingList();
      this.askStanding_btn.enabled = false;
      this.upStanding_btn.enabled = false;
      this.downStanding_btn.enabled = false;
      this.curStanding = null;
      this.standingList = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo.standingArray;
      this.clanPan.setSize(734,333);
      var _loc5_ = this.clanPan.fillContent();
      var _loc4_ = this.sortStandingArray(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_BY),lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SORT_STANDING_LIST_REVERSE));
      var _loc6_ = new TextFormat();
      _loc6_.bold = true;
      var _loc3_ = 0;
      var _loc2_;
      while(_loc3_ < _loc4_.length)
      {
         if(_loc4_[_loc3_].names != this.master.gamer.clanMemberInfo.clanInfo.clanName)
         {
            _loc2_ = _loc5_.attachMovie("clanItem","clanItem" + _loc5_.getNextHighestDepth(),_loc5_.getNextHighestDepth());
            _loc2_._y = Math.round(this.getNextLowestPoint() + 2);
            _loc2_.clanStandingInfo = _loc4_[_loc3_].clanStandingInfo;
            _loc2_.name_txt.text = _loc4_[_loc3_].name;
            _loc2_.myStanding_txt.text = _loc4_[_loc3_].parseStat;
            _loc2_.theirStanding_txt.text = this.parseStatString(_loc4_[_loc3_].theirStat);
            _loc2_.bg._alpha = (_loc3_ % 2 + 1) * 50;
            this.doLater("initStandingBg",[_loc2_.bg]);
            this.currStandingList.push(_loc2_);
         }
         _loc3_ = _loc3_ + 1;
      }
      this.clanPan.chekSize();
   }
   function initStandingBg(mc)
   {
      mc.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectStanding);
      mc.addEventListener(lol.gpui.controls.GPUIButton.DOUBLE_CLICK,this,this.doubleClickStanding);
   }
   function selectStanding(obj)
   {
      if(this.curStanding != obj.target._parent)
      {
         this.curStanding.bg.toggled = false;
         this.curStanding.bg._alpha = this.prevAlpha;
         this.curStanding = obj.target._parent;
         this.prevAlpha = this.curStanding.bg._alpha;
         if(this.prevAlpha == 50)
         {
            this.curStanding.bg._alpha = 100;
         }
      }
      else
      {
         this.curStanding.bg.toggled = true;
      }
      var _loc3_ = this.curStanding.clanStandingInfo;
      var _loc2_ = this.master.gamer.clanMemberInfo.rights;
      this.upStanding_btn.enabled = _loc2_.allowChangeStandings && _loc3_.stat != 1;
      this.downStanding_btn.enabled = _loc2_.allowChangeStandings && _loc3_.stat != -1;
      this.askStanding_btn.enabled = true;
   }
   function doubleClickStanding()
   {
   }
   function askStanding()
   {
      var _loc2_ = this.curStanding.clanStandingInfo;
      var _loc3_ = _loc2_.data;
      this.clanInspector.getStanding(_loc3_);
   }
   function upStanding()
   {
      var _loc2_ = this.curStanding.clanStandingInfo;
      var _loc3_ = _loc2_.data;
      this.tempClanName = _loc2_.name;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.SET_STANDING_SUCCES,this,this.upStandingAck);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.SET_STANDING_NO_MONEY,this,this.setStandingNoMoney);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.WE_SET_STANDING,this,this.weSetStanding);
      this.clanInspector.setStanding("up",_loc3_);
   }
   function upStandingAck()
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.SET_STANDING_SUCCES,this,this.upStandingAck);
      var _loc2_ = this.openAlertWindow("Вы улучшили отношения с кланом <" + this.tempClanName + ">");
   }
   function weSetStanding()
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.WE_SET_STANDING,this,this.weSetStanding);
      this.buildStandingList();
   }
   function downStanding()
   {
      var _loc2_ = this.curStanding.clanStandingInfo;
      var _loc3_ = _loc2_.data;
      this.tempClanName = _loc2_.name;
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.SET_STANDING_SUCCES,this,this.downStandingAck);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.SET_STANDING_NO_MONEY,this,this.setStandingNoMoney);
      this.clanInspector.addEventListener(lol.core.clans.ClanEvent.WE_SET_STANDING,this,this.weSetStanding);
      this.clanInspector.setStanding("down",_loc3_);
   }
   function downStandingAck()
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.SET_STANDING_SUCCES,this,this.downStandingAck);
      var _loc2_ = this.openAlertWindow("Вы ухудшили отношения с кланом <" + this.tempClanName + ">");
      this.buildStandingList();
   }
   function setStandingNoMoney()
   {
      this.clanInspector.removeEventListener(lol.core.clans.ClanEvent.SET_STANDING_NO_MONEY,this,this.setStandingNoMoney);
      var _loc2_ = this.openAlertWindow("Не хватает денег\rна клановом счете");
   }
   function sortStandingArray(type, reverse)
   {
      var _loc4_ = new Array();
      this.standingList = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo.standingArray;
      var _loc3_;
      var _loc2_;
      for(var _loc5_ in this.standingList)
      {
         _loc3_ = this.standingList[_loc5_];
         _loc2_ = new Object();
         _loc2_.clanStandingInfo = _loc3_;
         _loc2_.name = _loc3_.name;
         _loc2_.stat = _loc3_.stat;
         _loc2_.parseStat = this.parseStatString(_loc3_.stat);
         _loc2_.theirStat = _loc3_.theirStat;
         _loc2_.data = _loc3_.data;
         _loc4_.push(_loc2_);
      }
      _loc4_.sortOn(type);
      if(!reverse)
      {
         _loc4_.reverse();
      }
      return _loc4_;
   }
   function parseStatString(stat)
   {
      switch(stat)
      {
         case 0:
            return "Нейтралитет";
         case 1:
            return "Мир";
         case -1:
            return "Война";
         case undefined:
            return "Не известно";
         default:
            return stat;
      }
   }
   function killStandingList()
   {
      for(var _loc2_ in this.currStandingList)
      {
         this.currStandingList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectMember);
         this.currStandingList[_loc2_].bg.removeEventListener(lol.gpui.controls.GPUIButton.DOUBLE_CLICK,this,this.doubleClick);
      }
      this.currItem = null;
      this.currStandingList = new Array();
   }
   function openAlertWindow(str)
   {
      var _loc1_ = lol.core.SceneShifter.openNewWindow("alert");
      _loc1_.content.label = str;
   }
   function getNextLowestPoint()
   {
      return this.clanPan.cont_mc._height;
   }
   function enabledAllCheckBox()
   {
      this.chatAndViewStandings.enabled = false;
      this.addItemsToClanStorage.enabled = false;
      this.getItemsFromClanStorage.enabled = false;
      this.acceptNewBaseMembers.enabled = false;
      this.fireBaseMembers.enabled = false;
      this.acceptNewMiddleMembers.enabled = false;
      this.getAfroFromClanBank.enabled = false;
      this.getGoldFromClanBank.enabled = false;
      this.changeStandings.enabled = false;
   }
   function unselectAllCheckBox()
   {
      this.chatAndViewStandings.toggled = false;
      this.addItemsToClanStorage.toggled = false;
      this.getItemsFromClanStorage.toggled = false;
      this.acceptNewBaseMembers.toggled = false;
      this.fireBaseMembers.toggled = false;
      this.acceptNewMiddleMembers.toggled = false;
      this.getAfroFromClanBank.toggled = false;
      this.getGoldFromClanBank.toggled = false;
      this.changeStandings.toggled = false;
   }
   function enabledCheckBox(_rights)
   {
      if(this.rankDetection(_rights) == 0)
      {
         this.enabledAllCheckBox();
         this.allRights.enabled = false;
         this.allRights.toggled = false;
      }
      else if(this.rankDetection(_rights) == 1)
      {
         this.enabledAllCheckBox();
         this.allRights.enabled = false;
         this.allRights.toggled = false;
      }
      else if(this.rankDetection(_rights) == 2)
      {
         this.enabledAllCheckBox();
         this.chatAndViewStandings.enabled = true;
         this.addItemsToClanStorage.enabled = true;
         this.acceptNewBaseMembers.enabled = true;
         this.getItemsFromClanStorage.enabled = true;
      }
      else if(this.rankDetection(_rights) == 3)
      {
         this.enabledAllCheckBox();
         this.chatAndViewStandings.enabled = true;
         this.addItemsToClanStorage.enabled = true;
         this.acceptNewBaseMembers.enabled = true;
         this.getItemsFromClanStorage.enabled = true;
      }
   }
   function setRightsCheckBox(_rights)
   {
      this.acceptNewBaseMembers.toggled = _rights._allowAcceptNewBaseMembers;
      this.acceptNewMiddleMembers.toggled = _rights.allowAcceptNewMiddleMembers;
      this.addItemsToClanStorage.toggled = _rights.allowAddItemsToClanStorage;
      this.changeStandings.toggled = _rights.allowChangeStandings;
      this.chatAndViewStandings.toggled = _rights.allowChatAndViewStandings;
      this.fireBaseMembers.toggled = _rights.allowFireBaseMembers;
      this.getAfroFromClanBank.toggled = _rights.allowGetAfroFromClanBank;
      this.getGoldFromClanBank.toggled = _rights.allowGetGoldFromClanBank;
      this.getItemsFromClanStorage.toggled = _rights.allowGetItemsFromClanStorage;
   }
   function unselectionOutRightsCheckBox(_rights)
   {
      if(this.rankDetection(_rights) == 0)
      {
         this.unselectAllCheckBox();
      }
      else if(this.rankDetection(_rights) == 1)
      {
         this.getItemsFromClanStorage.toggled = false;
         this.acceptNewBaseMembers.toggled = false;
         this.fireBaseMembers.toggled = false;
         this.acceptNewMiddleMembers.toggled = false;
         this.getAfroFromClanBank.toggled = false;
         this.getGoldFromClanBank.toggled = false;
         this.changeStandings.toggled = false;
      }
      else if(this.rankDetection(_rights) == 2)
      {
         this.fireBaseMembers.toggled = false;
         this.getAfroFromClanBank.toggled = false;
         this.getGoldFromClanBank.toggled = false;
         this.changeStandings.toggled = false;
         this.acceptNewMiddleMembers.toggled = false;
      }
      else if(this.rankDetection(_rights) == 3)
      {
         this.fireBaseMembers.toggled = false;
         this.getAfroFromClanBank.toggled = false;
         this.getGoldFromClanBank.toggled = false;
         this.changeStandings.toggled = false;
         this.acceptNewMiddleMembers.toggled = false;
      }
   }
   function kill()
   {
      lol.core.SceneShifter.hotKeyManager.removeFilter("clan");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.cancel);
      this.killAddMemberPage();
      this.killChangeRightsPage();
      this.killClanList();
      this.killClanMembersPage();
      this.killCreatePage();
      this.killMoneyPage();
   }
   function selectionOfEnding(num)
   {
      var _loc1_ = String(num);
      var _loc2_ = Number(_loc1_.substring(_loc1_.length - 1,_loc1_.length));
      if(_loc2_ >= 2 && _loc2_ <= 4)
      {
         return "а";
      }
      return "";
   }
   function rankDetection(_rights)
   {
      var _loc2_ = 0;
      if(_rights.allowChatAndViewStandings || _rights.allowAddItemsToClanStorage)
      {
         _loc2_ = 0;
      }
      if(_rights.allowAcceptNewBaseMembers || _rights.allowGetItemsFromClanStorage)
      {
         _loc2_ = 1;
      }
      if(_rights.allowFireBaseMembers || _rights.allowAcceptNewMiddleMembers || _rights.allowGetAfroFromClanBank || _rights.allowGetGoldFromClanBank)
      {
         _loc2_ = 2;
      }
      if(!_rights.allowAllOtherRights && _rights.allowChangeStandings)
      {
         _loc2_ = 2;
      }
      if(_rights.allowAllOtherRights)
      {
         _loc2_ = 4;
      }
      return _loc2_;
   }
}
