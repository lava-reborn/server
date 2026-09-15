class lol.core.Session
{
   var XMC;
   var _parent;
   var data;
   var dispatchEvent;
   var hash;
   var hashHTTPR;
   var helloTimeout;
   var host;
   var port;
   var spt;
   var spt_int;
   function Session()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("onClose",this);
      this.XMC.addEventListener("onConnect",this);
      this.XMC.addEventListener("connectionFailed",this);
      this.XMC.addEventListener("hello",this);
      this.XMC.addEventListener("kickban",this);
      this.XMC.addEventListener("shutdown",this);
   }
   function loadSS()
   {
      var _loc2_ = lol.core.SSettings.getInstance();
      _loc2_.addEventListener("onLoad",this,this.createSBase);
      _loc2_.start();
   }
   function createSBase()
   {
      var _loc2_ = lol.local.SBase.getInstance();
      _loc2_.addEventListener("onLoad",this,this.loadSBase);
      _loc2_.createDB();
   }
   function getHashHostPort(str)
   {
      var _loc4_ = new Object();
      var _loc7_;
      var _loc6_;
      var _loc5_;
      var _loc3_ = str.indexOf(":");
      if(_loc3_ == -1)
      {
         _loc3_ = str.length;
      }
      _loc4_.host_str = str.substring(0,_loc3_);
      var _loc2_ = str.indexOf(" ",_loc3_);
      if(_loc2_ == -1)
      {
         _loc2_ = str.length;
      }
      _loc4_.port_str = str.substring(_loc3_ + 1,_loc2_);
      if(_loc2_ != str.length - 1)
      {
         _loc4_.hash_str = str.substring(_loc2_ + 1,str.length);
      }
      return _loc4_;
   }
   function attribsLoaded(success)
   {
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(success)
      {
         _loc4_ = lol.core.Master.getInstance().session;
         _loc3_ = this.data;
         _loc2_ = this._parent.getHashHostPort(_loc3_);
         this.host = _loc2_.host_str;
         this.port = _loc2_.port_str;
         this.hash = _loc2_.hash_str;
         lol.core.SceneShifter.enterScene();
         this._parent.connect(this.host,this.port,this.hash);
      }
   }
   function _trace(str)
   {
      lol.core.SceneShifter.main.dPan.trace(str);
   }
   function loadSBase(obj)
   {
      var _loc5_ = lol.core.SSettings.getInstance();
      _loc5_.removeEventListener("onLoad",this,this.createSBase);
      var _loc4_;
      var _loc3_;
      if(_root.logged == 1 && lol.services.SSEmulator.PATHTYPE == lol.services.SSEmulator.WEB)
      {
         _loc4_ = new LoadVars();
         _loc3_ = new LoadVars();
         _loc3_._parent = this;
         _loc3_.onLoad = this.attribsLoaded;
         _loc4_.sendAndLoad("/exe/lavaclient/loaduser/?ajax",_loc3_,"POST");
      }
      else
      {
         lol.core.SceneShifter.enterScene();
      }
   }
   function getHashAndLogin()
   {
      var _loc3_ = _root.session;
      this.hashHTTPR = new lol.server.HTTPRequest();
      this.hashHTTPR = new lol.server.HTTPRequest();
      this.hashHTTPR.addEventListener("onXML",this,this.hashAccess);
      this.hashHTTPR.addEventListener("failed",this,this.hashFailed);
      this.hashHTTPR.Send("",lol.services.SSEmulator.getHashURL(_loc3_));
   }
   function hashFailed()
   {
      lol.core.SceneShifter.enterScene();
   }
   function hashAccess(obj)
   {
      lol.core.SceneShifter.enterScene();
      var _loc2_ = obj.data.toString();
      var _loc4_;
      var _loc3_;
      if(_loc2_ != undefined && _loc2_ != "0")
      {
         _loc4_ = lol.core.SSettings.getInstance().host;
         _loc3_ = lol.core.SSettings.getInstance().port;
         this.connect(_loc4_,_loc3_,_loc2_);
      }
   }
   function onConnect()
   {
      this.start();
   }
   function connectionFailed(obj)
   {
   }
   function onClose()
   {
   }
   function connect(_host, _port, _hash)
   {
      this.host = _host;
      this.port = _port;
      this.hash = _hash;
      if(this.XMC.status)
      {
         this.start();
      }
      else
      {
         this.XMC.connect(this.host,this.port);
      }
   }
   function start()
   {
      lol.core.Master.getInstance().currentState = lol.core.Master.ENTER_STATE;
      this.sendHello();
   }
   function sendHello()
   {
      var _loc2_ = new lol.server.mess.CSM_Hello();
      this.helloTimeout = setInterval(this,"helloTimeOutFunction",20000);
      this.XMC.Send(_loc2_);
   }
   function helloTimeOutFunction()
   {
      clearInterval(this.helloTimeout);
      this.XMC.closeWithoutHelloResponse();
   }
   function hello(obj)
   {
      clearInterval(this.helloTimeout);
      this.login();
   }
   function login()
   {
      var _loc2_;
      if(this.hash.length > 0)
      {
         _loc2_ = new lol.server.mess.CSM_Login(new lol.data.GDString(this.hash));
         if(this.XMC.Send(_loc2_))
         {
            lol.server.XMLCCallStack.addCall("cmdAck",this,this.cmdAck);
         }
      }
   }
   function cmdAck(obj)
   {
      this.XMC.removeEventListener("cmdAck",this);
      var _loc2_ = obj.param.res;
      if(Number(_loc2_) == 0)
      {
         lol.core.Master.getInstance().persGen.loadDescription();
      }
      this.dispatchEvent({type:"onLogin",res:_loc2_,hash:this.hash});
   }
   function finish()
   {
      var _loc2_ = new lol.server.mess.CSM_Logout();
      this.XMC.Send(_loc2_);
   }
   function kickban(obj)
   {
      var _loc4_ = obj.param.admin;
      var _loc2_ = obj.param.seconds;
      var _loc3_ = obj.param.reason;
      var _loc1_ = "Администратор " + _loc4_ + " ведет работу над вашим аккаунтом.\r";
      if(_loc2_ > 0)
      {
         _loc1_ += "Аккаунт будет недоступен в течении " + _loc2_ + " секунд.";
      }
      if(_loc3_)
      {
         _loc1_ += "\r\n" + _loc3_;
      }
      var _loc6_ = lol.core.SceneShifter.openNewWindow("alert","center");
      _loc6_.content.write(_loc1_);
   }
   function shutdown(obj)
   {
      var _loc1_ = obj.param.seconds;
      var _loc2_ = "Сервер будет остановлен через " + _loc1_ + " секунд. Перед началом игры, пожалуйста, выключите и включите клиент.";
      var _loc3_ = lol.core.SceneShifter.openNewWindow("alert","center");
      _loc3_.content.write(_loc2_);
   }
   function kill()
   {
      this.XMC.removeEventListener("onConnect",this);
      this.XMC.removeEventListener("onClose",this);
      this.XMC.removeEventListener("connectionFailed",this);
      lol.server.XMLCCallStack.skipCall("cmdAck",this,this.cmdAck);
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("Session_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
