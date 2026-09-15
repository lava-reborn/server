class lol.events.EventJacket
{
   var addEventListener;
   var delay;
   var dispatchEvent;
   var func;
   var funcName;
   var interval;
   var onEvent;
   var onEventDelegate;
   var onExecute;
   var paramsArray;
   var removeEventListener;
   var scope;
   var scopeEvent;
   var spt;
   var spt_int;
   var target;
   function EventJacket()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.addEventListener("onEvent",this);
      this.addEventListener("onExecute",this);
      if(arguments.length > 0)
      {
         if(arguments[0] instanceof Array)
         {
            this.init.apply(this,arguments[0]);
         }
         else
         {
            this.init.apply(this,arguments);
         }
      }
   }
   function init()
   {
      if(typeof arguments[0] == "function")
      {
         this._target = null;
      }
      else
      {
         this._target = arguments[0];
         arguments.splice(0,1);
      }
      var _loc5_;
      if(typeof arguments[0] == "string" || typeof arguments[0] == "function")
      {
         this._func = arguments[0];
         this.funcName = arguments[0];
         arguments.splice(0,1);
      }
      else
      {
         _loc5_ = function(o)
         {
            var _loc3_ = arguments.callee.obj;
            for(var _loc4_ in _loc3_)
            {
               this[_loc4_] = _loc3_[_loc4_];
            }
         };
         _loc5_.obj = arguments[0];
         this._func = _loc5_;
      }
      this._params = arguments[0];
      this._delay = arguments[1];
      this.setObserver(arguments[2],arguments[3]);
   }
   function get _target()
   {
      return this.target;
   }
   function set _target(obj)
   {
      this.target = obj;
   }
   function get _func()
   {
      return this.func;
   }
   function set _func(f)
   {
      if(typeof f == "string")
      {
         this.func = this.target[f];
      }
      else
      {
         this.func = f;
      }
   }
   function get _params()
   {
      return this.paramsArray;
   }
   function set _params(arr)
   {
      this.paramsArray = arr;
   }
   function set _delay(del)
   {
      this.delay = del;
   }
   function get _delay()
   {
      return this.delay;
   }
   function setObserver(sc, scEvent)
   {
      if(!sc)
      {
         return undefined;
      }
      if(typeof sc == "string")
      {
         this._scope = this.target;
         this._scopeEvent = sc;
      }
      else
      {
         this._scope = sc;
         this._scopeEvent = scEvent;
      }
   }
   function initObserver()
   {
      this.onEventDelegate = mx.utils.Delegate.create(this,this.reportEvent);
      this._scope.addEventListener(this._scopeEvent,this.onEventDelegate);
   }
   function removeObserver()
   {
      this._scope.removeEventListener(this._scopeEvent,this.onEventDelegate);
   }
   function set _scope(sc)
   {
      this.scope = sc;
   }
   function get _scope()
   {
      return this.scope;
   }
   function set _scopeEvent(scEvent)
   {
      this.scopeEvent = scEvent;
   }
   function get _scopeEvent()
   {
      return this.scopeEvent;
   }
   function Execute()
   {
      if(this._delay > 0)
      {
         clearInterval(this.interval);
         this.interval = setInterval(this,"executeEvent",this._delay);
      }
      else
      {
         this.executeEvent();
      }
   }
   function executeEvent()
   {
      clearInterval(this.interval);
      if(this._scope)
      {
         this.initObserver();
         this.__execute();
      }
      else
      {
         this.__execute();
         this.reportEvent();
      }
   }
   function __execute()
   {
      this._func.apply(this._target,this._params);
      this.dispatchEvent({type:"onExecute"});
   }
   function reportEvent(evt_obj)
   {
      this.removeObserver();
      var _loc3_ = new Object();
      for(var _loc4_ in evt_obj)
      {
         _loc3_[_loc4_] = evt_obj[_loc4_];
      }
      _loc3_.type = "onEvent";
      _loc3_.target = this;
      this.dispatchEvent(_loc3_);
   }
   function kill()
   {
      this.removeEventListener("onEvent",this);
      this.removeEventListener("onExecute",this);
      delete this.onEventDelegate.target;
      delete this.onEventDelegate.func;
      delete this.onEventDelegate;
      delete this.onExecute.target;
      delete this.onExecute.func;
      delete this.onExecute;
      delete this.onEvent.target;
      delete this.onEvent.func;
      delete this.onEvent;
      delete this.target;
      delete this.scope;
      delete this.func;
      this.removeObserver();
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess(this.funcName + "_" + this.spt + " " + this.paramsArray,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
