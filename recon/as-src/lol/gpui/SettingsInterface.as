class lol.gpui.SettingsInterface extends lol.gpui.GPUIObject
{
   var bookmark1_btn;
   var bookmark1_mc;
   var bookmark2_btn;
   var bookmark2_mc;
   var bookmark0_btn;
   var bookmark0_mc;
   var close_btn;
   var cont;
   var currentBookMark;
   var currentCode;
   var default_btn;
   var difCont;
   var dispatchEvent;
   var musicSlider;
   var mute_btn;
   var scrollPan;
   var soundCont;
   var soundSlider0;
   var soundSlider1;
   var initPage0 = "initHotKeysSettings";
   var initPage1 = "initDifferentSettings";
   var initPage2 = "initSoundSettings";
   function SettingsInterface()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.default_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.defaultSettings);
      this.bookmark0_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.bookmark1_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.bookmark2_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.scrollPan.fillContent();
      this.scrollPan.setSize(419,367);
      this.cont = this.scrollPan.content;
      this.bookmark0_btn.data = 0;
      this.bookmark1_btn.data = 1;
      this.bookmark2_btn.data = 2;
      this.currentBookMark = this.bookmark0_btn;
      this.bookmark0_mc.toggled = true;
      this.bookmark1_mc.toggled = false;
      this.bookmark2_mc.toggled = false;
      this.initHotKeysSettings();
      lol.core.SceneShifter.hotKeyManager.addFilter("settings");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function kill()
   {
      this.bookmark0_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.bookmark1_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.bookmark2_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectBookMark);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.default_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.defaultSettings);
      lol.core.SceneShifter.hotKeyManager.removeFilter("settings");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
   function selectBookMark(obj)
   {
      if(this.currentBookMark != obj.target)
      {
         this["bookmark" + this.currentBookMark.data + "_mc"].toggled = false;
         this.currentBookMark = obj.target;
         this["bookmark" + this.currentBookMark.data + "_mc"].toggled = true;
         this[this["initPage" + this.currentBookMark.data]]();
      }
   }
   function initHotKeysSettings()
   {
      this.difCont = null;
      this.scrollPan.fillContent();
      this.cont = this.scrollPan.content;
      var _loc3_ = lol.core.SceneShifter.hotKeyManager.getHotKeyArr();
      var _loc4_ = 0;
      var _loc2_;
      for(var _loc5_ in _loc3_)
      {
         if(_loc3_[_loc5_].about != "")
         {
            _loc2_ = this.cont.attachMovie("setting_btn","setting_btn" + _loc5_,this.cont.getNextHighestDepth());
            _loc2_.id = _loc5_;
            _loc2_._y = _loc4_ * (_loc2_._height + 4);
            _loc2_.addEventListener("input",this,this.inputCode);
            _loc2_.addEventListener("save",this,this.saveCode);
            _loc4_ = _loc4_ + 1;
         }
      }
      this.scrollPan.setPosition(0,0);
   }
   function inputCode(obj)
   {
      if(this.currentCode != obj.target)
      {
         this.currentCode.bg_btn.toggled = false;
         this.currentCode.key_txt.text = this.currentCode.tempStr;
         this.currentCode.key_txt.textColor = 5328970;
         this.currentCode.keyListener(false);
         this.currentCode = obj.target;
      }
   }
   function saveCode(obj)
   {
      var _loc2_ = lol.core.SceneShifter.hotKeyManager.getHotKeyArr();
      var _loc3_ = _loc2_[obj.target.id];
      _loc3_.keyCode = obj.codeArr;
      delete _loc2_[obj.target.id];
      _loc2_[obj.target.id] = _loc3_;
      lol.core.SceneShifter.hotKeyManager.resort();
      lol.core.SceneShifter.hotKeyManager.saveSettings();
      delete this.currentCode;
   }
   function initDifferentSettings()
   {
      this.scrollPan.fillContent();
      this.cont = this.scrollPan.content;
      this.difCont = this.cont.attachMovie("differentSettingsContent","difCont",this.cont.getNextHighestDepth());
      this.doLater("initCheckBox");
   }
   function initCheckBox()
   {
      this.difCont.showTimeInChat_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTimeInChat);
      this.difCont.showTimeInChat_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT);
      this.difCont.autoReload_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoReload);
      this.difCont.autoReload_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_RELOAD);
      this.difCont.criticalAmmo_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.criticalAmmo);
      this.difCont.criticalAmmo_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRITICAL_AMMO_ALARM);
      this.difCont.criticalAmmo_txt.text = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_CRITICAL_AMMO);
      this.difCont.criticalAmmo_txt.onChanged = mx.utils.Delegate.create(this,this.changedCriticalAmmo);
      this.difCont.criticalAmmo_txt.restrict = "0-9";
      this.difCont.numOfMessage_txt.text = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_MESSAGE);
      this.difCont.numOfMessage_txt.onChanged = mx.utils.Delegate.create(this,this.changedNumOfMessage);
      this.difCont.numOfMessage_txt.restrict = "0-9";
      this.difCont.autoShot_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoShot);
      this.difCont.autoShot_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_SHOT);
      this.difCont.autoFire_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoFire);
      this.difCont.autoFire_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_FIRE);
      this.difCont.pathFinding_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.pathFinding);
      this.difCont.pathFinding_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.PATH_FINDING);
      this.difCont.serviceMessage_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.serviceMessage);
      this.difCont.serviceMessage_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SERVICE_MESSAGE);
      this.difCont.animation_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.animation);
      this.difCont.animation_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.ANIMATION);
      this.difCont.cruelTrophhy_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.cruelTrophhy);
      this.difCont.cruelTrophhy_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRUEL_TROPHY);
      this.difCont.showOwnSet_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showOwnSet);
      this.difCont.showOwnSet_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_OWN_WEAR_SET);
      this.difCont.showGameHelp_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showGameHelp);
      this.difCont.showGameHelp_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
      this.difCont.showTradeChannel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTradeChannel);
      this.difCont.showTradeChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TRADE_CHANNEL);
      this.difCont.showWorldChannel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showWorldChannel);
      this.difCont.showWorldChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_WORLD_CHANNEL);
      this.difCont.showHelpChannel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHelpChannel);
      this.difCont.showHelpChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_HELP_CHANNEL);
      this.difCont.showEventChannel_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showEventChannel);
      this.difCont.showEventChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL);
      this.difCont.showHeadMsg_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHeadMessages);
      this.difCont.showHeadMsg_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_MSGS_UNDER_HEAD);
      var _loc2_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanReg;
      if(_loc2_ == 16777215)
      {
         this.difCont.clanInvite_btn.toggled = true;
      }
      else if(_loc2_ == 0)
      {
         this.difCont.clanInvite_btn.toggled = false;
      }
      else
      {
         this.difCont.clanInvite_btn.enabled = false;
      }
      this.difCont.clanInvite_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.clanInvite);
      var _loc3_ = lol.core.Master.getInstance().gamer.partyManager.inParty(0);
      if(_loc3_)
      {
         this.difCont.partyInvite_btn.toggled = true;
      }
      else
      {
         this.difCont.partyInvite_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.FORBID_PARTY_INVITE);
      }
      this.difCont.partyInvite_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.partyInvite);
   }
   function killDifferentSettings()
   {
      this.difCont.showHeadMsg_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHeadMessages);
      this.difCont.showTimeInChat_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTimeInChat);
      this.difCont.autoReload_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoReload);
      this.difCont.criticalAmmo_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.criticalAmmo);
      this.difCont.clanInvite_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.clanInvite);
      this.difCont.partyInvite_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.partyInvite);
      this.difCont.autoShot_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoShot);
      this.difCont.autoFire_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.autoFire);
      this.difCont.pathFinding_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.pathFinding);
      this.difCont.serviceMessage_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.serviceMessage);
      this.difCont.showOwnSet_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showOwnSet);
      this.difCont.showTradeChannel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showTradeChannel);
      this.difCont.showWorldChannel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showWorldChannel);
      this.difCont.showHelpChannel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showHelpChannel);
      this.difCont.showEventChannel_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showEventChannel);
   }
   function partyInvite(obj)
   {
      lol.core.party.PartyManager.getInstance().PartyInviteForbidden(obj.target.toggled);
   }
   function clanInvite(obj)
   {
      lol.core.SceneShifter._ref.clanInviteParam = false;
      lol.core.clans.ClanInspector.getInstance().changeClanInvitationState();
   }
   function waterAnimation(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.WATER_ANIMATION,obj.target.toggled);
   }
   function showTimeInChat(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT,obj.target.toggled);
      lol.core.SceneShifter.chat.refreshCurrentChannel();
   }
   function autoScroll(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SCROLL_IN_SIDE,obj.target.toggled);
   }
   function autoReload(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.AUTO_RELOAD,obj.target.toggled);
   }
   function criticalAmmo(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.CRITICAL_AMMO_ALARM,obj.target.toggled);
      lol.core.SceneShifter.locationScreen.mainSlotPan.flareWeapon();
   }
   function changedCriticalAmmo()
   {
      var _loc2_ = Number(this.difCont.criticalAmmo_txt.text);
      if(this.difCont.criticalAmmo_txt.text == "")
      {
         _loc2_ = 0;
      }
      if(_loc2_ > 100)
      {
         _loc2_ = 100;
      }
      this.difCont.criticalAmmo_txt.text = _loc2_;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.NUMBER_OF_CRITICAL_AMMO,_loc2_);
      lol.core.SceneShifter.locationScreen.mainSlotPan.flareWeapon();
   }
   function changedNumOfMessage()
   {
      var _loc2_ = Number(this.difCont.numOfMessage_txt.text);
      if(this.difCont.numOfMessage_txt.text == "")
      {
         _loc2_ = 0;
      }
      if(_loc2_ > 250)
      {
         _loc2_ = 250;
      }
      else if(_loc2_ < 1)
      {
         _loc2_ = 1;
      }
      this.difCont.numOfMessage_txt.text = _loc2_;
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.NUMBER_OF_MESSAGE,_loc2_);
      lol.core.SceneShifter.chat.refreshCurrentChannel();
   }
   function showOwnSet(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_OWN_WEAR_SET,obj.target.toggled);
      lol.core.Master.getInstance().gamer.equipment.checkFullSetManually();
   }
   function showGameHelp(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_GAME_HELP,obj.target.toggled);
   }
   function showHeadMessages(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_MSGS_UNDER_HEAD,obj.target.toggled);
   }
   function showTradeChannel(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_TRADE_CHANNEL,obj.target.toggled);
      if(obj.target.toggled)
      {
         lol.core.SceneShifter.chat.createTradeChannel();
      }
      else
      {
         lol.core.SceneShifter.chat.removeTradeChannel();
      }
   }
   function showWorldChannel(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_WORLD_CHANNEL,obj.target.toggled);
      if(obj.target.toggled)
      {
         lol.core.SceneShifter.chat.createWorldChannel();
      }
      else
      {
         lol.core.SceneShifter.chat.removeWorldChannel();
      }
   }
   function showHelpChannel(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_HELP_CHANNEL,obj.target.toggled);
      if(obj.target.toggled)
      {
         lol.core.SceneShifter.chat.createHelpChannel();
      }
      else
      {
         lol.core.SceneShifter.chat.removeHelpChannel();
      }
   }
   function showEventChannel(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL,obj.target.toggled);
      if(obj.target.toggled)
      {
         lol.core.SceneShifter.chat.createEventChannel();
      }
      else
      {
         lol.core.SceneShifter.chat.removeEventChannel();
      }
   }
   function autoShot(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.AUTO_SHOT,obj.target.toggled);
   }
   function autoFire(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.AUTO_FIRE,obj.target.toggled);
   }
   function pathFinding(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.PATH_FINDING,obj.target.toggled);
   }
   function serviceMessage(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SERVICE_MESSAGE,obj.target.toggled);
   }
   function animation(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.ANIMATION,obj.target.toggled);
   }
   function cruelTrophhy(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.CRUEL_TROPHY,obj.target.toggled);
   }
   function initSoundSettings()
   {
      this.scrollPan.fillContent();
      this.cont = this.scrollPan.content;
      this.soundCont = this.cont.attachMovie("soundSettingsContent","soundCont",this.cont.getNextHighestDepth());
      this.doLater("initSoundSlider");
   }
   function initSoundSlider()
   {
      this.soundSlider0 = this.soundCont.soundSlider0;
      this.soundSlider0.setSize(135);
      this.soundSlider0.upButton._visible = this.soundSlider0.downButton._visible = false;
      this.soundSlider0.addEventListener("position",this,this.dragSlider);
      this.soundSlider0.data = "game";
      this.soundSlider1 = this.soundCont.soundSlider1;
      this.soundSlider1.setSize(135);
      this.soundSlider1.upButton._visible = this.soundSlider1.downButton._visible = false;
      this.soundSlider1.addEventListener("position",this,this.dragSlider);
      this.soundSlider1.data = "interface";
      this.musicSlider = this.soundCont.musicSlider;
      this.musicSlider.setSize(135);
      this.musicSlider.upButton._visible = this.musicSlider.downButton._visible = false;
      this.musicSlider.addEventListener("position",this,this.dragMusicSlider);
      this.musicSlider.data = "music";
      this.soundCont.gameSpeaker.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.gameMute);
      this.soundCont.interfaceSpeaker.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.interfaceMute);
      this.soundCont.musicSpeaker.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.musicMute);
      this.mute_btn = this.soundCont.mute_btn;
      this.mute_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.mute);
      this.setVolume(this.soundSlider0,lol.gpui.UserSettings.getSetting("gameSoundVolume"));
      this.setVolume(this.soundSlider1,lol.gpui.UserSettings.getSetting("interfaceSoundVolume"));
      this.setVolume(this.musicSlider,lol.gpui.UserSettings.getSetting("musicVolume"));
      if(lol.gpui.UserSettings.getSetting("gameSoundVolume") == 0 && lol.gpui.UserSettings.getSetting("interfaceSoundVolume") == 0)
      {
         this.mute_btn.toggled = true;
      }
   }
   function gameMute(obj)
   {
      if(obj.target.toggled)
      {
         this.setVolume(this.soundSlider0,0);
      }
      else
      {
         this.setVolume(this.soundSlider0,50);
      }
   }
   function interfaceMute(obj)
   {
      if(obj.target.toggled)
      {
         this.setVolume(this.soundSlider1,0);
      }
      else
      {
         this.setVolume(this.soundSlider1,50);
      }
   }
   function musicMute(obj)
   {
      if(obj.target.toggled)
      {
         this.setVolume(this.musicSlider,0);
      }
      else
      {
         this.setVolume(this.musicSlider,50);
      }
   }
   function mute(obj)
   {
      if(obj.target.toggled)
      {
         this.setVolume(this.soundSlider0,0);
         this.setVolume(this.soundSlider1,0);
         this.setVolume(this.musicSlider,0);
      }
      else
      {
         this.setVolume(this.soundSlider0,50);
         this.setVolume(this.soundSlider1,50);
         this.setVolume(this.musicSlider,50);
      }
   }
   function dragSlider(obj)
   {
      var _loc2_ = obj.pos;
      obj.target.sliderButton.pos_txt.text = Math.round(_loc2_);
      if(_loc2_ == 0)
      {
         this.soundCont[obj.target.data + "Speaker"].toggled = true;
      }
      else
      {
         this.soundCont[obj.target.data + "Speaker"].toggled = false;
      }
      lol.gpui.UserSettings.setSetting(obj.target.data + "SoundVolume",_loc2_);
   }
   function dragMusicSlider(obj)
   {
      var _loc2_ = obj.pos;
      obj.target.sliderButton.pos_txt.text = Math.round(_loc2_);
      if(_loc2_ <= 0)
      {
         this.soundCont.musicSpeaker.toggled = true;
      }
      else
      {
         this.soundCont.musicSpeaker.toggled = false;
      }
      lol.gpui.UserSettings.setSetting("musicVolume",_loc2_);
      lol.sound.SoundManager.getInstance().musicVolume(_loc2_);
   }
   function setVolume(scroll, value)
   {
      scroll.setPosition(value);
      scroll.sliderButton.pos_txt.text = Math.round(value);
      if(value == 0)
      {
         this.soundCont[scroll.data + "Speaker"].toggled = true;
      }
      else
      {
         this.soundCont[scroll.data + "Speaker"].toggled = false;
      }
      lol.gpui.UserSettings.setSetting(scroll.data + "SoundVolume",value);
   }
   function defaultSettings()
   {
      delete lol.core.SceneShifter.hotKeyManager.getHotKeyArr();
      lol.core.SceneShifter.hotKeyManager.createDefaultArr();
      lol.core.SceneShifter.hotKeyManager.saveSettings();
      lol.gpui.UserSettings.defaultSettings();
      this.difCont.showTimeInChat_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TIME_IN_CHAT);
      this.difCont.autoReload_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_RELOAD);
      this.difCont.criticalAmmo_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.CRITICAL_AMMO_ALARM);
      this.difCont.criticalAmmo_txt.text = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_CRITICAL_AMMO);
      this.difCont.numOfMessage_txt.text = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.NUMBER_OF_MESSAGE);
      this.difCont.autoShot_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_SHOT);
      this.difCont.autoFire_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.AUTO_FIRE);
      this.difCont.showTradeChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_TRADE_CHANNEL);
      this.difCont.showWorldChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_WORLD_CHANNEL);
      this.difCont.showHelpChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_HELP_CHANNEL);
      this.difCont.showEventChannel_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_EVENT_CHANNEL);
      this.difCont.showOwnSet_btn.toggled = lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_OWN_WEAR_SET);
      if(this.difCont)
      {
         this.selectBookMark({target:this.bookmark1_btn});
         this.initDifferentSettings();
      }
      else if(this.soundCont)
      {
         this.selectBookMark({target:this.bookmark2_btn});
         this.initSoundSettings();
      }
      else if(this.cont)
      {
         this.selectBookMark({target:this.bookmark0_btn});
         this.initHotKeysSettings();
      }
   }
   function close()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
      this.dispatchEvent({type:"closeWindow"});
   }
}
