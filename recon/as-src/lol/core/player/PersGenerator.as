class lol.core.player.PersGenerator
{
   var HTTP;
   var XMC;
   var accInfoReceived;
   var activated;
   var avatars;
   var can_create;
   var dispatchEvent;
   var newPersInfo;
   var persGenWindow;
   var persInfoReceived;
   var persNum;
   var readyPersonages;
   var tempGeneratedPers;
   var xmlInfoLoaded;
   var introPlayed = false;
   var playHelp_bool = false;
   var playIntro_bool = false;
   function PersGenerator()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("accountInfo",this);
      this.XMC.addEventListener("persInfo",this);
      this.XMC.addEventListener("onClose",this);
      lol.events.LEventDispatcher.initialize(this);
   }
   function onClose()
   {
      this.accInfoReceived = false;
      this.persInfoReceived = false;
   }
   function loadDescription()
   {
      this.HTTP = new lol.server.HTTPRequest();
      this.HTTP.addEventListener("onXML",this);
      this.HTTP.addEventListener("failed",this);
      this.HTTP.Send("",lol.services.SSEmulator.getAvatarInfoURL());
   }
   function onXML(obj)
   {
      this.xmlInfoLoaded = true;
      this.parse(obj.data);
      this.HTTP.removeEventListener("onXML",this);
      this.HTTP.kill();
      this.HTTP = null;
   }
   function parse(doc)
   {
      var _loc5_ = doc.firstChild;
      var _loc3_ = _loc5_.childNodes[0].childNodes;
      this.avatars = new Array();
      var _loc2_;
      for(var _loc4_ in _loc3_)
      {
         _loc2_ = new Object();
         _loc2_.id = _loc3_[_loc4_].attributes.id;
         _loc2_.sex = _loc3_[_loc4_].attributes.sex;
         _loc2_.buy = _loc3_[_loc4_].attributes.buy;
         _loc2_.description = _loc3_[_loc4_].childNodes.join("");
         this.avatars.unshift(_loc2_);
      }
      this.checkFullInfo();
   }
   function failed(obj)
   {
      this.dispatchEvent({type:"failed"});
   }
   function accountInfo(obj)
   {
      this.persNum = obj.param.nPers;
      this.can_create = obj.param.can_create;
      if(this.can_create)
      {
         this.accInfoReceived = true;
         this.checkFullInfo();
      }
   }
   function playIntro(obj)
   {
      this.newPersInfo = obj;
      lol.core.SceneShifter.introScene();
   }
   function skipIntro()
   {
      lol.core.SceneShifter.removeIntroScene();
      if(this.playHelp_bool)
      {
         this.startHelpIntro();
      }
      else
      {
         this.activatePlayer();
      }
   }
   function startHelpIntro()
   {
      var _loc2_ = lol.services.Help.getInstance();
      _loc2_.addEventListener("onLoad",this,this.playHelpIntro);
      _loc2_.start();
   }
   function playHelpIntro(obj)
   {
      obj.target.removeEventListener("onLoad",this,this.playHelpIntro);
      var _loc2_ = lol.core.SceneShifter.openNewWindow("helpVideoLessons","globalCenter");
      _loc2_.content.lessonsArr = lol.services.Help.getInstance().lessonsArr;
      _loc2_.content.curLesson = 0;
      _loc2_.content.skipFlag = true;
      _loc2_.content.addEventListener("closeWindow",this,this.skipHelpIntro);
   }
   function skipHelpIntro()
   {
      this.accInfoReceived = true;
      this.activatePlayer();
   }
   function persInfo(obj)
   {
      if(!this.readyPersonages)
      {
         this.readyPersonages = new Array();
      }
      this.persInfoReceived = true;
      this.persNum = this.persNum - 1;
      var _loc2_ = new lol.core.player.PersInfo();
      _loc2_.id = obj.param.num;
      _loc2_.name = lol.server.XMLString.unescape(obj.param.name);
      _loc2_.sex = obj.param.sex;
      _loc2_.dead = Boolean(obj.param.death);
      _loc2_.resID = obj.param.res;
      this.readyPersonages[_loc2_.id] = _loc2_;
      this.checkFullInfo();
   }
   function checkFullInfo()
   {
      var _loc2_;
      if(this.xmlInfoLoaded)
      {
         if(this.accInfoReceived)
         {
            this.persGenWindow = this.openPersGenUI();
            _loc2_ = new lol.utils.Timeout(this,this._startCreate,100);
         }
         else if(this.persInfoReceived)
         {
            this.createAvatars();
            this.selectDefaultPers();
         }
         this.accInfoReceived = false;
         this.persInfoReceived = false;
      }
   }
   function _startCreate()
   {
      this.persGenWindow.startCreate(this.avatars,null,this.readyPersonages,1);
   }
   function openPersGenUI()
   {
      lol.core.SceneShifter.openSlideWindow("persGenPanel");
      var _loc1_ = lol.core.SceneShifter._sl.getWindow("persGenPanel");
      return _loc1_.content;
   }
   function selectDefaultPers()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      _loc2_.playerInfo = this.readyPersonages[0];
      var _loc3_ = new lol.server.mess.CSM_SelectPers(0);
      this.XMC.Send(_loc3_);
   }
   function createAvatars()
   {
      var _loc4_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc3_;
      var _loc7_;
      var _loc6_;
      while(_loc4_ < this.readyPersonages.length)
      {
         _loc2_ = this.readyPersonages[_loc4_];
         _loc5_ = _loc2_.resID;
         _loc3_ = this.getAvatar(_loc5_);
         _loc7_ = _loc3_.sex;
         _loc6_ = _loc3_.buy;
         _loc2_.setAvatar(_loc5_,_loc7_,_loc6_);
         _loc2_.resID = null;
         _loc2_.sex = _loc3_.sex;
         _loc4_ = _loc4_ + 1;
      }
   }
   function getAvatar(id)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.avatars.length)
      {
         if(id == this.avatars[_loc2_].id)
         {
            return this.avatars[_loc2_];
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function selectPers(obj)
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      _loc2_.playerInfo = obj.persInfo;
      var _loc3_ = new lol.server.mess.CSM_SelectPers(obj.persInfo.id);
      this.XMC.Send(_loc3_);
   }
   function generatePers(obj)
   {
      this.tempGeneratedPers = obj;
      this.___generatePers();
   }
   function ___generatePers()
   {
      var _loc2_ = lol.core.Master.getInstance().gamer;
      _loc2_.playerInfo = this.tempGeneratedPers.persInfo;
      var _loc3_ = this.tempGeneratedPers.persInfo.name;
      var _loc5_ = this.tempGeneratedPers.persInfo.sex;
      var _loc4_ = this.tempGeneratedPers.persInfo.avatar.id;
      var _loc6_ = new lol.server.mess.CSM_CreatePers(new lol.data.GDString(_loc3_),_loc5_,_loc4_);
      if(this.XMC.Send(_loc6_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.cmdAck);
      }
   }
   function cmdAck(obj)
   {
      this.persGenWindow.removeEventListener("selectPers",this);
      if(Number(obj.param.res == 0))
      {
         lol.core.SceneShifter.removePersGenScene();
         this.playIntro();
      }
      else
      {
         this.dispatchEvent({type:"failed"});
      }
   }
   function activatePlayer()
   {
      var _loc2_;
      if(!this.activated)
      {
         this.activated = true;
         _loc2_ = new lol.server.mess.CSM_ActivatePlayer();
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.actPlayerAck);
         }
      }
   }
   function actPlayerAck(obj)
   {
      if(obj.param.res == 0)
      {
      }
      this.activated = false;
   }
   function sendSmsCode()
   {
      var _loc2_;
      var _loc4_;
      var _loc3_;
      var _loc5_;
      if(_loc2_.length > 0)
      {
         _loc4_ = "<code>" + _loc2_ + "</code>";
         _loc3_ = new XML(_loc4_);
         _loc3_.sendAndLoad(_loc5_,this.HTTP);
      }
   }
   function accessCode()
   {
   }
}
