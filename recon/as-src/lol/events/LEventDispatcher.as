class lol.events.LEventDispatcher
{
   static var _fEventDispatcher = undefined;
   static var exceptions = {move:1,draw:1,load:1};
   function LEventDispatcher()
   {
   }
   static function _removeEventListener(queue, event, handler, handlerFunc)
   {
      var _loc1_;
      var _loc3_;
      var _loc4_;
      if(queue != undefined)
      {
         for(_loc1_ in queue)
         {
            _loc3_ = queue[_loc1_][0];
            _loc4_ = queue[_loc1_][1];
            if(_loc3_ == handler && handlerFunc == _loc4_)
            {
               queue.splice(_loc1_,1);
               return undefined;
            }
         }
      }
   }
   static function initialize(object)
   {
      if(lol.events.LEventDispatcher._fEventDispatcher == undefined)
      {
         lol.events.LEventDispatcher._fEventDispatcher = new lol.events.LEventDispatcher();
      }
      object.addEventListener = lol.events.LEventDispatcher._fEventDispatcher.addEventListener;
      object.removeEventListener = lol.events.LEventDispatcher._fEventDispatcher.removeEventListener;
      object.dispatchEvent = lol.events.LEventDispatcher._fEventDispatcher.dispatchEvent;
      object.dispatchQueue = lol.events.LEventDispatcher._fEventDispatcher.dispatchQueue;
   }
   function dispatchQueue(queueObj, eventObj)
   {
      var _loc8_ = "__q_" + eventObj.type;
      var _loc3_ = queueObj[_loc8_];
      var _loc4_;
      var _loc1_;
      var _loc5_;
      var _loc2_;
      if(_loc3_ != undefined)
      {
         for(_loc4_ in _loc3_)
         {
            _loc1_ = _loc3_[_loc4_][0];
            _loc5_ = _loc3_[_loc4_][1];
            _loc2_ = typeof _loc1_;
            if(_loc2_ == "object" || _loc2_ == "movieclip")
            {
               _loc5_.apply(_loc1_,[eventObj]);
            }
            else
            {
               _loc1_.apply(queueObj,[eventObj]);
            }
         }
      }
   }
   function dispatchEvent(eventObj)
   {
      if(eventObj.target == undefined)
      {
         eventObj.target = this;
      }
      this[eventObj.type + "Handler"](eventObj);
      this.dispatchQueue(this,eventObj);
   }
   function addEventListener(event, handler, handlerFunc)
   {
      var _loc3_ = "__q_" + event;
      if(this[_loc3_] == undefined)
      {
         this[_loc3_] = new Array();
      }
      var _loc4_ = !handlerFunc ? handler[event] : handlerFunc;
      _global.ASSetPropFlags(this,_loc3_,1);
      lol.events.LEventDispatcher._removeEventListener(this[_loc3_],event,handler,_loc4_);
      this[_loc3_].push([handler,_loc4_]);
   }
   function removeEventListener(event, handler, handlerFunc)
   {
      var _loc4_ = !handlerFunc ? handler[event] : handlerFunc;
      var _loc3_ = "__q_" + event;
      lol.events.LEventDispatcher._removeEventListener(this[_loc3_],event,handler,_loc4_);
   }
}
