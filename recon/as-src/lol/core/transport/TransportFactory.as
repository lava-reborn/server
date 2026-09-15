class lol.core.transport.TransportFactory
{
   var XMC;
   static var callStack;
   static var transStore;
   static var _ref = new lol.core.transport.TransportFactory();
   static var callCount = 0;
   static var packageLength = 5;
   function TransportFactory()
   {
      lol.core.transport.TransportFactory.transStore = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ts_si",this);
      lol.core.transport.TransportFactory.callStack = new Array();
   }
   static function requestSI(typeID)
   {
      var _loc1_;
      if(typeID)
      {
         _loc1_ = new lol.server.mess.CSM_TS_get_si(typeID);
         lol.core.transport.TransportFactory.addCall(_loc1_);
      }
   }
   static function addCall(mess)
   {
      lol.core.transport.TransportFactory.callStack.push(mess);
      if(lol.core.transport.TransportFactory.callCount < lol.core.transport.TransportFactory.packageLength)
      {
         lol.core.transport.TransportFactory.sendCall();
      }
   }
   static function sendCall()
   {
      var _loc1_;
      if(lol.core.transport.TransportFactory.callStack.length > 0)
      {
         lol.core.transport.TransportFactory.callCount++;
         _loc1_ = lol.core.transport.TransportFactory.callStack.shift();
         lol.core.transport.TransportFactory._ref.XMC.Send(_loc1_);
      }
   }
   static function updateCall()
   {
      lol.core.transport.TransportFactory.callCount--;
      if(lol.core.transport.TransportFactory.callCount <= lol.core.transport.TransportFactory.packageLength)
      {
         lol.core.transport.TransportFactory.sendCall();
      }
   }
   function ts_si(obj)
   {
      var _loc3_ = obj.param.typeID;
      this.initializeItem(obj);
      lol.core.transport.TransportFactory.updateCall();
   }
   function initializeItem(obj)
   {
      var _loc2_ = obj.param.type;
      var _loc1_ = lol.core.transport.TransportFactory.transStore[_loc2_];
      if(_loc1_)
      {
         _loc1_.initialize(obj.param);
      }
   }
   static function create(typeID)
   {
      var _loc2_;
      if(!lol.core.transport.TransportFactory.transStore[typeID])
      {
         _loc2_ = lol.core.transport.TransportFactory.createTransObject(typeID);
         lol.core.transport.TransportFactory.requestSI(typeID);
         return _loc2_;
      }
      return lol.core.transport.TransportFactory.transStore[typeID];
   }
   static function createTransObject(typeID)
   {
      var _loc1_ = new lol.core.transport.TransObject(typeID);
      lol.core.transport.TransportFactory.transStore[typeID] = _loc1_;
      return _loc1_;
   }
}
