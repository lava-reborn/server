class lol.services.DebugPanel extends MovieClip
{
   var H;
   var W;
   var X;
   var XMC;
   var Y;
   var a_prof_btn;
   var activated;
   var back;
   var build_txt;
   var but;
   var dispatchEvent;
   var flag;
   var front_cb;
   var hash_btn;
   var input_txt;
   var keyFlag;
   var loadedArr;
   var loading_btn;
   var loc_btn;
   var logArr;
   var mode;
   var obstacle_cb;
   var onEnterFrame;
   var output_txt;
   var processArr;
   var processExplorer;
   var process_btn;
   var prof_btn;
   var rbut;
   var scrBar;
   var server_btn;
   var debugFocus = false;
   var maxChars = 500;
   var focus_clear = false;
   var countLog = 0;
   var packMessageNum = 5;
   var alwaysDown = false;
   function DebugPanel()
   {
      super();
      this.front_cb._visible = false;
      this.obstacle_cb._visible = false;
      this._visible = false;
      lol.events.LEventDispatcher.initialize(this);
      Key.addListener(this);
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("tryConnect",this);
      this.XMC.addEventListener("onXML",this);
      this.XMC.addEventListener("onSend",this);
      this.XMC.addEventListener("onConnect",this);
      this.XMC.addEventListener("onClose",this);
      this.XMC.addEventListener("failed",this);
      this.XMC.addEventListener("hello",this);
      this.swapDepths(1000);
      this.W = 400;
      this.H = 300;
      this.resizeWindow();
      this.open();
      this.but.flag = true;
      this.but.onPress = function()
      {
         this.flag = !this.flag;
         if(this.flag)
         {
            this._parent.open();
         }
         else
         {
            this._parent.close();
         }
      };
      this.rbut.onPress = mx.utils.Delegate.create(this,this.startResizeWindow);
      this.rbut.onRelease = this.rbut.onReleaseOutside = mx.utils.Delegate.create(this,this.fixWindow);
      this.onEnterFrame = this.init;
      this.build_txt.text = "Client: " + this.version + "; swf: " + _root.vversion;
      this.logArr = new Array();
      this.processArr = new Array();
   }
   function focusFunc()
   {
      this.input_txt.onKillFocus = function(newFocus)
      {
         lol.core.SceneShifter.hotKeyManager.enabled = true;
      };
      this.input_txt.onSetFocus = function(oldFocus)
      {
         lol.core.SceneShifter.hotKeyManager.enabled = false;
      };
      this.output_txt.onKillFocus = function(newFocus)
      {
         this._parent.focus_clear = false;
         this._parent.killFunc();
      };
      this.output_txt.onSetFocus = function(oldFocus)
      {
         this._parent.focus_clear = true;
         this._parent.initFunc();
      };
   }
   function initFunc()
   {
      lol.core.SceneShifter.hotKeyManager.addFilter("debug");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.BACKSPACE,this,this.backspace);
   }
   function killFunc()
   {
      lol.core.SceneShifter.hotKeyManager.removeFilter("debug");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.BACKSPACE,this,this.backspace);
   }
   function init()
   {
      delete this.onEnterFrame;
      this.H = this.rbut._y;
      this.scrBar.target = this.output_txt;
      this.resizeWindow();
      this.server_btn.label = "log";
      this.scrBar.addEventListener(lol.gpui.controls.ScrollBar.POSITION,this);
      var _loc3_ = new lol.utils.Timeout(this,this.focusFunc,500);
      this.server_btn.onPress = function()
      {
         this._parent.logLoading();
      };
      this.processExplorer = lol.utils.ProcessExplorer._ref;
      this.process_btn.label = "objects";
      this.process_btn.onPress = function()
      {
         this._parent.mode = "process";
         this._parent.output_txt.text = "";
         this._parent.XMC.removeEventListener("onXML",this._parent);
         lol.utils.ProcessExplorer._ref.addEventListener("refreshList",this._parent);
      };
      this.prof_btn.label = "zlist";
      this.prof_btn.onPress = mx.utils.Delegate.create(this,this.showZList);
      this.a_prof_btn.label = "all";
      this.a_prof_btn.onPress = function()
      {
         this._parent.mode = "all";
         this._parent.output_txt.text = "";
      };
      this.loading_btn.label = "Load";
      this.loading_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.loadingSourses);
      this.hash_btn.label = "Hash";
      this.hash_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.hash);
      this.loc_btn.label = "Loc";
      this.loc_btn.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.locChange);
      this.front_cb.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.showFronts);
      this.obstacle_cb.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.showObstacles);
      this.input_txt.onKillFocus = function(newFocus)
      {
         this._parent.debugFocus = false;
      };
      this.input_txt.onSetFocus = function(oldFocus)
      {
         this._parent.debugFocus = true;
      };
      var _loc2_ = lol.core.Master.getInstance().locGen;
      _loc2_.addEventListener("locLoaded",this);
   }
   function logLoading()
   {
      this.countLog = 0;
      this.output_txt.text = "";
      this.server_btn._enabled = false;
      this.process_btn._enabled = false;
      this.prof_btn._enabled = false;
      this.loc_btn._enabled = false;
      this.loading_btn._enabled = false;
      this.hash_btn._enabled = false;
      this.onEnterFrame = this.logOnEnterFrame;
   }
   function logOnEnterFrame()
   {
      var _loc2_ = this.countLog;
      var _loc3_;
      while(_loc2_ < this.countLog + this.packMessageNum)
      {
         _loc3_ = this.logArr[_loc2_];
         if(_loc3_)
         {
            this.Output(_loc2_ + ". " + _loc3_.mess,_loc3_.from);
         }
         _loc2_ = _loc2_ + 1;
      }
      this.countLog += this.packMessageNum;
      var _loc4_ = Math.round(this.countLog * 100 / this.logArr.length);
      this.server_btn.label = _loc4_ + "%";
      this.scrBar.setPosition(100);
      if(this.countLog >= this.logArr.length)
      {
         this.server_btn._enabled = true;
         this.process_btn._enabled = true;
         this.prof_btn._enabled = true;
         this.loc_btn._enabled = true;
         this.loading_btn._enabled = true;
         this.hash_btn._enabled = true;
         this.XMC.addEventListener("onXML",this);
         this.mode = "log";
         this.server_btn.label = "Log";
         delete this.onEnterFrame;
      }
   }
   function locLoaded(obj)
   {
      var _loc4_;
      var _loc3_;
      var _loc2_;
      if(this.mode == "loc")
      {
         this.output_txt.text = "";
         _loc4_ = lol.core.Master.getInstance().currentLocation.locInfo;
         this.Output("Location " + _loc4_.sourceName + " loaded","CLIENT");
         _loc3_ = obj.list;
         _loc2_ = 0;
         while(_loc2_ < _loc3_.length)
         {
            this.Output(_loc3_[_loc2_],"");
            _loc2_ = _loc2_ + 1;
         }
      }
   }
   function locChange(obj)
   {
      this.mode = "loc";
      var _loc2_ = this.loadedArr;
      this.locLoaded({list:_loc2_});
   }
   function showFronts()
   {
      if(this.front_cb.toggled)
      {
         lol.core.SceneShifter.locationScreen.displayLoc.lBuilder.createFrontHex();
      }
      else
      {
         lol.core.SceneShifter.locationScreen.displayLoc.lBuilder.clearFronts();
      }
   }
   function showObstacles()
   {
      if(this.obstacle_cb.toggled)
      {
         lol.core.SceneShifter.locationScreen.displayLoc.lBuilder.showObstacles();
      }
      else
      {
         lol.core.SceneShifter.locationScreen.displayLoc.lBuilder.clearObstacles();
      }
   }
   function backspace()
   {
      if(this.focus_clear)
      {
         this.output_txt.text = "";
      }
   }
   function refreshList(obj)
   {
      this.output_txt.text = "process: (" + obj.list.length + ")\r\n";
      for(var _loc3_ in obj.list)
      {
         this.output_txt.text += obj.list[_loc3_].spt + ": " + obj.list[_loc3_].name + "\r";
      }
   }
   function onKeyDown()
   {
      if(Key.isDown(13))
      {
         if(this.activated)
         {
            this.Input();
         }
      }
      if(Key.isDown(16))
      {
         this.keyFlag = true;
      }
   }
   function onKeyUp()
   {
      this.keyFlag = false;
   }
   function onSend(obj)
   {
      var _loc4_ = obj.t0;
      var _loc2_ = "t0: " + _loc4_ + ";  " + obj.data;
      var _loc3_ = "CLIENT";
      this.addToLog(_loc2_,_loc3_);
      if(this.mode == "log")
      {
         this.Output(_loc2_,_loc3_);
      }
   }
   function addToLog(mess, from)
   {
      this.logArr.push({mess:mess,from:from,time:getTimer()});
      if(this.logArr.length > this.maxChars)
      {
         this.logArr.shift();
      }
   }
   function trace(mess)
   {
      this.logArr.push({mess:mess,from:"TRACE",time:getTimer()});
      if(this.logArr.length > this.maxChars)
      {
         this.logArr.shift();
      }
   }
   function tryConnect(obj)
   {
      this.Output("Try connect to " + obj.host + " port:" + obj.port,"CLIENT");
   }
   function onConnect(obj)
   {
      var _loc2_ = "Connected to " + lol.core.Master.getInstance().session.host + " port:" + lol.core.Master.getInstance().session.port;
      var _loc3_ = "CLIENT";
      this.Output(_loc2_,_loc3_);
      this.addToLog(_loc2_,_loc3_);
   }
   function onClose(obj)
   {
      var _loc2_ = "Connection closed";
      var _loc3_ = "CLIENT";
      this.Output(_loc2_,_loc3_);
      this.addToLog(_loc2_,_loc3_);
   }
   function failed(obj)
   {
      var _loc2_ = "Connection failed";
      var _loc3_ = "CLIENT";
      this.Output(_loc2_,_loc3_);
      this.addToLog(_loc2_,_loc3_);
   }
   function onXML(obj)
   {
      var _loc4_ = obj.t0;
      var _loc2_ = "t0: " + _loc4_ + ";  " + obj.data;
      var _loc3_ = "SERVER";
      this.addToLog(_loc2_,_loc3_);
      if(this.mode == "log")
      {
         this.Output(_loc2_,_loc3_);
      }
   }
   function Output(mess, from)
   {
      var _loc3_ = !from ? "" : from + ": ";
      var _loc2_ = _loc3_ + " -> " + mess + "\r";
      this.output_txt.text += _loc2_;
      if(this.alwaysDown)
      {
         this.scrBar.setPosition(100);
      }
   }
   function position(obj)
   {
      if(obj.pos == 100)
      {
         this.alwaysDown = true;
      }
      else
      {
         this.alwaysDown = false;
      }
   }
   function Input(str)
   {
      var _loc2_;
      if(this.input_txt.text)
      {
         this.dispatchEvent({type:"onInput",text:this.input_txt.text});
         _loc2_ = new lol.server.mess.CSMessage();
         _loc2_.body = this.input_txt.text;
         _loc2_.name = lol.server.filters.Filter.DEFAULT;
         this.XMC.Send(_loc2_);
         this.input_txt.text = "";
      }
   }
   function onMouseDown()
   {
      if(this.hitTest(_root._xmouse,_root._ymouse,false))
      {
         this._alpha = 100;
         this.activated = true;
      }
      else
      {
         this._alpha = 50;
         this.activated = false;
      }
   }
   function open()
   {
      this._x = this.X;
      this._y = this.Y;
      this.input_txt._visible = this.output_txt._visible = true;
      this.but.gotoAndStop(1);
      this.rbut._visible = true;
      this.scrBar._visible = true;
      this.loc_btn._visible = true;
      this.resizeWindow();
      this.build_txt._visible = true;
      this.back.onPress = function()
      {
         var _loc2_ = lol.core.SceneShifter.main.getNextHighestDepth();
         this._parent.swapDepths(_loc2_);
         this._parent.startDrag();
      };
      this.back.onRelease = this.back.onReleaseOutside = function()
      {
         this._parent.stopDrag();
      };
   }
   function close()
   {
      this.X = this._x;
      this.Y = this._y;
      this.W = this._width;
      this.H = this._height;
      this.input_txt._visible = this.output_txt._visible = false;
      this.build_txt._visible = false;
      this.but.gotoAndStop(2);
      this.but._x = this.W;
      this.but._y = 5;
      this.rbut._visible = false;
      this.scrBar._visible = false;
      this.back.clear();
      lol.utils.Draw.drawFillRect(this.back,0,0,this.W + 20,25,1,11184810,100,16777215,100);
      this._x = 0;
      this._y = 0;
      this.loc_btn._visible = false;
      this.front_cb._visible = false;
      this.obstacle_cb._visible = false;
      this.mode = "closed";
      this.output_txt.text = "";
      delete this.back.onPress;
      delete this.back.onRelease;
      delete this.back.onReleaseOutside;
   }
   function startResizeWindow()
   {
      this.rbut.startDrag(false,50,50,1800,800);
      this.rbut.onMouseMove = mx.utils.Delegate.create(this,this.resizeWindow);
   }
   function resizeWindow()
   {
      var _loc3_ = 5;
      var _loc2_ = 5;
      this.W = this.rbut._x;
      this.H = this.rbut._y;
      this.back.clear();
      lol.utils.Draw.drawFillRect(this.back,0,0,this.W + 20,this.H + 20,1,11184810,100,16777215,100);
      this.but._x = this.W;
      this.but._y = _loc2_;
      this.scrBar._x = this.W;
      this.scrBar._y = 24;
      this.scrBar.setSize(this.H - 30);
      this.scrBar.drawBorder();
      this.output_txt._x = _loc3_;
      this.output_txt._y = _loc2_ + 10;
      this.output_txt._width = this.W - 20;
      this.output_txt._height = this.H - 3 * _loc3_ - this.input_txt._height;
      this.input_txt._x = _loc3_;
      this.input_txt._y = 2 * _loc2_ + this.output_txt._height;
      this.input_txt._width = this.W - 20;
      this.build_txt._y = this.input_txt._y + this.input_txt._height;
   }
   function fixWindow()
   {
      this.rbut.stopDrag();
      delete this.rbut.onMouseMove;
   }
   function hello(obj)
   {
      var _loc3_ = obj.param.build_dt;
      this.build_txt.text = "central build: " + _loc3_ + ";    Client: " + this.version + "; swf: " + _root.vversion;
   }
   function get version()
   {
      var _loc1_;
      return _loc1_;
   }
   function showZList()
   {
      var _loc6_ = lol.core.SceneShifter.locationScreen.displayLoc.depthManager.getList();
      this.output_txt.text = "";
      var _loc3_ = 0;
      var _loc2_;
      var _loc4_;
      var _loc5_;
      while(_loc3_ < _loc6_.length)
      {
         _loc2_ = _loc6_[_loc3_];
         _loc4_ = !_loc2_.resID ? _loc2_.sprite.id : _loc2_.resID + ":" + _loc2_.minD;
         _loc5_ = _loc3_ + ":  " + _loc4_;
         this.Output(_loc5_,"");
         _loc3_ = _loc3_ + 1;
      }
   }
   function loadingSourses()
   {
      this.mode = "loading";
      this.output_txt.text = "";
      var _loc2_ = 0;
      while(_loc2_ < this.loadedArr.length)
      {
         this.output_txt.htmlText += this.loadedArr[_loc2_] + "\r";
         _loc2_ = _loc2_ + 1;
      }
   }
   function hash()
   {
      var _loc2_ = lol.core.Master.getInstance().session.hash;
      this.output_txt.text = "";
      this.output_txt.htmlText = _loc2_;
   }
   function loadingReport(mess)
   {
      if(!this.loadedArr)
      {
         this.loadedArr = new Array();
      }
      if(this.loadedArr.length > 500)
      {
         this.loadedArr.shift();
      }
      this.loadedArr.push(getTimer() + ": " + mess);
      if(this.mode == "loading")
      {
         this.output_txt.htmlText += getTimer() + ": " + mess + "\r";
      }
   }
   function processComplete(obj)
   {
      var _loc2_ = obj.process;
      var _loc3_ = _loc2_.callArray.length - 1;
      var _loc4_ = _loc2_.callArray[_loc3_];
      var _loc5_ = _loc2_.name + ": dt=" + _loc4_ + "; c:" + _loc2_.count;
      this.processArr.push({mess:_loc5_,from:""});
      if(this.processArr.length > this.maxChars)
      {
         this.processArr.shift();
      }
   }
   function testLoading()
   {
      var _loc4_ = this.createEmptyMovieClip("newspaper",this.getNextHighestDepth());
      _loc4_._x = -300;
      var _loc2_ = new Object();
      _loc2_.onLoadStart = mx.utils.Delegate.create(this,this.loadStart);
      _loc2_.onLoadComplete = mx.utils.Delegate.create(this,this.loadComplete);
      _loc2_.onLoadInit = mx.utils.Delegate.create(this,this.loadInit);
      var _loc3_ = new MovieClipLoader();
      _loc3_.addListener(_loc2_);
      _loc3_.loadClip("http://res.lava-online.ru/res/avatars/0_1.swf",_loc4_);
   }
   function loadStart(target_mc)
   {
      target_mc.startTimer = getTimer();
   }
   function loadComplete(target_mc)
   {
      target_mc.completeTimer = getTimer();
   }
   function loadInit(target_mc)
   {
      var _loc3_ = target_mc.completeTimer - target_mc.startTimer;
      target_mc.createTextField("timer_txt",target_mc.getNextHighestDepth(),0,target_mc._height,target_mc._width,22);
      target_mc.timer_txt.text = "loaded in " + _loc3_ + " ms.";
      this.loadingReport("ok. TEST LOADING");
   }
}
