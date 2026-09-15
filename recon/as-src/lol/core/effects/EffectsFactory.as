class lol.core.effects.EffectsFactory
{
   var XMC;
   static var callStack;
   static var fxStore;
   static var _ref = new lol.core.effects.EffectsFactory();
   static var callCount = 0;
   static var packageLength = 5;
   function EffectsFactory()
   {
      lol.core.effects.EffectsFactory.fxStore = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("e_si",this);
      this.XMC.addEventListener("e_di",this);
      lol.core.effects.EffectsFactory.callStack = new Array();
   }
   function kill()
   {
      this.XMC.removeEventListener("e_si",this);
      this.XMC.removeEventListener("e_di",this);
   }
   static function requestSI(typeID)
   {
      var _loc1_;
      if(typeID)
      {
         _loc1_ = new lol.server.mess.CSM_E_get_si(typeID);
         lol.core.effects.EffectsFactory.addCall(_loc1_);
      }
   }
   static function addCall(mess)
   {
      lol.core.effects.EffectsFactory.callStack.push(mess);
      if(lol.core.effects.EffectsFactory.callCount < lol.core.effects.EffectsFactory.packageLength)
      {
         lol.core.effects.EffectsFactory.sendCall();
      }
   }
   static function sendCall()
   {
      var _loc1_;
      if(lol.core.effects.EffectsFactory.callStack.length > 0)
      {
         lol.core.effects.EffectsFactory.callCount++;
         _loc1_ = lol.core.effects.EffectsFactory.callStack.shift();
         lol.core.effects.EffectsFactory._ref.XMC.Send(_loc1_);
      }
   }
   static function updateCall()
   {
      lol.core.effects.EffectsFactory.callCount--;
      if(lol.core.effects.EffectsFactory.callCount <= lol.core.effects.EffectsFactory.packageLength)
      {
         lol.core.effects.EffectsFactory.sendCall();
      }
   }
   function e_si(obj)
   {
      var _loc3_ = obj.param.type;
      this.initializeEffect(obj);
      lol.core.effects.EffectsFactory.updateCall();
   }
   function initializeEffect(obj)
   {
      var _loc2_ = obj.param.type;
      var _loc1_ = lol.core.effects.EffectsFactory.fxStore[_loc2_];
      if(!_loc1_)
      {
         _loc1_ = lol.core.effects.EffectsFactory.createProtoEffect(_loc2_);
      }
      _loc1_.initialize(obj.param,true);
      _loc1_.inited = true;
   }
   static function createProtoEffect(em, typeID)
   {
      var _loc2_;
      if(!lol.core.effects.EffectsFactory.fxStore[typeID])
      {
         _loc2_ = lol.core.effects.EffectsFactory.createEmptyEffectObject(em,typeID);
         lol.core.effects.EffectsFactory.requestSI(typeID);
         return _loc2_;
      }
      return lol.core.effects.EffectsFactory.fxStore[typeID];
   }
   static function createEmptyEffectObject(em, typeID)
   {
      var _loc1_ = new lol.core.effects.Effect(em,typeID);
      lol.core.effects.EffectsFactory.fxStore[typeID] = _loc1_;
      return _loc1_;
   }
   static function createRealEffect(em, typeID, notRequestDI, mobID, needUpdateEvent)
   {
      var _loc2_ = lol.core.effects.EffectsFactory.createProtoEffect(em,typeID);
      var _loc1_;
      if(_loc2_)
      {
         _loc1_ = new lol.core.effects.Effect(em,typeID);
         _loc1_.initialize(_loc2_,needUpdateEvent);
         if(!notRequestDI && mobID == 0)
         {
            lol.core.effects.EffectsFactory.requestDI(typeID,mobID);
         }
         return _loc1_;
      }
      return undefined;
   }
   static function getWhatWeHave()
   {
   }
   static function requestDI(typeID, mobID)
   {
      var _loc1_ = new lol.server.mess.CSM_E_get_di(typeID,mobID);
      lol.core.effects.EffectsFactory.addCall(_loc1_);
   }
   function e_di(obj)
   {
      var _loc2_ = obj.param.type;
      var _loc1_ = obj.param.mobi_id;
      if(_loc1_ && _loc1_ != 0)
      {
         return undefined;
      }
      if(lol.core.effects.EffectsFactory.fxStore[_loc2_])
      {
         lol.core.effects.EffectsFactory.fxStore[_loc2_].updateProperties(obj.param,true);
         lol.core.effects.EffectsFactory.updateCall();
      }
   }
}
