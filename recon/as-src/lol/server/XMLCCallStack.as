class lol.server.XMLCCallStack
{
   var XMC;
   var commandList;
   var evtStr;
   static var callList;
   function XMLCCallStack(evt)
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener(evt,this,this.processCommand);
      this.commandList = new Array();
      this.evtStr = evt;
   }
   static function addCall(evtType, obj, func, data)
   {
      if(!lol.server.XMLCCallStack.callList)
      {
         lol.server.XMLCCallStack.callList = new Array();
      }
      if(!lol.server.XMLCCallStack.callList[evtType])
      {
         lol.server.XMLCCallStack.callList[evtType] = new lol.server.XMLCCallStack(evtType);
      }
      lol.server.XMLCCallStack.callList[evtType].addCommand(obj,func,data);
   }
   static function skipCall(evtType, obj, func)
   {
      lol.server.XMLCCallStack.callList[evtType].skipCommand(obj,func);
   }
   static function clear()
   {
      var _loc1_;
      for(var _loc2_ in lol.server.XMLCCallStack.callList)
      {
         _loc1_ = lol.server.XMLCCallStack.callList[_loc2_];
         _loc1_.clearStack();
      }
      lol.server.XMLCCallStack.callList = null;
   }
   function addCommand(obj, func, data)
   {
      var _loc2_ = new Object();
      _loc2_.handler = obj;
      _loc2_.handlerFunc = func;
      _loc2_.data = data;
      this.commandList.push(_loc2_);
      this.XMC.dispatchEvent({type:"cclength"});
   }
   function processCommand(evt_obj)
   {
      var _loc2_ = this.commandList.shift();
      var _loc3_ = _loc2_.handler;
      var _loc4_ = _loc2_.handlerFunc;
      var _loc5_ = _loc2_.data;
      var _loc6_ = evt_obj.param;
      _loc4_.apply(_loc3_,[{param:_loc6_,data:_loc5_}]);
      this.XMC.dispatchEvent({type:"cclength"});
   }
   function skipCommand(obj, func)
   {
      for(var _loc4_ in this.commandList)
      {
         if(this.commandList[_loc4_].handler == obj && this.commandList[_loc4_].handlerFunc == func)
         {
            this.commandList.splice(Number(_loc4_),1);
            break;
         }
      }
      this.XMC.dispatchEvent({type:"cclength"});
   }
   function clearStack()
   {
      this.XMC.removeEventListener(this.evtStr,this,this.processCommand);
      this.commandList = null;
   }
}
