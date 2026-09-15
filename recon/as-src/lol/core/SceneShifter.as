class lol.core.SceneShifter
{
   var BG_Statistic_Window;
   var H;
   var UIPanels;
   var W;
   var XMC;
   var dispatchEvent;
   var login;
   var resizeObj;
   static var _sl;
   static var chat;
   static var clientTest;
   static var contextMenuManager;
   static var currFadeIn_Mc;
   static var currFadeOut_Mc;
   static var deleteCurrentScene;
   static var enterWinFrame;
   static var fadeIn_mc;
   static var fadeOutCurrentScene;
   static var fadeOut_mc;
   static var gamehelpMessageManager;
   static var gmapScreen;
   static var hintManager;
   static var introScreen;
   static var linkAlert;
   static var linkGame;
   static var linkHint;
   static var linkWindow;
   static var locationScreen;
   static var serviceMessageManager;
   static var tempChatShift;
   static var refDelegate = new mx.utils.Delegate();
   static var main = _root;
   static var mainDepth = 3;
   static var _ref = new lol.core.SceneShifter();
   static var hotKeyManager = new lol.services.HotKeyManager();
   static var stageShift = 0;
   static var firstGame = false;
   var addGoldTooltip_bool = true;
   var minW = 950;
   var minH = 650;
   var maxW = 1280;
   var maxH = 1024;
   var minScreenH = 360;
   var flagSceneEnabled = false;
   var leaveClan = false;
   var clanInviteParam = true;
   function SceneShifter()
   {
      lol.events.LEventDispatcher.initialize(this);
      _root._focusrect = false;
      this.createUIPanels();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("onClose",this);
      this.resizeObj = new Object();
      this.resizeObj.onResize = mx.utils.Delegate.create(this,this.setMCSize);
      Stage.addListener(this.resizeObj);
      var _loc3_ = new lol.utils.Timeout(this,this.addListenerCopyLog,1000);
   }
   function addListenerCopyLog()
   {
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.COPY_LOG,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
   }
   static function init()
   {
      var _loc4_ = lol.core.SceneShifter.main.createEmptyMovieClip("gameInterfaces",0);
      var _loc3_ = lol.core.SceneShifter.main.createEmptyMovieClip("atherWin",1);
      var _loc2_ = lol.core.SceneShifter.main.createEmptyMovieClip("alertWin",2);
      var _loc1_ = lol.core.SceneShifter.main.createEmptyMovieClip("hint_mc",3);
      lol.core.SceneShifter.linkGame = _loc4_;
      lol.core.SceneShifter.linkWindow = _loc3_;
      lol.core.SceneShifter.linkAlert = _loc2_;
      lol.core.SceneShifter.linkHint = _loc1_;
      lol.core.SceneShifter.hintManager = new lol.gpui.HintManager();
      lol.core.SceneShifter.serviceMessageManager = new lol.gpui.ServiceMessageManager();
      lol.core.SceneShifter.contextMenuManager = new lol.gpui.ContextMenuManager();
      lol.core.SceneShifter.clientTest = new lol.services.ClientTest();
      lol.core.SceneShifter._ref.setMCSize();
      lol.gpui.UserSettings.init();
   }
   function setMCSize()
   {
      lol.core.SceneShifter.hintManager.removeAll();
      var _loc3_;
      var _loc2_;
      _loc3_ = Stage.width >= this.maxW ? this.maxW : Stage.width;
      _loc2_ = Stage.height >= this.maxH ? this.maxH : Stage.height;
      _loc3_ = _loc3_ <= this.minW ? this.minW : _loc3_;
      _loc2_ = _loc2_ <= this.minH ? this.minH : _loc2_;
      lol.core.SceneShifter.linkGame._x = Math.round((this.minW - Stage.width) / 2);
      lol.core.SceneShifter.linkGame._y = Math.round((this.minH - Stage.height) / 2);
      lol.core.SceneShifter.linkWindow._x = Math.round(this.minW / 2);
      lol.core.SceneShifter.linkWindow._y = Math.round(this.minH / 2);
      lol.core.SceneShifter.linkAlert._x = Math.round(this.minW / 2);
      lol.core.SceneShifter.linkAlert._y = Math.round(this.minH / 2);
      lol.core.SceneShifter.linkHint._x = Math.round((this.minW - Stage.width) / 2);
      lol.core.SceneShifter.linkHint._y = Math.round((this.minH - Stage.height) / 2);
      lol.core.SceneShifter.enterWinFrame._x = Math.round((Stage.width - 895) / 2);
      lol.core.SceneShifter.enterWinFrame._y = Math.round((Stage.height - 600) / 2);
      if(_loc3_ == this.maxW)
      {
         lol.core.SceneShifter._ref.currentScene._x = Math.round((Stage.width - this.maxW) / 2);
         lol.core.SceneShifter.chat._x = Math.round((Stage.width - this.maxW) / 2 + 20);
      }
      else
      {
         lol.core.SceneShifter._ref.currentScene._x = 0;
         lol.core.SceneShifter.chat._x = 20;
      }
      if(_loc2_ == this.maxH)
      {
         lol.core.SceneShifter._ref.currentScene._y = Math.round((Stage.height - this.maxH) / 2);
         lol.core.SceneShifter.chat._y = Math.round(lol.core.SceneShifter._ref.currentScene._y + this.maxH - 144);
      }
      else
      {
         lol.core.SceneShifter.chat._y = Math.round(_loc2_ - 144);
         lol.core.SceneShifter._ref.currentScene._y = 0;
      }
      lol.core.SceneShifter.tempChatShift = _loc2_ - lol.core.SceneShifter.stageShift - 144 >= this.minScreenH ? lol.core.SceneShifter.stageShift : _loc2_ - this.minScreenH - 144;
      this.W = _loc3_;
      this.H = _loc2_ - lol.core.SceneShifter.tempChatShift;
      this.dispatchEvent({type:"resizeStage",w:this.W,h:this.H});
   }
   function sceneEnabled()
   {
      var _loc2_ = false;
      for(var _loc3_ in lol.core.SceneShifter._ref.UIPanels)
      {
         if(lol.core.SceneShifter._ref.UIPanels[_loc3_].instance && lol.core.SceneShifter._ref.UIPanels[_loc3_].mode)
         {
            _loc2_ = true;
            break;
         }
      }
      if(_loc2_ != this.flagSceneEnabled)
      {
         this.flagSceneEnabled = _loc2_;
         this.dispatchEvent({type:"sceneEnabled",status:this.flagSceneEnabled});
      }
      lol.core.SceneShifter._ref.currentScene.flagSceneEnabled = this.flagSceneEnabled;
   }
   function onClose()
   {
      lol.core.SceneShifter._sl = new lol.gpui.view.SlideWindowContainer();
      lol.core.SceneShifter.removeAllWindow();
      lol.core.mail.MailInspector.getInstance().kill();
   }
   static function removeAllWindow()
   {
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.hintManager.killHint();
      lol.core.SceneShifter.hintManager.removeAll();
      for(var _loc1_ in lol.core.SceneShifter._ref.UIPanels)
      {
         if(lol.core.SceneShifter._ref.UIPanels[_loc1_].instance && lol.core.SceneShifter._ref.UIPanels[_loc1_].cont != "linkAlert")
         {
            lol.core.SceneShifter.closeWindow(_loc1_);
            lol.core.SceneShifter._ref.UIPanels[_loc1_].instance.removeMovieClip();
            delete lol.core.SceneShifter._ref.UIPanels[_loc1_].instance;
         }
      }
   }
   static function enterScene()
   {
      lol.core.battlegrounds.BattleGroundManager.getInstance();
      lol.core.SceneShifter.removeAllWindow();
      lol.core.SceneShifter._sl = new lol.gpui.view.SlideWindowContainer();
      lol.core.SceneShifter.deleteCurrentScene();
      lol.core.SceneShifter.chat.kill();
      lol.core.SceneShifter.chat.removeMovieClip();
      lol.core.SceneShifter.chat = null;
      var _loc1_ = lol.core.clans.ClanInspector.getInstance();
      lol.core.SceneShifter.enterWinFrame = lol.core.SceneShifter.linkGame.attachMovie("enterWinFrame","enterWinFrame",lol.core.SceneShifter.mainDepth + 1);
      lol.core.SceneShifter.enterWinFrame._x = Stage.width / 2 - lol.core.SceneShifter.enterWinFrame._width / 2;
      lol.core.SceneShifter.enterWinFrame._y = Stage.height / 2 - 300;
      lol.core.SceneShifter.openNewSlideWindow("enterWin",lol.core.SceneShifter.enterWinFrame);
      lol.core.SceneShifter.gamehelpMessageManager = lol.gpui.gamehelp.GameHelpMessageManager.getInstance();
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter._removeEnterScene;
   }
   static function enterSceneClearPassword()
   {
      lol.core.SceneShifter.removeAllWindow();
      lol.core.SceneShifter._sl = new lol.gpui.view.SlideWindowContainer();
      lol.core.SceneShifter.deleteCurrentScene();
      lol.core.SceneShifter.chat.kill();
      lol.core.SceneShifter.chat.removeMovieClip();
      lol.core.SceneShifter.chat = null;
      var _loc2_ = lol.core.clans.ClanInspector.getInstance();
      lol.core.SceneShifter.enterWinFrame = lol.core.SceneShifter.linkGame.attachMovie("enterWinFrame","enterWinFrame",lol.core.SceneShifter.mainDepth + 1);
      var _loc1_;
      _loc1_ = SharedObject.getLocal("csettings","/");
      _loc1_.data.login = null;
      _loc1_.data.pass = null;
      _loc1_.data.hash = null;
      _loc1_.flush();
      lol.core.SceneShifter.enterWinFrame._x = Stage.width / 2 - lol.core.SceneShifter.enterWinFrame._width / 2;
      lol.core.SceneShifter.enterWinFrame._y = Stage.height / 2 - 300;
      lol.core.SceneShifter.openNewSlideWindow("enterWin",lol.core.SceneShifter.enterWinFrame);
      lol.core.SceneShifter.gamehelpMessageManager = lol.gpui.gamehelp.GameHelpMessageManager.getInstance();
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter._removeEnterScene;
   }
   static function removeEnterScene()
   {
      lol.core.SceneShifter.fadeInOut(lol.core.SceneShifter.enterWinFrame,false);
      lol.core.SceneShifter.fadeOutCurrentScene = lol.core.SceneShifter._removeEnterScene;
   }
   static function _removeEnterScene()
   {
      var _loc1_ = lol.core.SceneShifter.linkGame.enterWinFrame;
      if(_loc1_)
      {
         lol.core.SceneShifter._sl.isWindow = false;
         _loc1_.removeMovieClip();
         lol.core.SceneShifter.gmapScreen._visible = true;
         lol.core.SceneShifter.locationScreen._visible = true;
      }
      else
      {
         lol.core.SceneShifter.gmapScreen._visible = true;
         lol.core.SceneShifter.locationScreen._visible = true;
      }
   }
   static function fadeInOut(mc, fadeIn)
   {
      if(!lol.core.SceneShifter.fadeIn_mc)
      {
         lol.core.SceneShifter.fadeIn_mc = lol.core.SceneShifter.linkGame.createEmptyMovieClip("fadeIn_mc",lol.core.SceneShifter.linkGame.getNextHighestDepth());
      }
      if(!lol.core.SceneShifter.fadeOut_mc)
      {
         lol.core.SceneShifter.fadeOut_mc = lol.core.SceneShifter.linkGame.createEmptyMovieClip("fadeOut_mc",lol.core.SceneShifter.linkGame.getNextHighestDepth());
      }
      if(fadeIn)
      {
         delete lol.core.SceneShifter.fadeIn_mc.onEnterFrame;
         lol.core.SceneShifter.currFadeIn_Mc = mc;
         lol.core.SceneShifter.currFadeIn_Mc._alpha = 0;
         lol.core.SceneShifter.fadeIn_mc.onEnterFrame = mx.utils.Delegate.create(lol.core.SceneShifter,lol.core.SceneShifter._fadeIn);
      }
      else
      {
         delete lol.core.SceneShifter.fadeOut_mc.onEnterFrame;
         lol.core.SceneShifter.currFadeOut_Mc = mc;
         lol.core.SceneShifter.currFadeOut_Mc._alpha = 100;
         lol.core.SceneShifter.fadeOut_mc.onEnterFrame = mx.utils.Delegate.create(lol.core.SceneShifter,lol.core.SceneShifter._fadeOut);
      }
   }
   static function _fadeIn()
   {
      if(lol.core.SceneShifter.currFadeIn_Mc._alpha < 100)
      {
         lol.core.SceneShifter.currFadeIn_Mc._alpha += 20;
      }
      else
      {
         lol.core.SceneShifter.currFadeIn_Mc._alpha = 100;
         delete lol.core.SceneShifter.fadeIn_mc.onEnterFrame;
      }
   }
   static function _fadeOut()
   {
      if(lol.core.SceneShifter.currFadeOut_Mc._alpha > 0)
      {
         lol.core.SceneShifter.currFadeOut_Mc._alpha -= 20;
      }
      else
      {
         lol.core.SceneShifter.currFadeOut_Mc._alpha = 0;
         lol.core.SceneShifter.fadeOutCurrentScene();
         delete lol.core.SceneShifter.fadeOut_mc.onEnterFrame;
      }
   }
   static function gmapScene()
   {
      lol.core.SceneShifter._sl.isWindow = false;
      lol.core.SceneShifter.deleteCurrentScene();
      var _loc2_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.__gmapScene,100);
      var _loc1_ = lol.core.Master.getInstance();
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter._removeGMapScene;
      lol.core.SceneShifter.createChat();
   }
   static function __gmapScene()
   {
      lol.core.SceneShifter.gmapScreen = lol.core.SceneShifter.linkGame.attachMovie("globalMapPanel","gm",lol.core.SceneShifter.mainDepth);
      lol.core.SceneShifter._ref.currentScene = lol.core.SceneShifter.gmapScreen;
   }
   static function removeGMapScene()
   {
      lol.core.SceneShifter.fadeOutCurrentScene = lol.core.SceneShifter._removeGMapScene;
      lol.core.SceneShifter.fadeInOut(lol.core.SceneShifter.gmapScreen,false);
   }
   static function _removeGMapScene()
   {
      lol.core.SceneShifter.gmapScreen.kill();
      lol.core.SceneShifter.gmapScreen.removeMovieClip();
      delete lol.core.SceneShifter.gmapScreen;
      lol.core.SceneShifter.removeAllWindow();
   }
   static function locationScene()
   {
      lol.core.SceneShifter._sl.isWindow = false;
      lol.core.SceneShifter.createChat();
      lol.core.SceneShifter.deleteCurrentScene();
      lol.core.SceneShifter.locationScreen = lol.core.SceneShifter.linkGame.attachMovie("locationPanel","lp",lol.core.SceneShifter.mainDepth);
      lol.core.SceneShifter._ref.currentScene = lol.core.SceneShifter.locationScreen;
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter._removeLocationScene;
      lol.core.SceneShifter.createChat();
   }
   static function removeLocationScene()
   {
      lol.core.SceneShifter.fadeOutCurrentScene = lol.core.SceneShifter._removeLocationScene;
      lol.core.SceneShifter.fadeInOut(lol.core.SceneShifter.locationScreen,false);
   }
   static function _removeLocationScene()
   {
      lol.core.SceneShifter.locationScreen.displayLoc.kill();
      lol.core.SceneShifter.locationScreen.kill();
      lol.core.SceneShifter.locationScreen.removeMovieClip();
      delete lol.core.SceneShifter.locationScreen;
      lol.core.SceneShifter.removeAllWindow();
   }
   static function showVisavisAvatar(id)
   {
      lol.core.SceneShifter._ref.visavisAvatar.removeMovieClip();
      var _loc1_;
      if(id)
      {
         _loc1_ = lol.core.SceneShifter.locationScreen;
         lol.core.SceneShifter._ref.visavisAvatar = _loc1_.attachMovie("actionBar","actionBar",_loc1_.getNextHighestDepth());
         lol.core.SceneShifter._ref.visavisAvatar.init(id,true,true);
         return lol.core.SceneShifter._ref.visavisAvatar;
      }
   }
   static function createChat()
   {
      var _loc1_;
      if(!lol.core.SceneShifter.chat)
      {
         lol.core.SceneShifter.chat = lol.core.SceneShifter.linkGame.attachMovie("chat","chat",0);
         _loc1_ = !lol.core.SceneShifter.locationScreen ? lol.core.SceneShifter.gmapScreen : lol.core.SceneShifter.locationScreen;
         lol.core.SceneShifter.chat._y = Stage.height - 144;
         lol.core.SceneShifter.chat._x = 20;
      }
      else
      {
         lol.core.SceneShifter.chat.initUsers();
      }
   }
   function createUIPanels()
   {
      this.UIPanels = new Array();
      this.UIPanels.spec = {linkID:"specInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.barter = {linkID:"barterInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.trade = {linkID:"tradeInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.upgrade = {linkID:"upgradeInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.repair = {linkID:"repairInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.bank = {linkID:"bankInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.regTrophy = {linkID:"regTrophyInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.loot = {linkID:"lootInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.transRent = {linkID:"transRentInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.inspect = {linkID:"inspectInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.auction = {linkID:"auctionInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.auctionMyLots = {linkID:"auctionMyLotsInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.goldToAfro = {linkID:"goldToAfroInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.feedBack = {linkID:"feedBackInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.quests = {linkID:"questInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.editLabel = {linkID:"editLabelPanel",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.exitLoc = {linkID:"exitLocationPanel",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.query = {linkID:"dialoguePan",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.alert = {linkID:"alertPan",group:false,mode:true,closeBtn:false,drag:true,cont:"linkAlert"};
      this.UIPanels.queryWithCheckBox = {linkID:"dialoguePanWithCheckBox",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.queryDeleteItem = {linkID:"dialoguePanDeleteItem",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.queryTradeItem = {linkID:"dialoguePanTradeItem",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.helpVideoLessons = {linkID:"helpVideoLessons",group:false,mode:true,closeBtn:true,drag:false,cont:"linkWindow"};
      this.UIPanels.loadLoc = {linkID:"preloaderPan",group:false,mode:true,closeBtn:false,drag:false,cont:"linkWindow"};
      this.UIPanels["default"] = {linkID:"inWork"};
      this.UIPanels.annotation = {linkID:"annotation",group:true,mode:false,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.equip = {linkID:["equipInterface"],closeBtn:true,mode:true,drag:false};
      this.UIPanels.char = {linkID:["charInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.clan = {linkID:["clanInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.questInfo = {linkID:["questInfoInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.mail = {linkID:["mailInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.trophy = {linkID:["trophyInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.battlegrounds = {linkID:["bgInterface"],closeBtn:true,mode:true,drag:false,prop:{span:40}};
      this.UIPanels.bg_statistic = {linkID:"bgStatistic",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.skills = {linkID:"charPanel",group:false,mode:false,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.slideWin = {linkID:["testWindow0","testWindow1","testWindow2"],mode:false,drag:true};
      this.UIPanels.enterWin = {linkID:["connectionPan","persGenPanel"],mode:false,drag:false};
      this.UIPanels.persGen = {linkID:["persGenPanel"],mode:false,drag:false};
      this.UIPanels.settings = {linkID:"settingsInterface",group:false,mode:true,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.topQuery = {linkID:"topQuery",group:false,mode:true,closeBtn:false,drag:false,cont:"linkWindow"};
      this.UIPanels.topAlert = {linkID:"topAlert",group:false,mode:true,closeBtn:false,drag:false,cont:"linkWindow"};
      this.UIPanels.topInfo = {linkID:"topInfo",group:false,mode:true,closeBtn:false,drag:false,cont:"linkAlert"};
      this.UIPanels.exchange = {linkID:"exchangePan",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.regeneration = {linkID:"regenerationInterface",group:false,mode:true,closeBtn:false,drag:true,cont:"linkWindow"};
      this.UIPanels.support = {linkID:"supportInterface",group:false,mode:false,closeBtn:true,drag:true,cont:"linkWindow"};
      this.UIPanels.game_hint = {linkID:"GameHelpWindow",group:false,mode:false,closeBtn:false,drag:true,cont:"linkWindow"};
   }
   static function openNewSlideWindow(win, cont)
   {
      var _loc6_;
      var _loc2_;
      var _loc1_;
      var _loc7_;
      var _loc4_;
      var _loc3_;
      var _loc8_;
      if(!lol.core.SceneShifter._sl.isWindow)
      {
         _loc6_ = lol.core.SceneShifter._sl;
         _loc2_ = !lol.core.SceneShifter._ref.UIPanels[win] ? "default" : win;
         _loc1_ = lol.core.SceneShifter._ref.UIPanels[_loc2_];
         _loc7_ = _loc1_.mode;
         _loc4_ = _loc1_.prop;
         _loc1_.instance = _loc1_;
         if(_loc7_)
         {
            _loc3_ = cont.winContainer.getNextHighestDepth();
            _loc8_ = cont.mode_mc.attachMovie("modeBackground","modeBackground" + _loc3_,_loc3_);
            _loc1_.modeLink = _loc8_;
            lol.core.SceneShifter._ref.sceneEnabled();
         }
         lol.core.SceneShifter.newInterfaceGameHelpMessage(win);
         lol.core.SceneShifter._sl.newGroupWindow(_loc1_,_loc2_,cont,_loc4_);
         lol.core.SceneShifter._sl.isWindow = true;
         return _loc6_;
      }
   }
   static function openSlideWindow(win)
   {
      var _loc1_ = lol.core.SceneShifter._sl;
      _loc1_.openWin(win);
      _loc1_.activeWindow = win;
   }
   static function closeSlideWindow(win)
   {
      var _loc2_ = !lol.core.SceneShifter._ref.UIPanels[win] ? "default" : win;
      var _loc4_ = lol.core.SceneShifter._ref.UIPanels[_loc2_];
      lol.core.SceneShifter._sl.modeLink.removeMovieClip();
      var _loc1_ = lol.core.SceneShifter._sl;
      _loc1_.kill();
      _loc1_.closeWin(win);
      delete _loc4_.instance;
      lol.core.SceneShifter._ref.sceneEnabled();
   }
   static function openNewAlert(type)
   {
      var _loc2_ = lol.core.SceneShifter._ref.currentScene.topWindow;
      var _loc1_ = _loc2_.open(type);
      return _loc1_;
   }
   static function closeAlert()
   {
      var _loc1_ = lol.core.SceneShifter.locationScreen.topWindow;
      _loc1_.close();
   }
   static function openNewWindow(win, pos, bookmark, groupWinId)
   {
      var _loc7_ = !lol.core.SceneShifter._ref.UIPanels[win] ? "default" : win;
      var _loc1_ = lol.core.SceneShifter._ref.UIPanels[_loc7_];
      var _loc10_ = _loc1_.group;
      var _loc2_;
      var _loc19_;
      var _loc14_;
      var _loc21_;
      var _loc8_;
      var _loc4_;
      var _loc12_;
      var _loc16_;
      var _loc3_;
      var _loc11_;
      var _loc5_;
      if(!_loc1_.instance || _loc10_)
      {
         _loc19_ = _loc1_.linkID;
         _loc14_ = _loc1_.mode;
         _loc21_ = _loc1_.closeBtn;
         _loc8_ = _loc1_.cont;
         _loc4_ = lol.core.SceneShifter[_loc8_].getNextHighestDepth();
         lol.core.SceneShifter.newInterfaceGameHelpMessage(win);
         if(!_loc10_)
         {
            _loc12_ = !bookmark ? "window" : "bookmarksWindow";
            _loc2_ = lol.core.SceneShifter[_loc8_].attachMovie(_loc12_,_loc12_ + _loc4_,_loc4_ + 1);
            _loc1_.instance = _loc2_;
         }
         else
         {
            if(!_loc1_.instance)
            {
               _loc16_ = new Array();
               _loc1_.instance = _loc16_;
            }
            for(var _loc9_ in _loc1_.instance)
            {
               if(_loc1_.instance[_loc9_].id == groupWinId)
               {
                  _loc3_ = _loc9_;
                  break;
               }
            }
            if(_loc3_ == undefined)
            {
               _loc2_ = lol.core.SceneShifter[_loc8_].attachMovie("window","window" + _loc4_,_loc4_ + 1);
               _loc11_ = new Object();
               _loc11_.id = groupWinId;
               _loc11_.win = _loc2_;
               _loc1_.instance.push(_loc11_);
            }
            else
            {
               lol.core.SceneShifter.sortWindows("annotation",_loc1_.instance[_loc3_].win);
            }
         }
         _loc2_.isDrag = _loc1_.drag;
         _loc2_.closeBtn = _loc1_.closeBtn;
         if(_loc14_)
         {
            lol.core.SceneShifter._ref.sceneEnabled();
            _loc5_ = lol.core.SceneShifter[_loc8_].attachMovie("modeBackground","modeBackground" + _loc4_,_loc4_);
            _loc5_._width = Stage.width;
            _loc5_._height = lol.core.SceneShifter._ref.H;
            _loc5_._x = (- Stage.width) / 2;
            _loc5_._y = (- Stage.height) / 2;
            _loc2_.modeLink = _loc5_;
            _loc2_.mode = _loc14_;
            lol.core.SceneShifter._ref.sceneEnabled();
         }
         if(bookmark)
         {
            _loc2_.fillContent(_loc7_,bookmark);
            _loc2_.winID = _loc7_;
         }
         else
         {
            _loc2_.fillContent(_loc19_);
            _loc2_.winID = _loc7_;
         }
      }
      var _loc15_;
      var _loc13_;
      var _loc24_;
      var _loc23_;
      var _loc20_;
      if(pos)
      {
         lol.core.SceneShifter.moveWindow(pos,_loc1_.instance);
      }
      else
      {
         _loc2_._visible = false;
         if(_loc10_)
         {
            _loc15_ = 100;
            _loc13_ = _loc1_.instance.length;
            _loc24_ = _loc15_ + 200 + _loc13_ * 25 - Math.round(Stage.width / 2);
            _loc23_ = _loc15_ + _loc13_ * 25 - Math.round(Stage.height / 2);
            _loc20_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.moveWindow,100,{x:_loc24_,y:_loc23_},_loc2_);
         }
         else
         {
            _loc20_ = new lol.utils.Timeout(lol.core.SceneShifter,lol.core.SceneShifter.moveWindow,100,"center",_loc2_);
         }
      }
      return _loc2_;
   }
   static function closeWindow(win, groupWin)
   {
      var _loc4_ = !win ? "default" : win;
      var _loc1_ = lol.core.SceneShifter._ref.UIPanels[_loc4_];
      var _loc5_ = _loc1_.group;
      _loc1_.instance.modeLink.removeMovieClip();
      _loc1_.instance.kill();
      if(!_loc5_)
      {
         _loc1_.instance.removeMovieClip();
         delete _loc1_.instance;
      }
      else
      {
         for(var _loc3_ in _loc1_.instance)
         {
            if(groupWin == _loc1_.instance[_loc3_].win || groupWin == "all")
            {
               _loc1_.instance[_loc3_].win.removeMovieClip();
               _loc1_.instance.splice(_loc3_,1);
            }
         }
         if(_loc1_.instance.length == 0)
         {
            delete _loc1_.instance;
         }
      }
      lol.core.SceneShifter._ref.sceneEnabled();
   }
   static function sortWindows(win, groupWin)
   {
      var _loc5_ = !lol.core.SceneShifter._ref.UIPanels[win] ? "default" : win;
      var _loc1_ = lol.core.SceneShifter._ref.UIPanels[_loc5_];
      var _loc6_ = _loc1_.group;
      var _loc8_ = _loc1_.cont;
      var _loc2_ = lol.core.SceneShifter[_loc8_].getNextHighestDepth();
      if(!_loc6_)
      {
         lol.core.SceneShifter._ref.UIPanels[win].instance.swapDepths(_loc2_);
      }
      else
      {
         for(var _loc4_ in _loc1_.instance)
         {
            if(groupWin == _loc1_.instance[_loc4_].win)
            {
               _loc1_.instance[_loc4_].win.swapDepths(_loc2_);
            }
         }
      }
   }
   static function moveWindow(pos, win)
   {
      win._visible = true;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      var _loc3_;
      if(typeof pos == "string")
      {
         _loc6_ = Stage.width;
         _loc5_ = Stage.height;
         if(win.content.bg)
         {
            _loc4_ = win.content.bg._width;
            _loc3_ = win.content.bg._height;
         }
         else
         {
            _loc4_ = win._width;
            _loc3_ = win._height;
         }
         switch(pos)
         {
            case "center":
               lol.core.SceneShifter._moveWindow((- _loc4_) / 2,(- _loc3_) / 2 - 72,win);
               break;
            case "globalCenter":
               lol.core.SceneShifter._moveWindow((- _loc4_) / 2,(- _loc3_) / 2,win);
               break;
            case "none":
               break;
            default:
               lol.core.SceneShifter._moveWindow((- _loc4_) / 2,(- _loc3_) / 2 - 72,win);
         }
      }
      else if(typeof pos == "object")
      {
         if(pos.x && pos.y)
         {
            lol.core.SceneShifter._moveWindow(pos.x,pos.y,win);
         }
      }
   }
   static function _moveWindow(x, y, w)
   {
      w._x = Math.round(x);
      w._y = Math.round(y);
   }
   function attachItem(target, link, depth)
   {
      var _loc1_ = !depth ? target.getNextHighestDepth() : depth;
      var _loc2_ = target.attachMovie(link,"item" + _loc1_,_loc1_);
      return _loc2_;
   }
   function initClanInspectorListeners()
   {
      var _loc2_ = lol.core.clans.ClanInspector.getInstance();
      _loc2_.addEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_RECEIVED,this,this.inviteInClan);
      _loc2_.addEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,this,this.kickedFromClan);
      _loc2_.addEventListener(lol.core.clans.ClanEvent.THEY_SET_STANDING,this,this.theyChangeStanding);
      _loc2_.addEventListener(lol.core.clans.ClanEvent.WE_SET_STANDING,this,this.weChangeStanding);
   }
   function theyChangeStanding(obj)
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
      var _loc3_ = this.getStandingString(obj.body.theirStat);
      _loc2_.content.label = "Клан &lt;" + obj.body.name + "&gt; изменил отношения к вашему клану на " + _loc3_;
   }
   function weChangeStanding(obj)
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
      var _loc3_ = this.getStandingString(obj.body.stat);
      _loc2_.content.label = "Ваш клан изменил отношения с кланом &lt;" + obj.body.name + "&gt; на " + _loc3_;
   }
   function getStandingString(num)
   {
      var _loc1_;
      switch(num)
      {
         case 0:
            _loc1_ = "нейтралитет";
            break;
         case 1:
            _loc1_ = "мир";
            break;
         case -1:
            _loc1_ = "войну";
      }
      return _loc1_;
   }
   function inviteInClan(obj)
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("query");
      _loc2_.content.addEventListener("click",this,this.inviteAnswer);
      _loc2_.content.label = "Персонаж " + obj.body.rec + " приглашает вас в клан " + obj.body.soc;
   }
   function inviteAnswer(obj)
   {
      obj.target.removeEventListener("click",this,this.inviteAnswer);
      lol.core.SceneShifter.closeWindow("query");
      lol.core.clans.ClanInspector.getInstance().inviteAnswer(obj.success);
   }
   function kickedFromClan(obj)
   {
      var _loc2_;
      if(this.clanInviteParam)
      {
         if(lol.core.SceneShifter._sl.isWindow)
         {
            lol.core.SceneShifter._ref.currentScene.openClanInterface();
         }
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert");
         if(!this.leaveClan)
         {
            _loc2_.content.label = "Вас исключили из клана";
         }
         else
         {
            _loc2_.content.label = "Вы больше не состоите в клане";
         }
      }
      else
      {
         this.clanInviteParam = true;
      }
      this.leaveClan = false;
   }
   function initBGManagerListeners()
   {
      var _loc2_ = lol.core.battlegrounds.BattleGroundManager.getInstance();
      trace("initBGManagerListeners -> " + _loc2_);
      _loc2_.addEventListener(lol.core.battlegrounds.BattleGroundManager.BG_EVENT_GOT_STATISTIC,this,this.battleGroundGotStatistic);
   }
   function battleGroundGotStatistic(obj)
   {
      var _loc2_ = lol.core.battlegrounds.BattleGroundManager.getInstance();
      trace("SceneShifter -> battleGroundGotStatistic got it!");
      if(this.UIPanels.bg_statistic.instance)
      {
         lol.core.SceneShifter.closeWindow("bg_statistic");
         this.BG_Statistic_Window = null;
         delete this.BG_Statistic_Window;
      }
      else
      {
         this.BG_Statistic_Window = lol.core.SceneShifter.openNewWindow("bg_statistic");
      }
   }
   static function introScene()
   {
      lol.core.SceneShifter._sl.isWindow = false;
      lol.core.SceneShifter.deleteCurrentScene();
      var _loc1_ = lol.core.Master.getInstance();
      lol.core.SceneShifter.introScreen = lol.gpui.Introduction(lol.utils.MCFabric.create(lol.gpui.Introduction,lol.core.SceneShifter.linkGame,"introScreen",lol.core.SceneShifter.mainDepth));
      lol.core.SceneShifter._ref.currentScene = lol.core.SceneShifter.introScreen;
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter._removeIntroScene;
   }
   static function removeIntroScene()
   {
      lol.core.SceneShifter.fadeInOut(lol.core.SceneShifter.introScreen,false);
      lol.core.SceneShifter.fadeOutCurrentScene = lol.core.SceneShifter._removeIntroScene;
   }
   static function _removeIntroScene()
   {
      lol.core.SceneShifter.introScreen.removeMovieClip();
      delete lol.core.SceneShifter.introScreen;
   }
   static function persGenScene()
   {
      lol.core.SceneShifter.removeAllWindow();
      lol.core.SceneShifter._sl = new lol.gpui.view.SlideWindowContainer();
      lol.core.SceneShifter.deleteCurrentScene();
      lol.core.SceneShifter.enterWinFrame = lol.core.SceneShifter.linkGame.attachMovie("enterWinFrame","enterWinFrame",lol.core.SceneShifter.mainDepth + 1);
      lol.core.SceneShifter.enterWinFrame._x = Stage.width / 2 - lol.core.SceneShifter.enterWinFrame._width / 2;
      lol.core.SceneShifter.enterWinFrame._y = Stage.height / 2 - 300;
      lol.core.SceneShifter.openNewSlideWindow("persGen",lol.core.SceneShifter.enterWinFrame);
      lol.core.SceneShifter.deleteCurrentScene = lol.core.SceneShifter.removePersGenScene;
   }
   static function removePersGenScene()
   {
      var _loc1_ = lol.core.SceneShifter.linkGame.enterWinFrame;
      if(_loc1_)
      {
         lol.core.SceneShifter._sl.isWindow = false;
         _loc1_.removeMovieClip();
         lol.core.SceneShifter.gmapScreen._visible = true;
         lol.core.SceneShifter.locationScreen._visible = true;
      }
      else
      {
         lol.core.SceneShifter.gmapScreen._visible = true;
         lol.core.SceneShifter.locationScreen._visible = true;
      }
   }
   function copyLog()
   {
      var _loc2_ = lol.core.SceneShifter.main.dPan.logArr;
      var _loc7_ = "";
      var _loc1_ = 0;
      var _loc4_;
      var _loc5_;
      var _loc3_;
      var _loc6_;
      while(_loc1_ < _loc2_.length)
      {
         _loc4_ = _loc2_[_loc1_].mess;
         _loc5_ = _loc2_[_loc1_].from;
         _loc3_ = _loc2_[_loc1_].time;
         _loc6_ = _loc5_ + " t1: " + _loc3_ + " -> " + _loc4_ + "\r\r";
         _loc7_ += _loc6_;
         _loc1_ = _loc1_ + 1;
      }
      System.setClipboard(_loc7_);
      var _loc8_ = lol.core.SceneShifter.openNewWindow("alert");
      _loc8_.content.label = "Лог скопирован<BR>в буфер обмена";
   }
   function copyHash()
   {
      System.setClipboard(lol.core.Master.getInstance().session.hash);
      var _loc1_ = lol.core.SceneShifter.openNewWindow("alert");
      _loc1_.content.label = "Ваш хэш скопирован<BR>в буфер обмена";
   }
   static function newServiceMessage(label_str, type)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SERVICE_MESSAGE);
      if(!_loc1_)
      {
         return lol.core.SceneShifter.serviceMessageManager.newMessage(label_str,type);
      }
   }
   static function newGameHelpMessage(id)
   {
      var _loc2_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(id != undefined && !isNaN(id) && _loc2_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newMessage(id);
      }
   }
   static function newStartGameHelpMessage()
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(_loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newStartGameHelpMessage();
      }
   }
   static function newNPCGameHelpMessage(npc_name)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(npc_name != undefined && _loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newNPCGameHelpMessage(npc_name);
      }
   }
   static function newQuestTypeMessage(quest_type)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(quest_type != undefined && !isNaN(quest_type) && _loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newQuestTypeMessage(quest_type);
      }
   }
   static function newLocationGameHelpMessage(location_name)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(location_name != undefined && _loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newLocationGameHelpMessage(location_name);
      }
   }
   static function newQuestGameHelpMessage(quest_name)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(quest_name != undefined && _loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newQuestGameHelpMessage(quest_name);
      }
   }
   static function newInterfaceGameHelpMessage(window_name)
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(window_name != undefined && _loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newInterfaceGameHelpMessage(window_name);
      }
   }
   static function newSkillLevelUpGameHelpMessage()
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(_loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newSkillLevelUpGameHelpMessage();
      }
   }
   static function newSpecLevelUpGameHelpMessage()
   {
      var _loc1_ = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      if(_loc1_)
      {
         lol.core.SceneShifter.gamehelpMessageManager.newSpecLevelUpGameHelpMessage();
      }
   }
   function getProfileUrl()
   {
      var _loc2_ = "http://lava-online.ru/exe/user/profile";
      var _loc4_;
      var _loc3_;
      if(this.login != undefined && this.login != "")
      {
         _loc2_ = _loc2_ + "/login/" + this.login + "/ref/1";
      }
      else
      {
         _loc4_ = lol.core.Master.getInstance();
         if(_loc4_ != undefined)
         {
            _loc3_ = _loc4_.gamer.playerInfo.name;
            if(_loc3_ != undefined && _loc3_ != "")
            {
               _loc2_ = _loc2_ + "/user/" + _loc3_ + "/ref/1";
            }
         }
      }
      return _loc2_;
   }
}
