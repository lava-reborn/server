class lol.gpui.LocationInterface extends lol.gpui.GPUIObject
{
   var BG_Manager;
   var _parent;
   var apBar;
   var attachMovie;
   var avatarPan;
   var bag_btn;
   var bag_mc;
   var battleLoc_btn;
   var battlegrounds_btn;
   var bottom_shadow;
   var charInfo_btn;
   var clan_btn;
   var codeDown;
   var codeDown1;
   var codeHandScroll;
   var codeLeft;
   var codeLeft1;
   var codeRight;
   var codeRight1;
   var codeUP;
   var codeUP1;
   var copyHash_btn;
   var copyLog_btn;
   var createEmptyMovieClip;
   var curType;
   var dispatchEvent;
   var displayLoc;
   var effectsPan;
   var equip_mc;
   var exitLoc_btn;
   var exit_btn;
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
   var fxPanMask;
   var getNextHighestDepth;
   var getURL;
   var goldToAfro_btn;
   var gold_btn;
   var helpAlert_mc;
   var help_btn;
   var help_mc;
   var inventary_btn;
   var leaveLocation_mc;
   var left_shadow;
   var locationFrame;
   var mail_btn;
   var mainSlotPan;
   var master;
   var miniMapMask;
   var miniMapPan;
   var moneyPanAfro;
   var moneyPanGold;
   var newMailAlert_mc;
   var newServiceMessage;
   var newType;
   var onEnterFrame;
   var planshet;
   var planshet_btn;
   var primaryItem_mc;
   var questInfo_mc;
   var quest_btn;
   var reload_btn;
   var right_shadow;
   var settingsWin;
   var settings_btn;
   var showhideFX_Btn;
   var showhideFX_back;
   var spt;
   var spt_int;
   var startBGPrepareTime;
   var startTime;
   var tf;
   var timer_mc;
   var topWindow;
   var top_shadow;
   var totalBGPrepareTime;
   var trophy_btn;
   var tt;
   var weaponMask;
   var weapon_bottom;
   var winConMask;
   var winContainer;
   var planshetFlag = false;
   var bagFlag = false;
   var equipFlag = false;
   var questInfoFlag = false;
   var clanFlag = false;
   var charFlag = false;
   var mailFlag = false;
   var trophyFlag = false;
   var enabledExitLoc = true;
   var toGMEnabled = true;
   var pressUp = false;
   var pressDown = false;
   var pressRight = false;
   var pressLeft = false;
   var curStepX = 0;
   var curStepY = 0;
   var maxStep = 30;
   var acseleration = 10;
   var _flagSceneEnabled = false;
   var traderMessage_bool = true;
   var bagOverload_bool = true;
   var gamer_level = -1;
   var gamer_gold = -1;
   var canLeavelocation = true;
   var exitTime = 0;
   function LocationInterface()
   {
      super();
      this.doLater("init");
      Key.addListener(this);
      lol.events.LEventDispatcher.initialize(this);
   }
   function init()
   {
      this.leaveLocation_mc._visible = false;
      lol.core.Master.getInstance().addEventListener("changeWorld",this,this.chWAck);
      this.locationFrame.addEventListener("position",this);
      this.goldToAfro_btn = this.frame_top.goldToAfro_btn;
      this.gold_btn = this.frame_top.gold_btn;
      this.forum_btn = this.frame_left_corner.forum_btn;
      this.copyLog_btn = this.frame_left_corner.copyLog_btn;
      this.copyHash_btn = this.frame_left_corner.copyHash_btn;
      this.bag_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.bag_btn.data = "equip";
      this.planshet_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.planshet_btn.data = "questInfo";
      this.avatarPan.char_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.avatarPan.char_btn.data = "char";
      this.exitLoc_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.toGlobal);
      this.inventary_btn = this.frame_left_corner.inventary_btn;
      this.charInfo_btn = this.frame_left_corner.charInfo_btn;
      this.quest_btn = this.frame_left_corner.quest_btn;
      this.clan_btn = this.frame_left_corner.clan_btn;
      this.mail_btn = this.frame_left_corner.mail_btn;
      this.trophy_btn = this.frame_left_corner.trophy_btn;
      this.battlegrounds_btn = this.frame_left_corner.battlegrounds_btn;
      this.settings_btn = this.frame_left_corner.settings_btn;
      this.newMailAlert_mc = this.frame_left_corner.newMailAlert_mc;
      this.newMailAlert_mc._visible = false;
      this.newMailAlert_mc._alpha = 100;
      this.inventary_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.inventary_btn.data = "equip";
      this.charInfo_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.charInfo_btn.data = "char";
      this.clan_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.clan_btn.data = "clan";
      this.mail_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.mail_btn.data = "mail";
      this.trophy_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.trophy_btn.data = "trophy";
      this.quest_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.quest_btn.data = "questInfo";
      this.BG_Manager = lol.core.battlegrounds.BattleGroundManager.getInstance();
      this.BG_Manager.addEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_PREPARE_TIME,this,this.startBGPrepareTimer);
      trace("BG_Manager = " + this.BG_Manager);
      this.settings_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openSettingsInterface);
      this.battlegrounds_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.battlegrounds_btn.data = "battlegrounds";
      lol.core.mail.MailInspector.getInstance().addEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.checkNewLetter);
      lol.core.mail.MailInspector.getInstance().addEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.checkNewLetter);
      this.checkNewLetter();
      this.help_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openHelp);
      this.exit_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.exitGame);
      this.goldToAfro_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goldToAfro);
      this.gold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      this.forum_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToForum);
      this.copyLog_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
      this.copyHash_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyHash);
      this.master = lol.core.Master.getInstance();
      this.master.locGen.addEventListener("locLoaded",this);
      this.doLater("locLoaded");
      var _loc2_ = this.master.gamer;
      if(this.master.gamer)
      {
         _loc2_.effects.addEventListener(lol.events.PlayerEvent.NEED_OPEN_FXPAN,this,this.effectsUpdate);
      }
      this.currentLocation.addEventListener("warState",this);
      this.currentLocation.addEventListener("addPlayer",this,this.addPlayer);
      this.currentLocation.addEventListener("startExitTimer",this,this.startExitTimer);
      var _loc3_ = this.master.gamer.attributes.gold;
      if(_loc3_ > 100)
      {
         this.traderMessage_bool = false;
      }
      this.checkTrader();
      this.tt = new lol.utils.Timeout(this,this.showTooltip,5000);
      this.battleLoc_btn.label = "Start battle";
      this.battleLoc_btn.onPress = function()
      {
         this._parent.battle = !this._parent.battle;
         this._parent.battleMode();
      };
      this.battleMode(this.currentLocation.warStatus);
      this.displayLoc = this.locationFrame.fillContent("testLoc");
      this.displayLoc.addEventListener("centerPoint",this);
      this.displayLoc.cursorManager.addEventListener("spriteOver",this,this.onSpriteOver);
      this.displayLoc.cursorManager.addEventListener("spriteOut",this,this.onSpriteOut);
      this.master.gamer.apManager.addEventListener("actionPoints",this);
      this.master.gamer.addEventListener("uiUpd",this);
      var _loc4_ = new lol.utils.Timeout(this,this.updMoney,1000);
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this);
      lol.core.SceneShifter.chat.addEventListener("chatRes",this);
      lol.core.SceneShifter._ref.setMCSize();
      this.reload_btn = this.weapon_bottom.reload_btn;
      this.reload_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.reload_func);
      this.reload_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT,this,this.reload_func_outside);
      this.reload_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.reload_func_press);
      this.reload_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT,this,this.hideReloadAP);
      this.reload_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.showReloadAP);
      this.showhideFX_Btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.panActivation);
      this.showhideFX_Btn.hintTitle_str = "Открыть/закрыть панель эффектов";
      this.exitLoc_btn.hintTitle_str = "Перейти на глобальную карту";
      this.reload_btn.hintTitle_str = "Перезарядить оружие";
      this.goldToAfro_btn.hintTitle_str = "Обмен золота на афро";
      this.gold_btn.hintTitle_str = "Пополнить счет";
      this.forum_btn.hintTitle_str = "Форум";
      this.help_btn.hintTitle_str = "Помощь";
      this.copyLog_btn.hintTitle_str = "Скопировать лог в буфер обмена";
      this.copyHash_btn.hintTitle_str = "Скопировать хэш в буфер обмена";
      this.weapon_bottom.um0_btn.hintTitle_str = "Одиночный выстрел";
      this.weapon_bottom.um1_btn.hintTitle_str = "Очередь";
      this.weapon_bottom.um2_btn.hintTitle_str = "Прицельный выстрел";
      this.avatarPan.healthBar_btn.hintTitle_str = "Индикатор здоровья";
      this.avatarPan.staminaBar_btn.hintTitle_str = "Индикатор выносливости";
      this.avatarPan.caunter_mc.health_btn.hintTitle_str = "Счетчик здоровья";
      this.avatarPan.caunter_mc.stamina_btn.hintTitle_str = "Счетчик выносливости";
      this.avatarPan.char_btn.stamina_btn.hintTitle_str = "Информация о персонаже";
      this.miniMapPan.hideMiniMapPan_btn.hintTitle_str = "Открыть/закрыть миникарту";
      this.miniMapPan.back_btn.hintTitle_str = "Миникарта";
      this.mainSlotPan.hidePan_btn.hintTitle_str = "Открыть/закрыть панель оружия";
      this.mainSlotPan.cw_btn.hintTitle_str = "Сменить активный слот";
      this.weapon_bottom.heal_btn.hintTitle_str = "Восстановить здоровье";
      this.weapon_bottom.eat_btn.hintTitle_str = "Восстановить выносливость";
      this.planshet_btn.hintTitle_str = "Взятые задания";
      this.bag_btn.hintTitle_str = "Инвентарь";
      this.inventary_btn.hintTitle_str = "Инвентарь";
      this.charInfo_btn.hintTitle_str = "Информация о персонаже";
      this.quest_btn.hintTitle_str = "Взятые задания";
      this.clan_btn.hintTitle_str = "Клан";
      this.mail_btn.hintTitle_str = "Почта";
      this.trophy_btn.hintTitle_str = "Трофеи";
      this.settings_btn.hintTitle_str = "Настройки";
      this.initHotKey();
      lol.core.quests.QuestInspector.getInstance().addEventListener(lol.core.quests.Quest.COMPLETE,this,this.questComplete);
      lol.core.quests.QuestInspector.getInstance().addEventListener(lol.core.quests.Quest.KILL_MOB,this,this.killMob);
      lol.core.quests.QuestInspector.getInstance().addEventListener(lol.core.quests.Quest.GET_OBJECT,this,this.getObject);
      lol.core.quests.QuestInspector.getInstance().addEventListener(lol.core.quests.Quest.DEL_OBJECT,this,this.delObject);
      this.exitLoc_btn.enabled = !this.master.gamer.prepare;
   }
   function reload_func_press()
   {
      this.weapon_bottom.reloadAlert._visible = false;
   }
   function reload_func_outside()
   {
      this.weapon_bottom.reloadAlert._visible = true;
      this.apBar.otherCost = 0;
      this.apBar.showAPCost();
   }
   function reload_func()
   {
      this.weapon_bottom.reloadAlert._visible = true;
      var _loc2_ = this.master.gamer;
      var _loc3_ = _loc2_.equipment;
      _loc3_.loadPrimary();
   }
   function showReloadAP()
   {
      var _loc2_ = this.master.gamer.equipment.primaryItem;
      if(_loc2_ instanceof lol.core.objects.FireArm)
      {
         this.apBar.otherCost = lol.core.objects.FireArm(_loc2_).getAP(lol.core.objects.Item.LOAD);
         this.apBar.showAPCost();
      }
   }
   function hideReloadAP()
   {
      this.apBar.otherCost = 0;
      this.apBar.showAPCost();
   }
   function effectsUpdate()
   {
      if(!lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.FX_PAN_OPEN))
      {
         this.effectsPan.panActivation();
      }
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
   function resizeStage(obj)
   {
      var _loc4_ = lol.core.SceneShifter._sl;
      _loc4_.getWindow("charInterface").content.showInfo();
      this.winContainer._x = Math.round(obj.w / 2);
      this.winConMask._width = obj.w - 2 * this.winConMask._x;
      this.bottom_shadow._y = Math.round(obj.h - 186);
      this.bottom_shadow._width = obj.w - 51;
      this.left_shadow._height = this.bottom_shadow._y - 46;
      this.top_shadow._width = obj.w - 51;
      this.right_shadow._x = Math.round(this.top_shadow._width + this.top_shadow._x - 7);
      this.right_shadow._height = this.left_shadow._height;
      this.frame_top_right._x = Math.round(obj.w);
      this.frame_top._x = Math.round(obj.w / 2);
      this.frame_left_mask._width = obj.w / 2;
      this.frame_right_mask._x = Math.round(obj.w / 2);
      this.frame_right_mask._width = obj.w / 2;
      this.frame_right._x = obj.w;
      this.frame_mask._width = obj.w;
      this.frame_mask._height = obj.h - 200;
      this.frame_left_corner._y = Math.round(obj.h - 334);
      this.frame_right_corner._y = Math.round(obj.h - 334);
      this.frame_right_corner._x = Math.round(obj.w);
      this.frame_bottom_middle._x = Math.round(obj.w / 2);
      this.frame_bottom_middle._y = Math.round(obj.h - 168);
      this.exit_btn._x = Math.round(obj.w - 140);
      this.avatarPan._y = Math.round(obj.h - 353);
      this.questInfo_mc._y = Math.round(obj.h - 284);
      this.planshet_btn._y = Math.round(obj.h - 216);
      this.equip_mc._y = Math.round(obj.h - 116);
      this.bag_btn._y = Math.round(obj.h - 275);
      if(this.mainSlotPan.panActivationFlag)
      {
         this.mainSlotPan._y = Math.round(obj.h - 405);
      }
      else
      {
         this.mainSlotPan._y = Math.round(obj.h - 325);
      }
      this.mainSlotPan.propeties();
      this.miniMapPan._x = Math.round(obj.w - 170);
      this.miniMapMask._x = Math.round(obj.w - 190);
      var _loc3_ = -5;
      this.effectsPan._y = obj.h - 590 - _loc3_;
      this.fxPanMask._y = obj.h - 600 - _loc3_;
      this.showhideFX_Btn._y = obj.h - 550;
      this.showhideFX_back._y = obj.h - 670;
      this.leaveLocation_mc._x = Math.round((obj.w - this.leaveLocation_mc._width) / 2);
      this.weapon_bottom._y = Math.round(obj.h - 191);
      this.weaponMask._y = Math.round(obj.h - 350);
      this.exitLoc_btn._x = Math.round((obj.w - this.exitLoc_btn._width) / 2);
      this.apBar._x = Math.round((obj.w - this.apBar.back._width) / 2);
      this.topWindow._x = Math.round((obj.w - this.topWindow._width) / 2);
      this.locationFrame.setSize(obj.w - 64,obj.h - 237);
      this.displayLoc.setViewArea(obj.w,obj.h);
   }
   function initHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.addFilter("location");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.EQUIPMENT,this,this.equip_key);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.PERS_INFO,this,this.char_key);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CHANGE_WORLD,this,this.toGlobal);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CENTER_ON_CHAR,this,this.centerChar);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.SETTINGS,this,this.openSettingsInterface);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.KEY_PRESS,this,this.keyPress_func);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.KEY_RELEASE,this,this.keyRelease_func);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FIRE_MODE0,this.mainSlotPan,this.mainSlotPan.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FIRE_MODE1,this.mainSlotPan,this.mainSlotPan.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.FIRE_MODE2,this.mainSlotPan,this.mainSlotPan.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.RELOAD,this,this.reload_func);
   }
   function killHotKey()
   {
      lol.core.SceneShifter.hotKeyManager.removeFilter("location");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.EQUIPMENT,this,this.equip_key);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.PERS_INFO,this,this.char_key);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CHANGE_WORLD,this,this.toGlobal);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CENTER_ON_CHAR,this,this.centerChar);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.SETTINGS,this,this.openSettingsInterface);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.KEY_PRESS,this,this.keyPress_func);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.KEY_RELEASE,this,this.keyRelease_func);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FIRE_MODE0,this.mainSlotPan,this.mainSlotPan.selectFuncKey1);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FIRE_MODE1,this.mainSlotPan,this.mainSlotPan.selectFuncKey2);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.FIRE_MODE2,this.mainSlotPan,this.mainSlotPan.selectFuncKey3);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.RELOAD,this,this.reload_func);
   }
   function openCloseSlideWindow(obj)
   {
      var _loc2_ = obj.target.data;
      var _loc4_ = lol.core.SceneShifter.locationScreen;
      var _loc3_;
      if(_loc4_.canLeavelocation || _loc2_ != "clan")
      {
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
      else
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "Ваш персонаж слишком занят";
      }
   }
   function openMc(type)
   {
      var mc = this[type + "_mc"];
      this.curType = type;
      this[type + "Flag"] = true;
      var _loc3_ = lol.core.SceneShifter.locationScreen;
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
   function bagAnimation_key()
   {
      if(!lol.core.SceneShifter._sl.isWindow)
      {
         this.bagAnimation();
      }
      else if(this.bagFlag)
      {
         this.bagFlag = !this.bagFlag;
         lol.core.SceneShifter._sl.closeWinBtn_func();
      }
      else if(this.planshetFlag || this.clanFlag)
      {
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeSlideGroup_bag);
      }
   }
   function closeSlideGroup_bag()
   {
      this.planshetFlag = false;
      this.clanFlag = false;
      lol.core.SceneShifter._sl.removeEventListener("closeSlideGroup",this,this.closeSlideGroup_bag);
      this.bagAnimation();
   }
   function bagAnimation()
   {
      this.bagFlag = !this.bagFlag;
      var _loc2_ = this.bag_mc;
      this.openBag();
   }
   function bagAction()
   {
      this.bagAnimation_key();
   }
   function openBag()
   {
      var mc = this.bag_mc;
      this.dispatchEvent({type:"bagOpen",value:true});
      var _loc3_ = lol.core.SceneShifter.locationScreen;
      var _loc2_ = lol.core.SceneShifter.openNewSlideWindow("equip",_loc3_);
      _loc2_.addEventListener("close",this,this.closeBagWindow);
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
   function closeBag()
   {
      var mc = this.bag_mc;
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
   function closeBagWindow(obj)
   {
      this.closeBag();
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.closeSlideWindow("equip");
      var _loc2_ = lol.core.Master.getInstance().gamer;
      _loc2_.equipment.close();
      obj.target.removeEventListener("close",this,this.closeBagWindow);
   }
   function planshetAnimation_key()
   {
      if(!lol.core.SceneShifter._sl.isWindow)
      {
         this.planshetAnimation();
      }
      else if(this.planshetFlag)
      {
         this.planshetFlag = !this.planshetFlag;
         lol.core.SceneShifter._sl.closeWinBtn_func();
      }
      else if(this.bagFlag || this.clanFlag)
      {
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeSlideGroup_planshet);
      }
   }
   function closeSlideGroup_planshet()
   {
      this.bagFlag = false;
      this.clanFlag = false;
      lol.core.SceneShifter._sl.removeEventListener("closeSlideGroup",this,this.closeSlideGroup_planshet);
      this.planshetAnimation();
   }
   function planshetAnimation()
   {
      this.planshetFlag = !this.planshetFlag;
      this.openPlanshet();
   }
   function planshetAction()
   {
      this.planshetAnimation_key();
   }
   function openPlanshet()
   {
      var mc = this.planshet;
      this.dispatchEvent({type:"planshetOpen",value:true});
      var _loc2_ = lol.core.SceneShifter.locationScreen;
      var _loc3_ = lol.core.SceneShifter.openNewSlideWindow("char",_loc2_);
      _loc3_.addEventListener("close",this,this.closePlanshetWindow);
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
   function closePlanshet()
   {
      var mc = this.planshet;
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
   function closePlanshetWindow(obj)
   {
      this.closePlanshet();
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.closeSlideWindow("char");
      obj.target.removeEventListener("close",this,this.closePlanshetWindow);
   }
   function openClanInterface(obj)
   {
      if(!lol.core.SceneShifter._sl.isWindow)
      {
         this.openClan();
      }
      else if(this.clanFlag)
      {
         this.clanFlag = false;
         lol.core.SceneShifter._sl.closeWinBtn_func();
      }
      else if(this.bagFlag)
      {
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeSlideGroup_clan);
      }
      else if(this.planshetFlag)
      {
         lol.core.SceneShifter._sl.closeWinBtn_func();
         lol.core.SceneShifter._sl.addEventListener("closeSlideGroup",this,this.closeSlideGroup_clan);
      }
   }
   function openClan()
   {
      this.clanFlag = true;
      var _loc2_ = lol.core.SceneShifter.locationScreen;
      var _loc3_ = lol.core.SceneShifter.openNewSlideWindow("clan",_loc2_);
      _loc3_.addEventListener("close",this,this.closeClanWindow);
   }
   function closeSlideGroup_clan()
   {
      this.bagFlag = false;
      this.planshetFlag = false;
      lol.core.SceneShifter._sl.removeEventListener("closeSlideGroup",this,this.closeSlideGroup_clan);
      this.openClan();
   }
   function closeClanWindow(obj)
   {
      obj.target.removeEventListener("close",this,this.closeClanWindow);
      lol.core.SceneShifter.closeSlideWindow("clan");
   }
   function locLoaded(obj)
   {
      var _loc2_ = 0;
      var _loc4_ = this.currentLocation.locationGrid.gridW * lol.core.location.LocationGrid.cellW;
      var _loc3_ = this.currentLocation.locationGrid.gridH * lol.core.location.LocationGrid.cellH;
      this.doLater("SSresizeStage");
      this.locationFrame.setScrollArea(0,- _loc2_,_loc4_,_loc3_ + _loc2_);
   }
   function SSresizeStage()
   {
      lol.core.SceneShifter._ref.setMCSize();
   }
   function warState(obj)
   {
      this.battleMode(this.currentLocation.warStatus);
   }
   function battleMode(ws)
   {
      if(ws)
      {
         this.enabledExitLoc = false;
         this.exitLoc_btn.enabled = false;
         this.apBar.open();
      }
      else
      {
         this.battleLoc_btn.label = "Start battle";
         this.enabledExitLoc = true;
         this.apBar.close();
         this.exitLoc_btn.enabled = !this.currentLocation.isSubLocation;
         this.deleteTimerLeaveLocation();
      }
   }
   function chWAck(obj)
   {
      this.toGMEnabled = true;
   }
   function toGlobal()
   {
      if(this.enabledExitLoc && this.toGMEnabled)
      {
         this.toGMEnabled = false;
         lol.core.Master.getInstance().changeWorld();
      }
   }
   function centerChar()
   {
      var _loc3_ = this.master.gamer;
      var _loc4_ = _loc3_.walker.numPos;
      var _loc2_ = this.currentLocation.getCellFromNumber(_loc4_);
      var _loc7_ = _loc2_.rx;
      var _loc6_ = _loc2_.ry;
      var _loc8_ = lol.core.location.LocDeclaration.abstractToReal({x:_loc2_.rx,y:_loc2_.ry});
      this.centerPoint({point:_loc8_,how:true});
   }
   function centerPoint(obj)
   {
      var _loc5_ = obj.how;
      var _loc3_ = obj.point.x;
      var _loc2_ = obj.point.y;
      if(_loc5_)
      {
         this.locationFrame.slideToCenter(_loc3_,_loc2_);
      }
      else
      {
         this.locationFrame.centerPoint(_loc3_,_loc2_);
      }
   }
   function actionPoints(obj)
   {
      var _loc3_ = this.master.gamer.apManager.ap;
      var _loc2_ = this.master.gamer.apManager.maxAP;
      this.apBar.showAP(_loc3_,_loc2_);
   }
   function get currentLocation()
   {
      return this.master.currentLocation;
   }
   function kill()
   {
      this.tt.Clear();
      this.help_mc.kill();
      this.bag_btn.removeEventListener(this.bag_btn.RELEAS_EVENT,this,this.openCloseSlideWindow);
      this.planshet_btn.removeEventListener(this.planshet_btn.RELEAS_EVENT,this,this.openCloseSlideWindow);
      this.avatarPan.char_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.master.gamer.removeEventListener("uiUpd",this);
      this.killHotKey();
      this.inventary_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.charInfo_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.settings_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openSettingsInterface);
      this.clan_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.mail_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.trophy_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openCloseSlideWindow);
      this.help_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.openHelp);
      this.goldToAfro_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goldToAfro);
      this.gold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToUserPage);
      this.forum_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.goToForum);
      this.copyLog_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
      this.copyHash_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyHash);
      lol.core.mail.MailInspector.getInstance().removeEventListener(lol.core.mail.MailEvent.UPDATE_INBOX,this,this.checkNewLetter);
      lol.core.mail.MailInspector.getInstance().removeEventListener(lol.core.mail.MailEvent.UPDATE_LETTER,this,this.checkNewLetter);
      this.mainSlotPan.kill();
      this.miniMapPan.kill();
      this.effectsPan.kill();
      lol.core.SceneShifter.hintManager.killHint();
      lol.core.quests.QuestInspector.getInstance().removeEventListener(lol.core.quests.Quest.COMPLETE,this,this.questComplete);
      lol.core.quests.QuestInspector.getInstance().removeEventListener(lol.core.quests.Quest.KILL_MOB,this,this.killMob);
      lol.core.quests.QuestInspector.getInstance().removeEventListener(lol.core.quests.Quest.GET_OBJECT,this,this.getObject);
      lol.core.quests.QuestInspector.getInstance().removeEventListener(lol.core.quests.Quest.DEL_OBJECT,this,this.delObject);
      this.currentLocation.removeEventListener("addPlayer",this);
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("LGUI_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
   function onSpriteOver(obj)
   {
      var _loc3_ = obj.flared.target.id;
      var _loc2_;
      var _loc4_;
      if(_loc3_)
      {
         _loc2_ = this.master.getPlayer(_loc3_);
         if(!(_loc2_ instanceof lol.core.player.NPC))
         {
            if(_loc2_ instanceof lol.core.player.Player)
            {
               _loc4_ = _loc2_.equipment.primaryItem;
               this.attachPrimaryItem(_loc4_);
            }
         }
      }
   }
   function onSpriteOut(obj)
   {
      this.attachPrimaryItem();
   }
   function attachPrimaryItem(item)
   {
      this.primaryItem_mc.removeMovieClip();
      var _loc2_;
      if(item)
      {
         this.primaryItem_mc = this.attachMovie("primaryItemCont_mc","primaryItem_mc",this.getNextHighestDepth());
         _loc2_ = this.primaryItem_mc.itemCont;
         _loc2_.attachIconEnabled = true;
         _loc2_.attachBackEnabled = true;
         _loc2_.fireArm_mod_mc._visible = false;
         _loc2_.blockFlag = true;
         this.doLater(_loc2_,"attachIcon",[item]);
         this.primaryItem_mc._x = lol.core.SceneShifter._ref.W - 220;
         this.primaryItem_mc._y = lol.core.SceneShifter._ref.H - lol.services.ChatPan.DEFAULT_H - 140;
      }
   }
   function keyPress_func(obj)
   {
      var _loc2_;
      var _loc4_;
      var _loc3_;
      if(lol.core.SceneShifter.hotKeyManager.enabled && lol.core.SceneShifter.hotKeyManager.checkFilter("location"))
      {
         _loc2_ = obj.code;
         _loc4_ = 50;
         _loc3_ = lol.core.SceneShifter.hotKeyManager.getHotKeyArr();
         this.codeHandScroll = _loc3_[lol.services.HotKeyEvent.HAND_SCROLL].keyCode[0];
         this.codeUP = _loc3_[lol.services.HotKeyEvent.SCROLL_UP].keyCode[0];
         this.codeDown = _loc3_[lol.services.HotKeyEvent.SCROLL_DOWN].keyCode[0];
         this.codeLeft = _loc3_[lol.services.HotKeyEvent.SCROLL_LEFT].keyCode[0];
         this.codeRight = _loc3_[lol.services.HotKeyEvent.SCROLL_RIGHT].keyCode[0];
         this.codeUP1 = _loc3_[lol.services.HotKeyEvent.SCROLL_UP].keyCode1[0];
         this.codeDown1 = _loc3_[lol.services.HotKeyEvent.SCROLL_DOWN].keyCode1[0];
         this.codeLeft1 = _loc3_[lol.services.HotKeyEvent.SCROLL_LEFT].keyCode1[0];
         this.codeRight1 = _loc3_[lol.services.HotKeyEvent.SCROLL_RIGHT].keyCode1[0];
         if(_loc2_ == this.codeHandScroll && !this.locationFrame.handDrag)
         {
            this.locationFrame.setHandScroll(true);
         }
         if(_loc2_ == this.codeUP || _loc2_ == this.codeUP1 && !this.pressUp && !this.pressDown)
         {
            this.pressUp = true;
            this.startMove();
         }
         if(_loc2_ == this.codeDown || _loc2_ == this.codeDown1 && !this.pressUp && !this.pressDown)
         {
            this.pressDown = true;
            this.startMove();
         }
         if(_loc2_ == this.codeLeft || _loc2_ == this.codeLeft1 && !this.pressLeft && !this.pressRight)
         {
            this.pressLeft = true;
            this.startMove();
         }
         if(_loc2_ == this.codeRight || _loc2_ == this.codeRight1 && !this.pressLeft && !this.pressRight)
         {
            this.pressRight = true;
            this.startMove();
         }
      }
   }
   function keyRelease_func(obj)
   {
      var _loc2_ = obj.code;
      if(_loc2_ == this.codeHandScroll && this.locationFrame.handDrag)
      {
         this.locationFrame.setHandScroll(false);
      }
      if(_loc2_ == this.codeUP || _loc2_ == this.codeUP1)
      {
         this.pressUp = false;
      }
      if(_loc2_ == this.codeDown || _loc2_ == this.codeDown1)
      {
         this.pressDown = false;
      }
      if(_loc2_ == this.codeLeft || _loc2_ == this.codeLeft1)
      {
         this.pressLeft = false;
      }
      if(_loc2_ == this.codeRight || _loc2_ == this.codeRight1)
      {
         this.pressRight = false;
      }
   }
   function startMove()
   {
      if(!this.onEnterFrame)
      {
         this.onEnterFrame = function()
         {
            var _loc3_ = this.locationFrame;
            var _loc4_ = this.pressUp;
            var _loc5_ = this.pressDown;
            var _loc7_ = this.pressRight;
            var _loc6_ = this.pressLeft;
            var _loc2_ = this.acseleration;
            if(_loc4_)
            {
               this.curStepY += _loc2_;
               if(this.curStepY >= this.maxStep)
               {
                  this.curStepY = this.maxStep;
               }
            }
            if(_loc5_)
            {
               this.curStepY -= _loc2_;
               if(this.curStepY <= - this.maxStep)
               {
                  this.curStepY = - this.maxStep;
               }
            }
            var _loc8_;
            if(!_loc4_ && !_loc5_)
            {
               _loc8_ = this.curStepY != 0 ? Math.abs(this.curStepY) / this.curStepY : 0;
               this.curStepY -= _loc8_ * _loc2_;
               if(_loc8_ > 0 && this.curStepY <= 0 || _loc8_ < 0 && this.curStepY >= 0)
               {
                  this.curStepY = 0;
               }
            }
            if(_loc7_)
            {
               this.curStepX -= _loc2_;
               if(this.curStepX <= - this.maxStep)
               {
                  this.curStepX = - this.maxStep;
               }
            }
            if(_loc6_)
            {
               this.curStepX += _loc2_;
               if(this.curStepX >= this.maxStep)
               {
                  this.curStepX = this.maxStep;
               }
            }
            if(!_loc7_ && !_loc6_)
            {
               _loc8_ = this.curStepX != 0 ? Math.abs(this.curStepX) / this.curStepX : 0;
               this.curStepX -= _loc8_ * _loc2_;
               if(_loc8_ > 0 && this.curStepX <= 0 || _loc8_ < 0 && this.curStepX >= 0)
               {
                  this.curStepX = 0;
               }
            }
            _loc3_.scrollY(this.curStepY);
            _loc3_.scrollX(this.curStepX);
            _loc3_.dispatchPosition();
            var _loc9_ = _loc3_.xPosition;
            var _loc10_ = _loc3_.yPosition;
            if(_loc6_ && _loc9_ == 0)
            {
               this.pressLeft = false;
               this.curStepX = 0;
            }
            if(_loc7_ && _loc9_ == 100)
            {
               this.pressRight = false;
               this.curStepX = 0;
            }
            if(_loc4_ && _loc10_ == 0)
            {
               this.pressUp = false;
               this.curStepY = 0;
            }
            if(_loc5_ && _loc10_ == 100)
            {
               this.pressRight = false;
               this.curStepY = 0;
            }
            if(!_loc4_ && !_loc5_ && !_loc6_ && !_loc7_ && this.curStepX == 0 && this.curStepY == 0)
            {
               delete this.onEnterFrame;
            }
         };
      }
   }
   function position(obj)
   {
      var _loc3_ = obj.width;
      var _loc2_ = obj.height;
      this.displayLoc.setViewArea(_loc3_,_loc2_);
   }
   function set flagSceneEnabled(value)
   {
      this._flagSceneEnabled = value;
      this.locationFrame.middleMouseButton(!this._flagSceneEnabled);
   }
   function uiUpd()
   {
      this.updMoney();
   }
   function updMoney()
   {
      var _loc2_ = lol.core.Master.getInstance();
      this.moneyPanAfro = this.frame_top.moneyPanAfro;
      this.moneyPanGold = this.frame_top.moneyPanGold;
      this.moneyPanAfro.type = "afro";
      this.moneyPanAfro.value = _loc2_.gamer.attributes.afro;
      this.moneyPanGold.type = "gold";
      this.moneyPanGold.value = _loc2_.gamer.attributes.gold;
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
            break;
         }
         this.newMailAlert_mc._visible = false;
         _loc2_ = _loc2_ + 1;
      }
   }
   function killMob(obj)
   {
      var _loc2_ = obj.changes;
      var _loc3_ = "Убит персонаж для задания &lt;" + this.parseQuestName(_loc2_.questName) + "&gt; (" + _loc2_.currNum + " из " + _loc2_.num + ")";
      var _loc4_;
      if(_loc2_.questName)
      {
         _loc4_ = lol.core.SceneShifter.newServiceMessage(_loc3_,lol.gpui.ServiceMessage.QUEST_MESSAGE);
      }
   }
   function getObject(obj)
   {
      var _loc2_ = obj.changes;
      var _loc3_ = " предмет &lt;" + _loc2_.itemName + "&gt; для задания &lt;" + this.parseQuestName(_loc2_.questName) + "&gt;<BR>(" + _loc2_.currNum + " из " + _loc2_.num + ")";
      if(_loc2_.lost)
      {
         _loc3_ = "Потерян" + _loc3_;
      }
      else
      {
         _loc3_ = "Найден" + _loc3_;
      }
      var _loc4_;
      if(_loc2_.itemName && _loc2_.questName)
      {
         _loc4_ = lol.core.SceneShifter.newServiceMessage(_loc3_,lol.gpui.ServiceMessage.QUEST_MESSAGE);
      }
   }
   function delObject(obj)
   {
      var _loc2_ = obj.changes;
      var _loc3_ = "Получен предмет &lt;" + _loc2_.itemName + "&gt; для задания &lt;" + this.parseQuestName(_loc2_.questName) + "&gt;";
      var _loc4_;
      if(_loc2_.itemName && _loc2_.questName)
      {
         _loc4_ = lol.core.SceneShifter.newServiceMessage(_loc3_,lol.gpui.ServiceMessage.QUEST_MESSAGE);
      }
   }
   function questComplete(obj)
   {
      var _loc2_ = "Задание &lt;" + this.parseQuestName(obj.questName) + "&gt; выполнено";
      var _loc4_;
      if(obj.questName)
      {
         _loc4_ = lol.core.SceneShifter.newServiceMessage(_loc2_,lol.gpui.ServiceMessage.QUEST_MESSAGE_COMPLETE);
      }
   }
   function parseQuestName(str)
   {
      var _loc1_ = lol.utils.ParseString.replaceAll(str,"\\","");
      _loc1_ = lol.utils.ParseString.replaceAll(_loc1_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
      return _loc1_;
   }
   function addPlayer(obj)
   {
      if(this.traderMessage_bool)
      {
         this.checkTrader();
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
   function checkPlayerAfterLoading()
   {
      var _loc6_ = this.master.gamer;
      var _loc4_;
      var _loc3_;
      var _loc2_;
      if(this.gamer_level > 3 && this.gamer_gold < 1000)
      {
         if(this.traderMessage_bool && lol.core.SceneShifter.serviceMessageManager.tradeLocation_bool)
         {
            _loc4_ = this.currentLocation.playerList;
            for(var _loc5_ in _loc4_)
            {
               _loc3_ = _loc4_[_loc5_];
               if(_loc3_ instanceof lol.core.player.Trader)
               {
                  _loc2_ = lol.MessageString.GOLD_MESSAGE_TRADE_LOCATION;
                  this.showGoldMessage(_loc2_);
                  this.traderMessage_bool = false;
                  lol.core.SceneShifter.serviceMessageManager.startTimeout("tradeLocation_bool");
                  break;
               }
            }
         }
      }
   }
   function loadedLevel(obj)
   {
      var _loc2_ = this.master.gamer;
      this.gamer_level = _loc2_.attributes.getLevel();
      _loc2_.attributes.removeEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.loadedLevel);
      if(this.gamer_gold != -1)
      {
         this.checkPlayerAfterLoading();
      }
   }
   function loadedGold(obj)
   {
      var _loc2_ = this.master.gamer;
      this.gamer_gold = _loc2_.attributes.gold;
      _loc2_.removeEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.loadedGold);
      if(this.gamer_level != -1)
      {
         this.checkPlayerAfterLoading();
      }
   }
   function checkTrader()
   {
      var _loc2_ = this.master.gamer;
      _loc2_.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.loadedLevel);
      _loc2_.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.loadedGold);
   }
   function checkBagOverload()
   {
      var _loc2_;
      if(this.bagOverload_bool && lol.core.SceneShifter.serviceMessageManager.bagOverload_bool)
      {
         _loc2_ = lol.MessageString.GOLD_MESSAGE_BAG_OVERLOAD;
         this.showGoldMessage(_loc2_);
         lol.core.SceneShifter.serviceMessageManager.startTimeout("bagOverload_bool");
      }
   }
   function showGoldMessage(str)
   {
      this.newServiceMessage = lol.core.SceneShifter.newServiceMessage(str,lol.gpui.ServiceMessage.GOLD_MESSAGE);
      this.newServiceMessage.addEventListener(lol.gpui.ServiceMessage.ON_RELEASE,this,this.addGold);
   }
   function addGold(obj)
   {
      obj.target.removeEventListener(lol.gpui.ServiceMessage.ON_RELEASE,this,this.addGold);
      this.goToUserPage();
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
   function exitGame()
   {
      var _loc1_;
      _loc1_ = lol.server.XMLConnection.getInstance();
      _loc1_.close();
      lol.core.SceneShifter.enterSceneClearPassword();
   }
   function startExitTimer()
   {
      if(!this.timer_mc)
      {
         this.timer_mc = this.createEmptyMovieClip("timer_mc",this.getNextHighestDepth());
         this.tf = new TextFormat();
         this.tf.bold = true;
      }
      this.dispatchEvent({type:"exitEnabled",value:false});
      delete this.timer_mc.onEnterFrame;
      this.startTime = getTimer();
      this.canLeavelocation = false;
      this.leaveLocation_mc._visible = true;
      this.exitTime = lol.core.GConstatns.getLeaveCombatLocationPause();
      this.timer_mc.onEnterFrame = mx.utils.Delegate.create(this,this.exitTimer);
   }
   function exitTimer()
   {
      var _loc3_ = Math.floor((getTimer() - this.startTime) / 1000);
      var _loc2_ = lol.core.GConstatns.getLeaveCombatLocationPause() - _loc3_;
      this.exitTime = _loc2_;
      this.leaveLocation_mc.leaveLocation_txt.text = "Выход возможен через " + _loc2_ + " сек.";
      this.leaveLocation_mc.leaveLocation_txt.setTextFormat(this.tf);
      if(_loc2_ <= 0)
      {
         this.deleteTimerLeaveLocation();
      }
   }
   function deleteTimerLeaveLocation()
   {
      this.dispatchEvent({type:"exitEnabled",value:true});
      this.leaveLocation_mc.leaveLocation_txt.text = "";
      this.leaveLocation_mc._visible = false;
      delete this.timer_mc.onEnterFrame;
      this.canLeavelocation = true;
      this.exitTime = 0;
   }
   function startBGPrepareTimer(obj)
   {
      var _loc2_ = obj.data;
      trace("par = " + _loc2_);
      if(!this.timer_mc)
      {
         this.timer_mc = this.createEmptyMovieClip("timer_mc",this.getNextHighestDepth());
         this.tf = new TextFormat();
         this.tf.bold = true;
      }
      delete this.timer_mc.onEnterFrame;
      this.startBGPrepareTime = getTimer();
      this.leaveLocation_mc._visible = true;
      this.totalBGPrepareTime = _loc2_;
      this.timer_mc.onEnterFrame = mx.utils.Delegate.create(this,this.BGPrepareTimer);
      this.exitTime = _loc2_;
   }
   function BGPrepareTimer()
   {
      var _loc3_ = Math.floor((getTimer() - this.startBGPrepareTime) / 1000);
      var _loc2_ = this.totalBGPrepareTime - _loc3_;
      this.exitTime = _loc2_;
      this.leaveLocation_mc.leaveLocation_txt.text = "Начало сражения через " + _loc2_ + " сек.";
      this.leaveLocation_mc.leaveLocation_txt.setTextFormat(this.tf);
      if(_loc2_ <= 0)
      {
         this.deleteTimerBGPrepare();
      }
   }
   function deleteTimerBGPrepare()
   {
      this.dispatchEvent({type:"exitEnabled",value:true});
      this.leaveLocation_mc.leaveLocation_txt.text = "";
      this.leaveLocation_mc._visible = false;
      delete this.timer_mc.onEnterFrame;
      this.exitTime = 0;
   }
   function panActivation()
   {
      this.effectsPan.panActivation();
   }
}
