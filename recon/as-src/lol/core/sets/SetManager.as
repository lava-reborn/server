class lol.core.sets.SetManager
{
   var XMC;
   static var callStack;
   static var setList;
   static var _ref = new lol.core.sets.SetManager();
   static var callCount = 0;
   static var packageLength = 5;
   function SetManager()
   {
      lol.core.sets.SetManager.callStack = new Array();
      lol.core.sets.SetManager.setList = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_si_set",this);
   }
   static function requestSI(typeID)
   {
      var _loc1_;
      if(typeID)
      {
         _loc1_ = new lol.server.mess.CSM_SSGetSetInfo(typeID);
         lol.core.sets.SetManager.addCall(_loc1_);
      }
   }
   static function addCall(mess)
   {
      lol.core.sets.SetManager.callStack.push(mess);
      if(lol.core.sets.SetManager.callCount < lol.core.sets.SetManager.packageLength)
      {
         lol.core.sets.SetManager.sendCall();
      }
   }
   static function sendCall()
   {
      var _loc1_;
      if(lol.core.sets.SetManager.callStack.length > 0)
      {
         lol.core.sets.SetManager.callCount++;
         _loc1_ = lol.core.sets.SetManager.callStack.shift();
         lol.core.sets.SetManager._ref.XMC.Send(_loc1_);
      }
   }
   static function updateCall()
   {
      lol.core.sets.SetManager.callCount--;
      if(lol.core.sets.SetManager.callCount <= lol.core.sets.SetManager.packageLength)
      {
         lol.core.sets.SetManager.sendCall();
      }
   }
   static function getSet(typeID)
   {
      if(lol.core.sets.SetManager.setList[typeID])
      {
         return lol.core.sets.SetManager.setList[typeID];
      }
      return lol.core.sets.SetManager.createSet(typeID);
   }
   static function createSet(typeID)
   {
      var _loc1_ = new lol.core.sets.SetObject(typeID);
      lol.core.sets.SetManager.setList[typeID] = _loc1_;
      lol.core.sets.SetManager.requestSI(typeID);
      return _loc1_;
   }
   function ss_si_set(obj)
   {
      var _loc1_ = lol.core.sets.SetManager.setList[obj.param.type];
      _loc1_.initSet(obj.param);
      lol.core.sets.SetManager.updateCall();
   }
}
