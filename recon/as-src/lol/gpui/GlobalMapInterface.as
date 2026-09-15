class lol.gpui.GlobalMapInterface extends lol.gpui.GPUIObject
{
   var _visible;
   var addEventListener;
   var ambush_btn;
   var apBar;
   var attack_btn;
   var avatarPan;
   var back_mc;
   var bottom_shadow;
   var centerChar_btn;
   var centerToLable_btn;
   var charInfo_btn;
   var clan_btn;
   var coordinate_txt;
   var copyHash_btn;
   var copyLog_btn;
   var createLabel_btn;
   var curID;
   var curType;
   var description_mc;
   var displayMap;
   var dragFlag;
   var editLabelPan;
   var editLabel_btn;
   var enterLoc_btn;
   var enterLoc_btn_alert;
   var follow_btn;
   var forum_btn;
   var frame_bottom_middle;
   var frame_left_corner;
   var frame_left_mask;
   var frame_mask;
   var frame_right;
   var frame_right_corner;
   var frame_right_mask;
   var frame_top;
   var frame_top_right;
   var getURL;
   var globalMap;
   var globalMapFrame;
   var goldToAfro_btn;
   var gold_btn;
   var helpAlert_mc;
   var help_btn;
   var help_mc;
   var hideMode_btn;
   var inventary_btn;
   var labelData;
   var leftBottom;
   var leftMask;
   var leftPan;
   var left_shadow;
   var locBorder_mc;
   var mail_btn;
   var markInfoPan;
   var markList_mc;
   var markPoint;
   var marks_btn;
   var master;
   var moneyPanAfro;
   var moneyPanGold;
   var moveToLabel_btn;
   var mselected;
   var newMailAlert_mc;
   var newType;
   var otherAv;
   var planshet_btn;
   var questInfo_mc;
   var quest_btn;
   var removeMovieClip;
   var rightMask;
   var rightPan;
   var rightPanControl;
   var right_shadow;
   var runMode_btn;
   var scaleDown_btn;
   var scaleUp_btn;
   var selectedUser;
   var sendMess_btn;
   var settingsWin;
   var settings_btn;
   var showGrid_btn;
   var showLabels_btn;
   var tStopMove;
   var tempMark;
   var topWindow;
   var top_shadow;
   var trophy_btn;
   var tt;
   var userInfo_mc;
   var userList_mc;
   var users_btn;
   var walkMode_btn;
   var winConMask;
   var winContainer;
   var bagFlag = false;
   var toLocEnabled = true;
   var equipFlag = false;
   var questInfoFlag = false;
   var clanFlag = false;
   var charFlag = false;
   function GlobalMapInterface()
   {
      super();
      this.doLater(this,"init");
      this.master = lol.core.Master.getInstance();
      this.master.addEventListener("changeWorld",this,this.chWAck);
      this.globalMap = this.master.globalMap;
      this.globalMap.addEventListener("addPlayer",this);
      this.globalMap.addEventListener("lost",this);
      this.globalMap.addEventListener("startMove",this,this.interceptDisabled);
      this.globalMap.addEventListener("addMark",this);
      this.globalMap.addEventListener("removeMark",this);
      this.globalMap.addEventListener("updateMark",this);
      lol.core.quests.QuestInspector.getInstance().addEventListener("update",this,this.reInitQuestMarks);
      Key.addListener(this);
      Mouse.addListener(this);
      this.addEventListener("bagOpen",this);
      this._visible = false;
   }
   function chatRes(obj)
   {
      var _loc5_ = lol.core.SceneShifter._ref.minW;
      var _loc4_ = lol.core.SceneShifter._ref.maxW;
      var _loc3_ = new Object();
      var _loc2_ = Stage.width >= _loc4_ ? _loc4_ : Stage.width;
      _loc2_ = _loc2_ <= _loc5_ ? _loc5_ : _loc2_;
      _loc3_.w = _loc2_;
      _loc3_.h = obj.h + 144;
      this.resizeStage(_loc3_);
   }
   function resizeStageDoLater()
   {
   }
   function resizeStage(obj)
   {
      if(!this._visible)
      {
         this._visible = true;
      }
      var _loc4_ = 1040;
      var _loc3_ = 720;
      this.winContainer._x = Math.round(obj.w / 2);
      this.winConMask._width = obj.w;
      this.bottom_shadow._y = obj.h - 186;
      this.bottom_shadow._width = obj.w - 51;
      this.left_shadow._height = this.bottom_shadow._y - 46;
      this.top_shadow._width = obj.w - 51;
      this.right_shadow._x = this.top_shadow._width + this.top_shadow._x - 7;
      this.right_shadow._height = this.left_shadow._height;
      this.frame_top_right._x = obj.w;
      this.frame_top._x = obj.w / 2;
      this.frame_left_mask._width = obj.w / 2;
      this.frame_right_mask._x = obj.w / 2;
      this.frame_right_mask._width = obj.w / 2;
      this.frame_right._x = obj.w;
      this.frame_mask._width = obj.w;
      this.frame_mask._height = obj.h - 200;
      this.frame_left_corner._y = obj.h - 334;
      this.frame_right_corner._y = obj.h - 334;
      this.frame_right_corner._x = obj.w;
      this.frame_bottom_middle._x = obj.w / 2;
      this.frame_bottom_middle._y = obj.h - 168;
      this.avatarPan._y = obj.h - 353;
      this.questInfo_mc._y = obj.h - 284;
      this.planshet_btn._y = Math.round(obj.h - 216);
      this.coordinate_txt._x = Math.round(obj.w - this.coordinate_txt._width - 70);
      this.coordinate_txt._y = Math.round(obj.h - 230);
      if(this.leftPan.panActivationFlag)
      {
         this.leftPan._y = obj.h - 327;
      }
      else
      {
         this.leftPan._y = obj.h - 206;
      }
      this.leftPan.propeties();
      this.leftBottom._y = obj.h - 180;
      this.leftMask._y = obj.h - 351;
      if(this.rightPan.panActivationFlag)
      {
         this.rightPan._y = obj.h - 320;
      }
      else
      {
         this.rightPan._y = obj.h - 199;
      }
      this.rightPan.propeties();
      this.rightPanControl._y = obj.h - 180;
      this.rightMask._y = obj.h - 351;
      this.apBar._x = (obj.w - this.apBar._width) / 2;
      this.topWindow._x = (obj.w - this.topWindow._width) / 2;
      this.globalMapFrame.setSize(obj.w - 50,obj.h - 200);
      this.back_mc._width = obj.w - 40;
      this.back_mc._height = obj.h - 200;
   }
   function init()
   {
      this.enterLoc_btn = this.frame_top.enterLoc_btn;
      this.centerChar_btn = this.frame_top.centerChar_btn;
      this.showGrid_btn = this.frame_top.showGrid_btn;
      this.scaleUp_btn = this.frame_top.scaleUp_btn;
      this.scaleDown_btn = this.frame_top.scaleDown_btn;
      this.enterLoc_btn_alert = this.frame_top.enterLoc_btn_alert;
      this.enterLoc_btn_alert._alpha = 0;
      this.enterLoc_btn_alert.stop();
      this.master.globalMap.gamer.walker.addEventListener("stopMove",this,this.stopMoveGamer);
      this.master.globalMap.gamer.walker.addEventListener("startMove",this,this.startMoveGamer);
      this.sendMess_btn = this.rightPanControl.sendMess_btn;
      this.sendMess_btn.enabled = false;
      this.follow_btn = this.rightPanControl.follow_btn;
      this.follow_btn.enabled = false;
      this.follow_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.interceptPlayer);
      this.goldToAfro_btn = this.frame_top.goldToAfro_btn;
      this.gold_btn = this.frame_top.gold_btn;
      this.forum_btn = this.frame_left_corner.forum_btn;
      this.copyLog_btn = this.frame_left_corner.copyLog_btn;
      this.copyHash_btn = this.frame_left_corner.copyHash_btn;
      this.goldToAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goldToAfro);
      this.gold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      this.forum_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToForum);
      this.copyLog_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
      this.copyHash_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyHash);
      this.createLabel_btn = this.rightPanControl.createLabel_btn;
      this.centerToLable_btn = this.rightPanControl.centerToLable_btn;
      this.showLabels_btn = this.rightPanControl.showLabels_btn;
      this.moveToLabel_btn = this.rightPanControl.moveToLabel_btn;
      this.editLabel_btn = this.rightPanControl.editLabel_btn;
      this.createLabel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.centerToLable_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.showLabels_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.moveToLabel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.editLabel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.inventary_btn = this.frame_left_corner.inventary_btn;
      this.trophy_btn = this.frame_left_corner.trophy_btn;
      this.inventary_btn.enabled = false;
      this.trophy_btn.enabled = false;
      this.charInfo_btn = this.frame_left_corner.charInfo_btn;
      this.quest_btn = this.frame_left_corner.quest_btn;
      this.mail_btn = this.frame_left_corner.mail_btn;
      this.newMailAlert_mc = this.frame_left_corner.newMailAlert_mc;
      this.newMailAlert_mc._visible = false;
      this.clan_btn = this.frame_left_corner.clan_btn;
      this.settings_btn = this.frame_left_corner.settings_btn;
      this.charInfo_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.charInfo_btn.data = "char";
      this.clan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.clan_btn.data = "clan";
      this.quest_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.quest_btn.data = "questInfo";
      this.mail_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.mail_btn.data = "mail";
      this.settings_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openSettingsInterface);
      this.planshet_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.planshet_btn.data = "questInfo";
      this.avatarPan.char_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.avatarPan.char_btn.data = "char";
      lol.core.mail.MailInspector.getInstance().addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.checkNewLetter);
      lol.core.mail.MailInspector.getInstance().addEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.checkNewLetter);
      this.checkNewLetter();
      this.hideMode_btn.label = "тихо";
      this.walkMode_btn.label = "шаг";
      this.runMode_btn.label = "бег";
      this.walkMode_btn.toggled = true;
      this.ambush_btn.label = "засада";
      this.attack_btn.label = "атака";
      this.enterLoc_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.toLocation);
      this.centerChar_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.centerChar);
      this.showGrid_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showGrid);
      this.scaleUp_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scaleUp);
      this.scaleDown_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scaleDown);
      this.help_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openHelp);
      this.displayMap = this.globalMapFrame.fillContent("testGlobMap");
      this.displayMap.addEventListener("centerPoint",this);
      this.displayMap.addEventListener("unlockMapAndMove",this,this.unlockMapAndMove);
      this.displayMap.addEventListener("releaseMap",this,this.releaseMap);
      this.displayMap.addEventListener("pressOnPlayer",this,this.pressMap);
      this.displayMap.addEventListener("cursorPosition",this,this.cursorPosition);
      this.locBorder_mc = this.displayMap.attachMovie("locBorder","locBorder",this.displayMap.getNextHighestDepth());
      this.locBorder_mc.name_txt.html = true;
      this.initUsers();
      this.initMarks();
      this.switchCursorMode("move");
      this.rightPan.addEventListener("control",this);
      this.rightPan.markList_mc.setSize(97,97);
      this.rightPan.userList_mc.setSize(97,97);
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
      lol.core.SceneShifter.chat.addEventListener("chatRes",this);
      lol.core.SceneShifter._ref.setMCSize();
      this.master.gamer.addEventListener("uiUpd",this,this.gamerUiUpd);
      var _loc5_ = new lol.utils.Timeout(this,this.updMoney,500);
      this.initHotKey();
      this.enterLoc_btn.hintTitle_str = "Перейти в локацию";
      this.centerChar_btn.hintTitle_str = "Центровать на персонаже";
      this.showGrid_btn.hintTitle_str = "Включить/выключить сетку";
      this.scaleUp_btn.hintTitle_str = "Увеличить масштаб";
      this.scaleDown_btn.hintTitle_str = "Уменьшить масштаб";
      this.createLabel_btn.hintTitle_str = "Создать метку на карте";
      this.centerToLable_btn.hintTitle_str = "Центровать на метке";
      this.moveToLabel_btn.hintTitle_str = "Идти к метке";
      this.showLabels_btn.hintTitle_str = "Показать/скрыть метки на карте";
      this.editLabel_btn.hintTitle_str = "Редактировать метку";
      this.users_btn.hintTitle_str = "Список игроков";
      this.marks_btn.hintTitle_str = "Список меток на карте";
      this.leftPan.hideMoveModePan_btn.hintTitle_str = "Открыть/закрыть панель";
      this.rightPan.hideMarksAndPlayers_btn.hintTitle_str = "Открыть/закрыть панель";
      this.follow_btn.hintTitle_str = "Перехват игрока";
      this.goldToAfro_btn.hintTitle_str = "Обмен золота на афро";
      this.gold_btn.hintTitle_str = "Пополнить счет";
      this.forum_btn.hintTitle_str = "Форум";
      this.help_btn.hintTitle_str = "Помощь";
      this.copyLog_btn.hintTitle_str = "Скопировать лог в буфер обмена";
      this.copyHash_btn.hintTitle_str = "Скопировать хэш в буфер обмена";
      this.planshet_btn.hintTitle_str = "Задания";
      this.charInfo_btn.hintTitle_str = "Информация о персонаже";
      this.quest_btn.hintTitle_str = "Задания";
      this.clan_btn.hintTitle_str = "Клан";
      this.mail_btn.hintTitle_str = "Почта";
      this.settings_btn.hintTitle_str = "Настройки";
      this.avatarPan.healthBar_btn.hintTitle_str = "Индикатор здоровья";
      this.avatarPan.staminaBar_btn.hintTitle_str = "Индикатор выносливости";
      this.avatarPan.caunter_mc.health_btn.hintTitle_str = "Счетчик здоровья";
      this.avatarPan.caunter_mc.stamina_btn.hintTitle_str = "Счетчик выносливости";
      this.avatarPan.char_btn.stamina_btn.hintTitle_str = "Информация о персонаже";
      var _loc4_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GRID);
      this.globalMapFrame.content.grid_mc._visible = _loc4_;
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.GLOBAL_SCALE);
      if(_loc2_ == "up")
      {
         this.displayMap.scaleUp();
      }
      else if(_loc2_ == "down")
      {
         this.displayMap.scaleDown();
      }
      var _loc3_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.LABEL_OR_PLAYERS);
      if(_loc3_ == "label")
      {
         this.control({marks:true,players:false});
      }
      else if(_loc3_ == "player")
      {
         this.control({marks:false,players:true});
      }
      else
      {
         this.control({marks:false,players:false});
      }
      this.tt = new lol.utils.Timeout(this,this.showTooltip,5000);
   }
   function chWAck(obj)
   {
      this.toLocEnabled = !obj.success;
   }
   function toLocation()
   {
      if(this.toLocEnabled)
      {
         this.toLocEnabled = false;
         this.master.changeWorld();
      }
   }
   function initHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.addFilter("global");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.PERS_INFO,this,this.char_key);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CHANGE_WORLD,this,this.toLocation);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CENTER_ON_CHAR,this,this.centerChar);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SETTINGS,this,this.openSettingsInterface);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SCALE_UP,this,this.scaleUp);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SCALE_DOWN,this,this.scaleDown);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.GRID,this,this.showGrid);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.KEY_PRESS,this,this.showNames);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.KEY_RELEASE,this,this.hideNames);
   }
   function killHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.removeFilter("location");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.PERS_INFO,this,this.char_key);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CHANGE_WORLD,this,this.toLocation);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CENTER_ON_CHAR,this,this.centerChar);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SETTINGS,this,this.openSettingsInterface);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SCALE_UP,this,this.scaleUp);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SCALE_DOWN,this,this.scaleDown);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.GRID,this,this.showGrid);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.KEY_PRESS,this,this.showNames);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.KEY_RELEASE,this,this.hideNames);
   }
   function openCloseSlideWindow(obj)
   {
      var _loc2_ = obj.target.data;
      if(!lol.core.SceneShifter._sl.isWindow)
      {
         this.openMc(_loc2_);
      }
      else if(this[_loc2_ + "Flag"])
      {
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeSlideWindow);
      }
      else
      {
         this.newType = _loc2_;
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeAndOpen);
      }
   }
   function openMc(type)
   {
      var mc = this[type + "_mc"];
      this.curType = type;
      this[type + "Flag"] = true;
      var _loc3_ = lol.core.SceneShifter.gmapScreen;
      var _loc4_ = lol.core.SceneShifter.openNewSlideWindow(type,_loc3_);
      _loc4_.addEventListener("close",this,this.closeCurWindow);
      delete mc.onEnterFrame;
      mc.onEnterFrame = function()
      {
         mc.nextFrame();
         if(mc._currentframe == mc._totalframes)
         {
            delete mc.onEnterFrame;
         }
      };
   }
   function closeMc(type)
   {
      var mc = this[type + "_mc"];
      delete mc.onEnterFrame;
      mc.onEnterFrame = function()
      {
         mc.prevFrame();
         if(mc._currentframe == 1)
         {
            delete mc.onEnterFrame;
         }
      };
   }
   function closeAndOpen()
   {
      this[this.curType + "Flag"] = false;
      lol.core.SceneShifter._sl.removeEventListener("closeSlideGroup",this,this.closeAndOpen);
      this.openMc(this.newType);
      this.newType = null;
   }
   function closeSlideWindow()
   {
      this[this.curType + "Flag"] = false;
      lol.core.SceneShifter._sl.removeEventListener("closeSlideGroup",this,this.closeSlideWindow);
      this.curType = null;
   }
   function closeCurWindow(obj)
   {
      this.closeMc(this.curType);
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.closeSlideWindow(this.curType);
      var _loc2_ = lol.core.Master.getInstance().gamer;
      _loc2_.equipment.close();
      obj.target.removeEventListener("close",this,this.closeCurWindow);
   }
   function equip_key()
   {
      var _loc2_ = new Object();
      _loc2_.data = "equip";
      this.openCloseSlideWindow({target:_loc2_});
   }
   function char_key()
   {
      var _loc2_ = new Object();
      _loc2_.data = "char";
      this.openCloseSlideWindow({target:_loc2_});
   }
   function control(obj)
   {
      this.chekToggledItem();
      this.follow_btn._visible = obj.players;
      this.sendMess_btn._visible = obj.players;
      this.createLabel_btn._visible = obj.marks;
      this.showLabels_btn._visible = obj.marks;
      this.editLabel_btn._visible = obj.marks;
      this.centerToLable_btn._visible = obj.marks;
      this.rightPanControl._visible = obj.marks || obj.players;
   }
   function chekToggledItem()
   {
      var _loc2_ = this.markList_mc.getList();
      for(var _loc3_ in _loc2_)
      {
         if(_loc2_[_loc3_].toggled)
         {
            this.markInfoPan._visible = true;
            break;
         }
      }
   }
   function click(obj)
   {
      var _loc4_;
      var _loc3_;
      switch(obj.target)
      {
         case this.createLabel_btn:
            this.createNewLabel(obj);
            break;
         case this.centerToLable_btn:
            _loc4_ = this.displayMap.markManager.getMarkNum(this.labelData);
            _loc3_ = this.displayMap.markManager.markList[_loc4_];
            this.centerPoint({point:{x:_loc3_._x,y:_loc3_._y},how:true});
            break;
         case this.showLabels_btn:
            this.showHideLabels(obj);
            break;
         case this.moveToLabel_btn:
            _loc4_ = this.displayMap.markManager.getMarkNum(this.labelData);
            _loc3_ = this.displayMap.markManager.markList[_loc4_];
            this.moveToLabel(_loc3_._x,_loc3_._y);
            break;
         case this.editLabel_btn:
            this.openEditLabelPan(obj);
         default:
            return;
      }
   }
   function initUsers()
   {
      this.userList_mc = this.rightPan.userList_mc;
      this.userInfo_mc = this.rightPan.userInfo_mc;
      this.otherAv = this.userInfo_mc.otherAv;
      this.userList_mc.addEventListener("click",this,this.__selectUser);
      var _loc2_;
      for(var _loc3_ in this.globalMap.playerList)
      {
         if(_loc3_ != lol.core.player.Gamer.ID)
         {
            _loc2_ = this.globalMap.playerList[_loc3_];
            this.addPlayer({player:_loc2_});
         }
      }
   }
   function addPlayer(obj)
   {
      var _loc2_ = obj.player;
      var _loc5_ = _loc2_.id;
      var _loc4_ = _loc2_.playerInfo;
      var _loc3_;
      if(_loc4_.name)
      {
         _loc3_ = _loc4_.name;
      }
      else
      {
         _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
         _loc3_ = _loc5_;
      }
      this.userList_mc.addItem({label:_loc3_,data:_loc2_});
   }
   function userInfoUpdate(obj)
   {
      obj.target.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      var _loc5_ = obj.target.id;
      var _loc4_ = obj.target.playerInfo.name;
      var _loc3_ = this.userList_mc.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data.id == _loc5_)
         {
            _loc3_[_loc2_].label = _loc4_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function lost(obj)
   {
      var _loc6_ = obj.player;
      var _loc3_ = obj.id;
      var _loc4_ = this.userList_mc.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc4_.length)
      {
         if(_loc4_[_loc2_].data.id == _loc3_)
         {
            this.displayMap.playerList[_loc3_].selectselect(false);
            this.userList_mc.removeItem(_loc2_);
            this.otherAv._visible = false;
            return undefined;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function __selectUser(obj)
   {
      var _loc3_;
      var _loc4_;
      if(obj.item.toggled)
      {
         _loc3_ = obj.item.data;
         _loc4_ = obj.item.toggled;
         this.otherAv._visible = true;
         this.userInfo_mc.id_txt.text = _loc3_.id;
         this.showAvatar(_loc3_.id);
         this.selectedUser = _loc3_;
         this.follow_btn.enabled = true;
         this.displayMap.playerList[_loc3_.id].select(true);
         this.displayMap.playerList[this.curID].select(false);
         this.curID = _loc3_.id;
      }
      else
      {
         _loc3_ = obj.item.data;
         this.otherAv._visible = false;
         this.selectedUser = null;
         this.follow_btn.enabled = false;
         this.displayMap.playerList[_loc3_.id].select(false);
         this.curID = null;
      }
   }
   function showAvatar(id)
   {
      var _loc5_ = this.master.getPlayer(id);
      var _loc6_ = _loc5_.playerInfo;
      var _loc2_ = _loc6_.avatar.id;
      var _loc3_ = lol.services.SSEmulator.getAvatarURL(_loc2_,1);
      var _loc4_ = lol.display.DisplaySprite.create(this.otherAv,"av",0);
      _loc4_.display("big_avatar" + _loc2_,_loc3_);
   }
   function initMarks()
   {
      this.markList_mc = this.rightPan.markList_mc;
      this.markInfoPan = this.rightPan.markInfoPan;
      this.markList_mc.addEventListener("click",this,this.__selectMark);
      var _loc2_;
      for(var _loc3_ in this.globalMap.markList)
      {
         _loc2_ = this.globalMap.markList[_loc3_];
         this._addMark({mark:_loc2_},lol.core.globmap.MarkManager.LABEL_TYPE);
      }
      this.initQuestMarks();
   }
   function initQuestMarks()
   {
      var _loc4_ = lol.core.quests.QuestInspector.getInstance().getCurrentQuests();
      var _loc2_;
      var _loc5_;
      var _loc3_;
      for(var _loc6_ in _loc4_)
      {
         _loc2_ = _loc4_[_loc6_].quest;
         _loc5_ = new Object();
         _loc5_.title = _loc2_.name;
         _loc5_.info = _loc2_.start_desc;
         _loc5_.type = "quest";
         if(_loc4_[_loc6_].complete)
         {
            if(_loc2_.finish_loc != -1 && _loc2_.name)
            {
               _loc3_ = lol.utils.LocIdToCoordinate.getValue(_loc2_.finish_loc);
               _loc5_.x = _loc3_.x;
               _loc5_.y = _loc3_.y;
               this._addMark({mark:_loc5_},lol.core.globmap.MarkManager.QUEST_TAKE);
            }
         }
         else if(_loc2_.loc != 0 && _loc2_.name)
         {
            _loc3_ = lol.utils.LocIdToCoordinate.getValue(_loc2_.loc);
            _loc5_.x = _loc3_.x;
            _loc5_.y = _loc3_.y;
            this._addMark({mark:_loc5_},lol.core.globmap.MarkManager.QUEST_GET);
         }
      }
   }
   function reInitQuestMarks()
   {
      var _loc3_ = this.displayMap.markManager.markList;
      var _loc2_ = 0;
      var _loc4_;
      var _loc5_;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].type == lol.core.globmap.MarkManager.QUEST_GET || _loc3_[_loc2_].type == lol.core.globmap.MarkManager.QUEST_TAKE)
         {
            _loc4_ = _loc3_[_loc2_];
            _loc4_.removeEventListener("_moveToLabel",this,this._moveToLabel);
            _loc5_ = _loc4_.markObj;
            this.displayMap.markManager.removeMark(_loc5_);
            this.markList_mc.removeItem(_loc2_);
         }
         _loc2_ = _loc2_ + 1;
      }
      this.initQuestMarks();
   }
   function createNewLabel(obj)
   {
      if(obj.target.toggled)
      {
         this.switchCursorMode("label");
      }
      else
      {
         this.switchCursorMode("move");
      }
   }
   function setLabel()
   {
      delete this.globalMapFrame.mask_mc.onPress;
      var _loc2_ = this.globalMapFrame.mask_mc;
      var _loc3_ = new flash.geom.Rectangle(0,0,_loc2_._width,_loc2_._height);
      var _loc4_ = this.globalMapFrame.mask_mc._xmouse;
      var _loc5_ = this.globalMapFrame.mask_mc._ymouse;
      var _loc6_ = new flash.geom.Point(_loc4_,_loc5_);
      if(_loc3_.containsPoint(_loc6_) && this.createLabel_btn.toggled)
      {
         this.createLabel_btn.toggled = false;
         this.markPoint = this.displayMap.getMouseCoord();
         this.editLabelPan = lol.core.SceneShifter.openNewWindow("editLabel");
         this.editLabelPan.content.addEventListener("applyMark",this);
         this.editLabelPan.content.delete_btn._visible = false;
      }
      this.switchCursorMode("move");
   }
   function applyMark(obj)
   {
      var _loc5_ = this.markPoint.x;
      var _loc4_ = this.markPoint.y;
      var _loc3_ = obj.title;
      var _loc2_ = obj.info;
      this.globalMap.addMark(_loc5_,_loc4_,_loc3_,_loc2_);
   }
   function addMark(obj)
   {
      this._addMark(obj,lol.core.globmap.MarkManager.LABEL_TYPE);
   }
   function _addMark(obj, type)
   {
      var _loc2_ = obj.mark;
      var _loc6_ = this.markList_mc.addItem({label:_loc2_.title,data:_loc2_});
      var _loc3_ = this.displayMap.addMark(_loc2_,type);
      if(type == lol.core.globmap.MarkManager.LABEL_TYPE)
      {
         _loc3_.addEventListener("editMark",this);
      }
      _loc3_.addEventListener("_moveToLabel",this,this._moveToLabel);
      this.markInfoPan.title_txt.text = _loc2_.title;
      this.markInfoPan.info_txt.html = true;
      this.markInfoPan.info_txt.text = _loc2_.info;
   }
   function parseString(strIn)
   {
      var _loc1_ = lol.utils.ParseString.replaceAll(strIn,"\\","");
      return lol.utils.ParseString.replaceAll(_loc1_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
   }
   function _moveToLabel(obj)
   {
      var _loc3_ = this.displayMap.markManager.getMarkNum(obj.target.markObj);
      var _loc2_ = this.displayMap.markManager.markList[_loc3_];
      if(_loc2_._x != undefined && _loc2_._y != undefined)
      {
         this.displayMap.playerMoveToCoords(_loc2_._x + 4,_loc2_._y + 4);
      }
   }
   function deleteMark(obj)
   {
      this.globalMap.removeMark(this.tempMark);
   }
   function removeMark(obj)
   {
      var _loc4_ = obj.mark;
      this.displayMap.removeMark(_loc4_);
      var _loc3_ = this.markList_mc.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data == _loc4_)
         {
            this.markList_mc.removeItem(_loc2_);
            this.markList_mc.chekSize();
            this.markInfoPan._visible = false;
            this.editLabel_btn.toggled = false;
            return undefined;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function editMark(obj)
   {
      this.tempMark = obj.target.markObj;
      this.editLabelPan = lol.core.SceneShifter.openNewWindow("editLabel");
      this.editLabelPan.content.addEventListener("applyMark",this,this.applyEdit);
      this.editLabelPan.content.addEventListener("deleteMark",this);
      this.editLabelPan.content.addEventListener("canselMark",this);
      this.editLabelPan.content.setMark(this.tempMark);
   }
   function openEditLabelPan()
   {
      this.tempMark = this.markList_mc.selectedItem.data;
      if(this.tempMark && this.tempMark.type != "quest")
      {
         this.editLabelPan = lol.core.SceneShifter.openNewWindow("editLabel");
         this.editLabelPan.addEventListener("closeWindow",this);
         this.editLabelPan.content.addEventListener("applyMark",this,this.applyEdit);
         this.editLabelPan.content.addEventListener("deleteMark",this);
         this.editLabelPan.content.addEventListener("canselMark",this);
         this.editLabelPan.content.setMark(this.tempMark);
      }
      else
      {
         this.editLabel_btn.toggled = false;
      }
   }
   function canselMark(obj)
   {
      this.editLabel_btn.toggled = false;
   }
   function applyEdit(obj)
   {
      this.editLabel_btn.toggled = false;
      this.unDescriptionMark();
      this.descriptionMark(obj.title,obj.info);
      this.globalMap.editMark({mark:this.tempMark,info:obj.info,title:obj.title});
   }
   function __selectMark(obj)
   {
      var _loc2_;
      var _loc4_;
      if(obj.item.toggled)
      {
         _loc2_ = obj.item.data;
         this.labelData = _loc2_;
         _loc4_ = obj.item.toggled;
         this.displayMap.selectMark(_loc2_);
         this.editLabelPan.setMark(_loc2_);
         this.markInfoPan._visible = true;
         this.descriptionMark(_loc2_.title,_loc2_.info);
         this.mselected = true;
      }
      else
      {
         this.labelData = null;
         this.markInfoPan._visible = false;
         this.displayMap.selectMark();
         this.unDescriptionMark();
         this.mselected = false;
      }
   }
   function descriptionMark(t, d)
   {
      this.description_mc = this.markInfoPan.description_mc;
      this.description_mc.vBar.scrollValue = 1;
      var _loc2_ = this.description_mc;
      var _loc3_ = this.markInfoPan.vBar;
      _loc3_.scrollValue = 2;
      _loc2_.title_txt.autoSize = true;
      _loc2_.desc_txt.autoSize = true;
      _loc2_.title_txt.htmlText = mx.utils.XMLString.unescape(t);
      _loc2_.desc_txt.htmlText = this.parseString(mx.utils.XMLString.unescape(d));
      this.doLater("checkSize");
      _loc3_.addEventListener("position",this);
   }
   function position(obj)
   {
      var _loc2_ = this.markInfoPan.desc_mask._height - this.description_mc._height;
      this.description_mc._y = _loc2_ * obj.pos / 100;
   }
   function checkSize()
   {
      var _loc2_ = this.markInfoPan.vBar;
      var _loc3_ = this.markInfoPan.desc_mask._height - this.description_mc._height;
      if(_loc3_ > 0)
      {
         _loc2_._visible = false;
      }
      else
      {
         _loc2_._visible = true;
      }
      this.description_mc.title_txt._y = this.description_mc.mark_mc._height;
      this.description_mc.line_mc._y = this.description_mc.title_txt._y + this.description_mc.title_txt._height;
      this.description_mc.desc_txt._y = this.description_mc.line_mc._y + this.description_mc.line_mc._height;
   }
   function unDescriptionMark()
   {
      this.markInfoPan.description_mc.clearContent();
   }
   function updateMark(obj)
   {
      var _loc7_ = obj.id;
      var _loc4_ = obj.title;
      var _loc6_ = obj.info;
      this.displayMap.updateMark(obj.mark);
      var _loc3_ = this.markList_mc.getList();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_].data == obj.mark)
         {
            this.descriptionMark(_loc4_,_loc6_);
            if(!_loc3_[_loc2_].toggled)
            {
               this.markList_mc.itemColor(_loc3_[_loc2_]);
            }
            _loc3_[_loc2_].label = _loc4_;
            return undefined;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function showHideLabels(obj)
   {
      if(!obj.target.toggled)
      {
         this.globalMapFrame.content.marks_mc._visible = true;
      }
      else
      {
         this.globalMapFrame.content.marks_mc._visible = false;
      }
   }
   function travelMode(obj)
   {
      this.hideMode_btn.toggled = obj.target != this.hideMode_btn ? false : true;
      this.walkMode_btn.toggled = obj.target != this.walkMode_btn ? false : true;
      this.runMode_btn.toggled = obj.target != this.runMode_btn ? false : true;
   }
   function showGrid(obj)
   {
      if(!this.globalMapFrame.content.grid_mc._visible)
      {
         this.globalMapFrame.content.grid_mc._visible = true;
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_GRID,true);
      }
      else
      {
         this.globalMapFrame.content.grid_mc._visible = false;
         lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_GRID,false);
      }
   }
   function centerChar()
   {
      this.displayMap.centerChar(true);
   }
   function centerPoint(obj)
   {
      this.centerToLable_btn.toggled = false;
      var _loc5_ = obj.how;
      var _loc3_ = obj.point.x;
      var _loc2_ = obj.point.y;
      if(_loc5_)
      {
         this.globalMapFrame.slideToCenter(_loc3_,_loc2_);
      }
      else
      {
         this.globalMapFrame.centerPoint(_loc3_,_loc2_);
      }
   }
   function moveToLabel(X, Y)
   {
      if(X != undefined && Y != undefined)
      {
         this.displayMap.playerMoveToCoords(X + 4,Y + 4);
      }
   }
   function onKeyDown()
   {
   }
   function onKeyUp()
   {
      this.globalMapFrame.setHandScroll(false);
   }
   function scaleUp()
   {
      this.displayMap.scaleUp();
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.GLOBAL_SCALE,"up");
   }
   function scaleDown()
   {
      this.displayMap.scaleDown();
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.GLOBAL_SCALE,"down");
   }
   function getFrameSize()
   {
      return this.globalMapFrame.getSize();
   }
   function switchCursorMode(cmode)
   {
      delete this.back_mc.onPress;
      switch(cmode)
      {
         case "label":
            this.back_mc.onPress = mx.utils.Delegate.create(this,this.setLabel);
            delete this.back_mc.onRelease;
            return;
         case "move":
            this.navigateMap();
      }
      this.navigateMap();
   }
   function navigateMap()
   {
      this.back_mc.onPress = mx.utils.Delegate.create(this,this.pressMap);
      this.back_mc.onRelease = mx.utils.Delegate.create(this,this.unlockMapAndMove);
   }
   function pressMap()
   {
      this.back_mc.onMouseMove = mx.utils.Delegate.create(this,this.dragMap);
      this.globalMapFrame.startDragContent();
   }
   function dragMap()
   {
      this.dragFlag = true;
   }
   function unlockMapAndMove()
   {
      if(!this.dragFlag)
      {
         this.displayMap.playerMove();
      }
      this.releaseMap();
   }
   function releaseMap()
   {
      delete this.back_mc.onMouseMove;
      this.dragFlag = false;
      this.globalMapFrame.stopDragContent();
   }
   function gamerUiUpd()
   {
      this.updMoney();
   }
   function updMoney()
   {
      this.moneyPanAfro = this.frame_top.moneyPanAfro;
      this.moneyPanGold = this.frame_top.moneyPanGold;
      this.moneyPanAfro.value = this.master.gamer.attributes.afro;
      this.moneyPanGold.type = "gold";
      this.moneyPanGold.value = this.master.gamer.attributes.gold;
   }
   function kill()
   {
      this.tt.Clear();
      this.leftPan.kill();
      this.rightPan.kill();
      lol.core.quests.QuestInspector.getInstance().removeEventListener("update",this,this.reInitQuestMarks);
      this.enterLoc_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.toLocation);
      this.centerChar_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.centerChar);
      this.showGrid_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showGrid);
      this.scaleUp_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scaleUp);
      this.scaleDown_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.scaleDown);
      this.help_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openHelp);
      this.goldToAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goldToAfro);
      this.gold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      this.forum_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToForum);
      this.copyLog_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
      this.copyHash_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyHash);
      this.createLabel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.centerToLable_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.showLabels_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.moveToLabel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.editLabel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
      this.charInfo_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.clan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.quest_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.mail_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.settings_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openSettingsInterface);
      lol.core.mail.MailInspector.getInstance().removeEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.checkNewLetter);
      lol.core.mail.MailInspector.getInstance().removeEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.checkNewLetter);
      this.displayMap.removeEventListener("centerPoint",this);
      this.displayMap.removeEventListener("moveToPlayer",this,this.unlockMapAndMove);
      this.displayMap.removeEventListener("pressOnPlayer",this,this.pressMap);
      this.rightPan.removeEventListener("control",this);
      lol.core.SceneShifter.chat.removeEventListener("chatRes",this);
      this.master.gamer.removeEventListener("uiUpd",this);
      this.killHotKey();
      this.globalMap.removeEventListener("addPlayer",this);
      this.globalMap.removeEventListener("lost",this);
      this.globalMap.removeEventListener("addMark",this);
      this.globalMap.removeEventListener("removeMark",this);
      this.globalMap.removeEventListener("updateMark",this);
      this.globalMap.removeEventListener("startMove",this,this.interceptDisabled);
      this.displayMap.removeEventListener("centerPoint",this);
      this.displayMap.kill();
      delete this.displayMap;
      delete this.globalMap;
      lol.core.SceneShifter.hintManager.killHint();
      this.removeMovieClip();
   }
   function cursorPosition(obj)
   {
      var _loc3_ = obj.x;
      var _loc2_ = obj.y;
      this.coordinate_txt.html = true;
      var _loc4_ = lol.utils.GetLocName.instance.getName(_loc3_,_loc2_);
      this.coordinate_txt.htmlText = "<font size=\'14\'>  </font><br>X: " + _loc3_ + "    Y: " + _loc2_;
      if(_loc4_ != null)
      {
         this.drawLocBorder("<i>" + _loc4_ + "</i>",Number(_loc3_) * obj.mapScale,Number(_loc2_) * obj.mapScale);
      }
      else
      {
         this.locBorder_mc._visible = false;
      }
   }
   function drawLocBorder(name, x, y)
   {
      this.locBorder_mc._x = x;
      this.locBorder_mc._y = y;
      this.locBorder_mc.name_txt.htmlText = name;
      this.locBorder_mc._visible = true;
   }
   function openSettingsInterface()
   {
      if(lol.core.SceneShifter._ref.UIPanels.settings.instance)
      {
         lol.core.SceneShifter.closeWindow("settings");
         this.settingsWin = null;
         delete this.settingsWin;
      }
      else
      {
         this.settingsWin = lol.core.SceneShifter.openNewWindow("settings");
      }
   }
   function openHelp()
   {
      this.help_mc.openClose();
   }
   function goldToAfro()
   {
      lol.core.SceneShifter.openNewWindow("goldToAfro");
   }
   function goToUserPage()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
   function goToForum()
   {
      var _loc2_ = "http://www.lava-online.ru/forum/";
      this.getURL(_loc2_,"_blank");
   }
   function startMoveGamer(obj)
   {
      this.enterLoc_btn_alert._alpha = 0;
      this.enterLoc_btn_alert.stop();
      this.tStopMove.Clear();
   }
   function stopMoveGamer(obj)
   {
      this.enterLoc_btn_alert.gotoAndPlay(1);
      this.enterLoc_btn_alert._alpha = 100;
      this.tStopMove = new lol.utils.Timeout(this,this.stopAlertEnterLocBtn,10000);
   }
   function stopAlertEnterLocBtn()
   {
      this.enterLoc_btn_alert._alpha = 0;
      this.enterLoc_btn_alert.stop();
   }
   function interceptPlayer(obj)
   {
      if(this.selectedUser)
      {
         if(this.follow_btn.toggled)
         {
            lol.core.Master.getInstance().globalMap.interceptPlayer(this.selectedUser.id,true);
         }
         else
         {
            lol.core.Master.getInstance().globalMap.interceptPlayer(this.selectedUser.id,false);
         }
      }
   }
   function interceptDisabled()
   {
      this.follow_btn.toggled = false;
   }
   function checkNewLetter()
   {
      var _loc4_ = lol.core.mail.MailInspector.getInstance().getInbox();
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc4_.length)
      {
         _loc3_ = _loc4_[_loc2_];
         if(!_loc3_.read)
         {
            this.newMailAlert_mc._visible = true;
            this.newMailAlert_mc._alpha = 100;
            break;
         }
         this.newMailAlert_mc._visible = false;
         _loc2_ = _loc2_ + 1;
      }
   }
   function showTooltip()
   {
      if(lol.core.SceneShifter._ref.addGoldTooltip_bool)
      {
         lol.gpui.HintManager.showHint(this.gold_btn.hintTitle_str,0,0,this.frame_top._x + this.gold_btn._x + 10,this.frame_top._y + this.gold_btn._y + 5);
         this.tt = new lol.utils.Timeout(this,this.showHelpTooltip,5000);
         lol.core.SceneShifter._ref.addGoldTooltip_bool = false;
      }
   }
   function showHelpTooltip()
   {
      lol.gpui.HintManager.showHint(this.help_btn.hintTitle_str,0,0,this.help_btn._x + 40,this.help_btn._y + 17);
      this.tt = new lol.utils.Timeout(this,this.closeHelpTooltip,5000);
      this.helpAlert_mc.play();
   }
   function closeHelpTooltip()
   {
      lol.gpui.HintManager.closeHint();
   }
   function showNames(obj)
   {
      if(obj.code == 17)
      {
         this.displayMap.showAllNames();
      }
      if(obj.code == 16)
      {
         this.displayMap.prepareForContextMenu(true);
      }
   }
   function hideNames(obj)
   {
      if(obj.code == 17)
      {
         this.displayMap.hideAllNames();
      }
      if(obj.code == 16)
      {
         this.displayMap.prepareForContextMenu(false);
      }
   }
}
