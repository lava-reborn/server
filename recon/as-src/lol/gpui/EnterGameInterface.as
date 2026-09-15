class lol.gpui.EnterGameInterface extends MovieClip
{
   var SO;
   var XMC;
   var _status;
   var copyLog_btn;
   var data;
   var hash;
   var host;
   var host_txt;
   var i_have_problem_btn;
   var login;
   var login_btn;
   var login_txt;
   var lostPassw_btn;
   var newsPaper_mc;
   var onEnterFrame;
   var pass;
   var pass_txt;
   var port;
   var port_txt;
   var rec_obj;
   var registration_btn;
   var saveLoginFlag;
   var saveLogin_btn;
   var send_clip;
   var status_txt;
   var support_btn;
   var text;
   var loadSettingsFlag = true;
   function EnterGameInterface()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("tryConnect",this);
      this.XMC.addEventListener("onConnect",this);
      this.XMC.addEventListener("onClose",this);
      this.XMC.addEventListener("failed",this);
      this.XMC.addEventListener("hello",this);
      Key.addListener(this);
      this.SO = SharedObject.getLocal("csettings","/");
      this.login_txt.tabIndex = 1;
      this.pass_txt.tabIndex = 2;
      this.host_txt.tabIndex = 3;
      this.port_txt.tabIndex = 4;
      this.onEnterFrame = this.init;
      var _loc3_ = lol.display.DisplaySprite.create(this.newsPaper_mc,"cont",0);
      var _loc4_ = lol.services.SSEmulator.getNewspaperURL();
      _loc3_.display("newsPaper_mc",_loc4_);
      _loc3_.addEventListener("onLoadSource",this);
   }
   function onChanged()
   {
      this.hash = null;
   }
   function focusText()
   {
      Selection.setFocus(this.login_txt);
   }
   function attribsLoaded(success)
   {
      var _loc3_;
      var _loc2_;
      if(success)
      {
         _loc3_ = lol.core.Master.getInstance().session;
         _loc2_ = _loc3_.getHashHostPort(this.data);
         if(_loc2_.host_str != undefined && _loc2_.port_str != undefined && _loc2_.host_str != "" && _loc2_.port_str != "")
         {
            this._parent.host_txt.text = _loc2_.host_str;
            this._parent.port_txt.text = _loc2_.port_str;
            trace("this._parent.host_txt.text = " + this._parent.host_txt.text);
            trace("this._parent.port_txt.text = " + this._parent.port_txt.text);
         }
      }
   }
   function getServerNum(str)
   {
      this.send_clip = new LoadVars();
      this.rec_obj = new LoadVars();
      this.rec_obj._parent = this;
      this.rec_obj.onLoad = this.attribsLoaded;
      this.send_clip.name = str;
      this.send_clip.sendAndLoad("/exe/lavaclient/loaduser/?ajax",this.rec_obj,"POST");
      return this.rec_obj.toString();
   }
   function init()
   {
      delete this.onEnterFrame;
      this.saveLogin_btn.addEventListener("click",this,this.saveLogin);
      this.i_have_problem_btn._visible = false;
      this.pass_txt.password = true;
      this.login_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.startSession);
      this.lostPassw_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.lostPassw);
      this.registration_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.registrtion);
      this.support_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.support);
      this.copyLog_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,lol.core.SceneShifter._ref,lol.core.SceneShifter._ref.copyLog);
      this.i_have_problem_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.haveProblem);
      this.pass_txt.onKillFocus = function(newFocus)
      {
         this._parent.killFocus();
      };
      this.pass_txt.onSetFocus = function(oldFocus)
      {
         this._parent.setFocus();
      };
      this.login_txt.addListener(this);
      this.pass_txt.addListener(this);
      this.login_txt.onChanged = function()
      {
         if(this.text != "")
         {
            this._parent.login_btn.enabled = true;
         }
         else
         {
            this._parent.login_btn.enabled = false;
         }
      };
      this.initSettings();
   }
   function kill()
   {
      this.login_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.startSession);
      this.lostPassw_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.lostPassw);
      this.registration_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.registrtion);
      this.support_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.support);
      this.i_have_problem_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.haveProblem);
   }
   function killFocus()
   {
      if(this.pass_txt.text == "")
      {
         if(this.saveLoginFlag)
         {
            this.pass_txt.password = false;
            this.pass_txt.text = "Пароль сохранен";
         }
      }
   }
   function setFocus()
   {
      this.pass_txt.password = true;
      this.pass_txt.text = "";
   }
   function initSettings()
   {
      this.saveLoginFlag = this.SO.data.saveLoginFlag;
      this.saveLogin_btn.toggled = this.saveLoginFlag;
      if(this.saveLoginFlag)
      {
         this.login = this.SO.data.login;
         this.hash = this.SO.data.hash;
         if(this.login.length > 0 && this.hash)
         {
            this.login_txt.text = !this.login ? "" : this.login;
            this.pass_txt.password = false;
            this.pass_txt.text = "Пароль сохранен";
         }
      }
      this.host_txt.text = lol.core.SSettings.getInstance().host;
      this.port_txt.text = String(lol.core.SSettings.getInstance().port);
   }
   function onConnect()
   {
      this.status_txt.text = "Соединение установлено, ожидается ответ сервера";
      var _loc2_ = lol.core.Master.getInstance().persGen;
      _loc2_.addEventListener("failed",this,this.errorLoading);
   }
   function onClose()
   {
      this.status = false;
      this.status_txt.text = "Соединение разорвано";
   }
   function failed()
   {
      this.status = false;
      this.i_have_problem_btn._visible = true;
      this.status_txt.text = "Соединение с сервером не установлено!";
      Key.addListener(this);
   }
   function hello(obj)
   {
      this.status_txt.text = "Подождите, идет загрузка";
   }
   function errorLoading()
   {
      this.status_txt.text = "Невозможно загрузить ресурс " + lol.services.SSEmulator.getAvatarInfoURL();
   }
   function startSession()
   {
      var _loc9_;
      var _loc6_;
      var _loc4_;
      var _loc5_;
      var _loc3_;
      var _loc7_;
      var _loc2_;
      var _loc8_;
      if(!this.status)
      {
         this.status = true;
         Selection.setFocus(null);
         if(!this.hash)
         {
            this.login = this.login_txt.text;
            this.pass = this.pass_txt.text;
            if(this.login.length > 0 && this.pass.length > 0)
            {
               _loc9_ = new lol.server.security.MD5rus();
               this.hash = _loc9_.hashMD5(this.pass + this.login);
            }
            else
            {
               this.status_txt.text = "Введите логин и пароль";
               this.status = false;
            }
         }
         if(this.saveLoginFlag)
         {
            this.SO.data.login = this.login;
            this.SO.data.hash = this.hash;
         }
         else
         {
            this.SO.data.login = null;
            this.SO.data.hash = null;
         }
         this.SO.flush();
         _loc6_ = lol.core.Master.getInstance();
         _loc4_ = _loc6_.session;
         _loc4_.addEventListener("onLogin",this);
         this.host = this.host_txt.text;
         this.port = Number(this.port_txt.text);
         if(this.hash)
         {
            lol.core.SceneShifter._ref.login = this.login;
            _loc4_.connect(this.host,this.port,this.hash);
            _loc5_ = lol.core.SceneShifter._ref.speedLoading;
            _loc3_ = lol.core.SceneShifter._ref.timeLoading;
            _loc7_ = escape(this.login);
            if(_loc3_ > 1000 && _loc3_ && _loc5_)
            {
               System.useCodepage = true;
               _loc2_ = new LoadVars();
               _loc8_ = new LoadVars();
               _loc2_.login = _loc7_;
               _loc2_.speed = _loc5_;
               _loc2_.time = _loc3_;
               _loc2_.sendAndLoad("http://www.lava-online.ru/res/stats.php",_loc8_,"POST");
            }
         }
      }
   }
   function tryConnect(obj)
   {
      this.status_txt.text = "Устанавливается соединение с " + this.host_txt.text;
   }
   function onLogin(obj)
   {
      var _loc3_;
      var _loc4_;
      if(obj.res > 0)
      {
         this.status = false;
         Key.addListener(this);
         this.status_txt.text = "";
         if(obj.res == 3)
         {
            _loc3_ = "Произошла ошибка при попытке прочитать аккаунт пользователя.\nОбратитесь к администрации Lava-Online.";
            _loc4_ = lol.core.SceneShifter.openNewWindow("alert","center");
            _loc4_.content.write(_loc3_);
         }
      }
      else
      {
         _root.var_login = this.login;
      }
   }
   function onKeyDown()
   {
      if(Key.isDown(13))
      {
         if(lol.core.SceneShifter._sl.activeWindow == "connectionPan")
         {
            this.startSession();
            Key.removeListener(this);
         }
      }
   }
   function saveLogin(obj)
   {
      this.saveLoginFlag = this.saveLogin_btn.toggled;
      this.SO.data.saveLoginFlag = this.saveLoginFlag;
      if(!this.saveLoginFlag)
      {
         this.SO.data.login = null;
         this.SO.data.hash = null;
      }
      this.SO.flush();
   }
   function haveProblem()
   {
      this.getURL("http://www.lava-online.ru/index.php?do=static&page=Proxy%20play","_blank");
   }
   function lostPassw()
   {
      this.getURL("http://www.lava-online.ru/index.php?do=lostpassword","_blank");
   }
   function registrtion()
   {
      this.getURL("http://www.lava-online.ru/index.php?do=register","_blank");
   }
   function support()
   {
      this.getURL("mailto:support@vr-ocean.com","_blank");
   }
   function set status(s)
   {
      this._status = s;
      var _loc2_ = 1 + Number(s);
      this.login_btn.gotoAndStop(_loc2_);
   }
   function get status()
   {
      return this._status;
   }
}
