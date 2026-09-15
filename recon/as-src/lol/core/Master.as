class lol.core.Master
{
   var XMC;
   var _currentState;
   var chat;
   var currentLocation;
   var dispatchEvent;
   var globalMap;
   var lgetted;
   var lloaded;
   var locGen;
   var persGen;
   var playerRegister;
   var resurrector;
   var sceneShifter;
   var session;
   var session_login_timer_id;
   var tempL;
   static var sInstance;
   static var singleCreation;
   var userCallChangeWorld = false;
   var changeGlobalTolLocal = false;
   static var ENTER_STATE = "enter";
   static var GLOBAL_STATE = "gm";
   static var LOCAL_STATE = "loc";
   static var CW_STATE = "cw";
   static var DEAD_STATE = "dead";
   function Master()
   {
      var _loc2_;
      if(lol.core.Master.singleCreation)
      {
         _loc2_ = new lol.utils.Timeout(this,this.init,100);
      }
   }
   function init()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("onClose",this);
      this.XMC.addEventListener("gmap",this);
      this.XMC.addEventListener("lcall",this);
      this.XMC.addEventListener("lenter",this);
      this.XMC.addEventListener("usrUp",this);
      lol.core.GConstatns.create();
      this.persGen = new lol.core.player.PersGenerator();
      this.chat = new lol.core.Chat();
      this.locGen = new lol.core.location.LocGen();
      this.locGen.addEventListener("locLoaded",this);
      this.sceneShifter = lol.core.SceneShifter._ref;
      this.resurrector = new lol.core.player.Resurrector();
      lol.utils.ErrorReport.create();
      this.start();
      this.session = new lol.core.Session();
      this.session_login_timer_id = setInterval(this,"sessionLogin",3000);
   }
   function sessionLogin()
   {
      clearInterval(this.session_login_timer_id);
      this.session.loadSS();
   }
   function quit()
   {
      this.session.finish();
   }
   function onClose()
   {
      this.finish();
   }
   function start()
   {
      this.playerRegister = new lol.core.player.PlayerRegister();
      this.playerRegister.createGamer();
      this.initClanInspector();
      this.initMailInspector();
   }
   function finish()
   {
      lol.server.XMLCCallStack.clear();
      this.globalMap.kill();
      delete this.globalMap;
      this.currentLocation.kill();
      delete this.currentLocation;
      this.playerRegister.clearPlayerList();
      this.playerRegister.kill();
      delete this.playerRegister;
      lol.core.quests.QuestInspector.getInstance().clear();
      lol.sound.SoundManager.getInstance().stopCurrentTrack();
      lol.core.mail.MailInspector.getInstance().kill();
      this.start();
      lol.core.SceneShifter.enterScene();
      lol.core.battlegrounds.BattleGroundManager.getInstance.kill();
   }
   function initClanInspector()
   {
      var _loc1_ = lol.core.clans.ClanInspector.getInstance();
      lol.core.SceneShifter._ref.initClanInspectorListeners();
   }
   function initMailInspector()
   {
      var _loc1_ = lol.core.mail.MailInspector.getInstance();
   }
   function addPlayer(id, rtype)
   {
      var _loc2_ = this.playerRegister.addPlayer(id,rtype);
      _loc2_.addEventListener("userUpdate",this);
      return _loc2_;
   }
   function removePlayer(id)
   {
      var _loc2_ = this.getPlayer(id);
      _loc2_.removeEventListener("userUpdate",this);
      this.playerRegister.removePlayer(id);
   }
   function get gamer()
   {
      return this.playerRegister.gamer;
   }
   function getPlayer(id)
   {
      return this.playerRegister.getPlayer(id);
   }
   function getPlayerByName(name)
   {
      return this.playerRegister.getPlayerByName(name);
   }
   function userUpdate(obj)
   {
      var _loc2_ = obj.target;
      this.dispatchEvent({type:"userUpdate",player:_loc2_});
   }
   function usrUp(obj)
   {
      var _loc2_ = obj.param.id;
      var _loc3_ = this.getPlayer(_loc2_);
      _loc3_.userUpdate(obj);
   }
   function changeWorld(param)
   {
      var _loc2_ = new lol.server.mess.CSM_ChangeWorld(param);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.changeWorldAck,this.currentState);
      }
      this.userCallChangeWorld = true;
      this.currentState = lol.core.Master.CW_STATE;
   }
   function changeWorldAck(obj)
   {
      var _loc2_ = obj.param.res;
      var _loc5_ = false;
      var _loc3_;
      if(_loc2_ == 0)
      {
         _loc5_ = true;
      }
      else if(_loc2_ == 39)
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "Вы не можете выйти из локации в режиме боя в течение " + lol.core.GConstatns.getLeaveCombatLocationPause() + " сек. после вашего последнего выстрела или удара ножом";
         this.currentState = obj.data;
      }
      else
      {
         this.currentState = obj.data;
      }
      this.dispatchEvent({type:"changeWorld",success:_loc5_});
   }
   function playerIntercepted()
   {
      if(!this.userCallChangeWorld && this.changeGlobalTolLocal)
      {
         return true;
      }
      return false;
   }
   function set currentState(cs)
   {
      this._currentState = cs;
      lol.server.filters.FilterManager.getInstance().changeState();
      this.dispatchEvent({type:"changeState",state:cs});
   }
   function get currentState()
   {
      return this._currentState;
   }
   function gmap(obj)
   {
      this.currentLocation.kill();
      delete this.currentLocation;
      this.currentState = lol.core.Master.GLOBAL_STATE;
      this.globalMap = new lol.core.globmap.GlobalMap();
      this.globalMap.addGamer(obj);
      lol.core.SceneShifter.gmapScene();
      this.gamer.requestInfo();
      if(this.gamer.playerInfo.dead)
      {
         this.resurrector.resurrectGamer();
      }
      lol.sound.SoundManager.getInstance().playSoundTrack("Signals");
      lol.core.quests.QuestInspector.getInstance().requestCurrentQuests();
   }
   function lcall(obj)
   {
      if(this.currentState == lol.core.Master.GLOBAL_STATE)
      {
         this.changeGlobalTolLocal = true;
      }
      else
      {
         this.changeGlobalTolLocal = false;
      }
      this.currentState = lol.core.Master.CW_STATE;
      this.lloaded = false;
      this.tempL = new Object();
      this.tempL.locID = obj.param.id;
      this.tempL.warState = obj.param.ws;
      this.tempL.ie = obj.param.ie;
      this.tempL.geoID = obj.param.g_id;
      this.locGen.geoID = this.tempL.geoID;
      this.locGen.loadLocDescription(this.tempL.locID);
   }
   function locLoaded()
   {
      this.lloaded = true;
      var _loc2_;
      var _loc3_;
      if(!this.lgetted && this.tempL.ie != 1)
      {
         _loc2_ = new lol.server.mess.CSM_L_Enter(1);
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.lenterAck);
         }
      }
      else if(this.currentLocation.isBGLocation())
      {
         _loc3_ = new lol.utils.Timeout(this,this.requestBGInfo,1500);
      }
      this.enterLocation();
   }
   function requestBGInfo()
   {
      var _loc1_ = lol.core.battlegrounds.BattleGroundManager.getInstance();
      if(_loc1_ != undefined)
      {
         _loc1_.requestingBGInfo();
      }
   }
   function lenterAck(obj)
   {
      var _loc2_;
      if(obj.param.res != 0)
      {
         _loc2_ = this.locGen.getGL();
         _loc2_.kill();
         this.locGen.setGL(null);
         this.dispatchEvent({type:"changeWorld",success:false});
      }
   }
   function lenter(obj)
   {
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.lenterAck);
      if(this.globalMap)
      {
         this.globalMap.kill();
         delete this.globalMap;
      }
      this.currentState = lol.core.Master.LOCAL_STATE;
      this.lgetted = true;
      this.tempL.pos = obj.param.pos;
      this.tempL.aspd = obj.param.aspd;
      this.tempL.amax = obj.param.amax;
      this.currentLocation.kill();
      this.currentLocation = this.locGen.getGL();
      var _loc2_ = this.currentLocation.locInfo;
      this.locGen.lsLoader.unloadSources(_loc2_);
      this.currentLocation.addGamer(this.tempL.pos);
      this.gamer.apManager.setAP(this.tempL.aspd,this.tempL.amax);
      this.currentLocation.warState(this.tempL.warState);
      this.currentLocation.locInfo.geoID = this.tempL.geoID;
      this.enterLocation();
      if(this.gamer.playerInfo.dead)
      {
         this.resurrector.resurrectGamer();
      }
      this.requestInfo();
   }
   function enterLocation()
   {
      this.userCallChangeWorld = false;
      if(this.lloaded && this.lgetted)
      {
         this.lgetted = false;
         this.lloaded = false;
         lol.core.SceneShifter.locationScene();
         this.locGen.setGL(null);
      }
   }
   function requestInfo()
   {
      this.gamer.requestInfo();
      this.gamer.attributes.requestAttributes();
      this.gamer.equipment.firstRequest();
      lol.core.quests.QuestInspector.getInstance().requestCurrentQuests();
      lol.core.objects.ItemFactory.sendCall();
      lol.core.sets.SetManager.sendCall();
      this.gamer.itemActivator.breakAction();
      lol.core.battlegrounds.BattleGroundManager.getInstance();
   }
   static function getInstance()
   {
      if(!lol.core.Master.sInstance)
      {
         lol.core.Master.singleCreation = true;
         lol.core.Master.sInstance = new lol.core.Master();
         lol.core.Master.singleCreation = false;
      }
      return lol.core.Master.sInstance;
   }
}
