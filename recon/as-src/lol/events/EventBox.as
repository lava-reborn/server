class lol.events.EventBox
{
   var EventList;
   var addEventListener;
   var dispatchEvent;
   var onEventDelegate;
   function EventBox()
   {
      this.init(arguments);
   }
   function init(arr)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.addEventListener("onExecute",this);
      this.addEventListener("onEvent",this);
      this.onEventDelegate = mx.utils.Delegate.create(this,this.reportEvent);
      this.EventList = new Array();
      for(var _loc3_ in arr)
      {
         if(arr[_loc3_] instanceof lol.events.EventJacket)
         {
            this.EventList.unshift(arr[_loc3_]);
         }
      }
   }
   function addEvent()
   {
      var _loc3_ = this.createNewEvent.apply(this,arguments);
      this.EventList.push(_loc3_);
      return _loc3_;
   }
   function addEventAt()
   {
      var _loc4_ = arguments[0];
      arguments.shift();
      var _loc3_ = this.createNewEvent.apply(this,arguments);
      this.EventList.splice(_loc4_,0,_loc3_);
      return _loc3_;
   }
   function getEvent(i)
   {
      return this.EventList[i];
   }
   function removeEvent(index)
   {
      this.EventList.splice(index,1);
   }
   function createNewEvent()
   {
      var _loc2_;
      if(arguments[0] instanceof lol.events.EventJacket)
      {
         _loc2_ = arguments[0];
      }
      else
      {
         _loc2_ = new lol.events.EventJacket(arguments);
      }
      return _loc2_;
   }
   function clear()
   {
      for(var _loc2_ in this.EventList)
      {
         this.EventList[_loc2_].removeEventListener("onEvent",this.onEventDelegate);
         this.EventList[_loc2_].kill();
         delete this.EventList[_loc2_];
      }
      delete this.onEventDelegate.target;
      delete this.onEventDelegate.func;
      delete this.onEventDelegate;
      delete this.EventList;
   }
   function get length()
   {
      return this.EventList.length;
   }
   function set length(§null§)
   {
   }
   function Execute(i)
   {
      this.EventList[i].addEventListener("onEvent",this.onEventDelegate);
      this.EventList[i].Execute();
      this.dispatchEvent({type:"onExecute",count:i});
   }
   function reportEvent(evt_obj)
   {
      var _loc6_ = evt_obj.target;
      var _loc5_ = evt_obj.type;
      _loc6_.removeEventListener(_loc5_,this.onEventDelegate);
      var _loc3_ = new Object();
      for(var _loc4_ in evt_obj)
      {
         _loc3_[_loc4_] = evt_obj[_loc4_];
      }
      _loc3_.type = "onEvent";
      _loc3_.target = this;
      this.dispatchEvent(_loc3_);
   }
}
