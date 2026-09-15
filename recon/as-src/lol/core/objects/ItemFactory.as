class lol.core.objects.ItemFactory
{
   var XMC;
   static var callStack;
   static var itemStore;
   static var itemTypeStore;
   static var _ref = new lol.core.objects.ItemFactory();
   static var callCount = 0;
   static var packageLength = 5;
   function ItemFactory()
   {
      lol.core.objects.ItemFactory.itemStore = new Array();
      lol.core.objects.ItemFactory.itemTypeStore = new Array();
      this.XMC = lol.server.XMLConnection.getInstance();
      this.XMC.addEventListener("ss_si_firearm",this);
      this.XMC.addEventListener("ss_si_heal",this);
      this.XMC.addEventListener("ss_si_wear",this);
      this.XMC.addEventListener("ss_si_ammo",this);
      this.XMC.addEventListener("ss_si_simple_obj",this);
      this.XMC.addEventListener("ss_si_coldarm",this);
      this.XMC.addEventListener("ss_si_trophy",this);
      this.XMC.addEventListener("ss_di_firearm",this);
      this.XMC.addEventListener("ss_di_heal",this);
      this.XMC.addEventListener("ss_di_wear",this);
      this.XMC.addEventListener("ss_di_heap",this);
      this.XMC.addEventListener("ss_di_coldarm",this);
      this.XMC.addEventListener("ss_di_trophy",this);
      lol.core.objects.ItemFactory.callStack = new Array();
   }
   static function requestSI(typeID)
   {
      var _loc1_;
      if(typeID)
      {
         _loc1_ = new lol.server.mess.CSM_SSGetStatInfo(typeID);
         lol.core.objects.ItemFactory.addCall(_loc1_);
      }
   }
   static function addCall(mess)
   {
      lol.core.objects.ItemFactory.callStack.push(mess);
      if(lol.core.objects.ItemFactory.callCount < lol.core.objects.ItemFactory.packageLength && lol.core.Master.getInstance().currentState == lol.core.Master.LOCAL_STATE)
      {
         lol.core.objects.ItemFactory.sendCall();
      }
   }
   static function sendCall()
   {
      var _loc1_;
      if(lol.core.objects.ItemFactory.callStack.length > 0)
      {
         lol.core.objects.ItemFactory.callCount++;
         _loc1_ = lol.core.objects.ItemFactory.callStack.shift();
         lol.core.objects.ItemFactory._ref.XMC.Send(_loc1_);
      }
   }
   static function updateCall()
   {
      lol.core.objects.ItemFactory.callCount--;
      if(lol.core.objects.ItemFactory.callCount <= lol.core.objects.ItemFactory.packageLength)
      {
         lol.core.objects.ItemFactory.sendCall();
      }
   }
   function ss_si_firearm(obj)
   {
      var _loc2_ = lol.core.objects.Item.FIRE_ARM;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_coldarm(obj)
   {
      var _loc2_ = lol.core.objects.Item.COLD_ARM;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_heal(obj)
   {
      var _loc2_ = lol.core.objects.Item.HEAL_ITEM;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_wear(obj)
   {
      var _loc2_ = lol.core.objects.Item.WEAR;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_ammo(obj)
   {
      var _loc2_ = lol.core.objects.Item.AMMO;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_simple_obj(obj)
   {
      var _loc2_ = lol.core.objects.Item.TRASH;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function ss_si_trophy(obj)
   {
      var _loc2_ = lol.core.objects.Item.TROPHY;
      this.initializeItem(obj,_loc2_);
      lol.core.objects.ItemFactory.updateCall();
   }
   function initializeItem(obj, rootID)
   {
      var _loc2_ = obj.param.type;
      var _loc1_ = lol.core.objects.ItemFactory.itemTypeStore[_loc2_];
      var _loc3_;
      if(!_loc1_.item)
      {
         _loc3_ = lol.core.objects.ItemFactory.getClass(rootID);
         _loc1_.item = new _loc3_(0,_loc2_,rootID);
      }
      _loc1_.initialize(obj.param);
   }
   static function requestSD(OID, target)
   {
      var _loc1_ = new lol.server.mess.CSM_SSGetDynInfo(new lol.data.BigUINT(new lol.data.BigUINTCluster(OID)),target);
      lol.core.objects.ItemFactory.addCall(_loc1_);
   }
   function ss_di_firearm(obj)
   {
      this.updateItemDI(obj);
   }
   function ss_di_coldarm(obj)
   {
      this.updateItemDI(obj);
   }
   function ss_di_trophy(obj)
   {
      this.updateItemDI(obj);
   }
   function ss_di_heal(obj)
   {
      this.updateItemDI(obj);
   }
   function ss_di_wear(obj)
   {
      this.updateItemDI(obj);
   }
   function ss_di_heap(obj)
   {
      this.updateItemDI(obj);
   }
   function updateItemDI(obj)
   {
      var _loc1_ = obj.param.obj;
      var _loc2_ = lol.core.objects.ItemFactory.getItem(_loc1_);
      _loc2_.updateProperties(obj.param);
      lol.core.objects.ItemFactory.updateCall();
   }
   static function create(oid, notRequestDI, target)
   {
      var _loc2_;
      var _loc3_;
      var _loc4_;
      var _loc7_;
      var _loc5_;
      var _loc6_;
      if(oid)
      {
         if(!lol.core.objects.ItemFactory.itemStore[oid])
         {
            _loc2_ = lol.utils.MDString.parseBigUINT(oid,4,2);
            _loc3_ = _loc2_[0];
            _loc4_ = _loc2_[1];
            _loc7_ = _loc2_[2];
            _loc5_ = lol.core.objects.ItemFactory.getClass(_loc3_);
            lol.core.objects.ItemFactory.createPrototype(_loc4_,_loc3_);
            _loc6_ = new _loc5_(oid,_loc4_,_loc3_);
            if(!notRequestDI)
            {
               lol.core.objects.ItemFactory.requestSD(oid,target);
            }
            lol.core.objects.ItemFactory.itemStore[oid] = _loc6_;
         }
         return lol.core.objects.ItemFactory.itemStore[oid];
      }
   }
   static function getItem(oid)
   {
      return lol.core.objects.ItemFactory.itemStore[oid];
   }
   function itemUpdate(obj)
   {
   }
   static function getClass(rootID)
   {
      var _loc1_;
      switch(rootID)
      {
         case lol.core.objects.Item.FIRE_ARM:
            _loc1_ = lol.core.objects.FireArm;
            break;
         case lol.core.objects.Item.COLD_ARM:
            _loc1_ = lol.core.objects.MeleeWeapon;
            break;
         case lol.core.objects.Item.WEAR:
            _loc1_ = lol.core.objects.Wear;
            break;
         case lol.core.objects.Item.HEAL_ITEM:
            _loc1_ = lol.core.objects.HealItem;
            break;
         case lol.core.objects.Item.AMMO:
            _loc1_ = lol.core.objects.Ammo;
            break;
         case lol.core.objects.Item.TRASH:
            _loc1_ = lol.core.objects.Trash;
            break;
         case lol.core.objects.Item.TROPHY:
            _loc1_ = lol.core.objects.Trophy;
            break;
         default:
            _loc1_ = lol.core.objects.Item;
      }
      return _loc1_;
   }
   static function createPrototype(typeID, rootID)
   {
      var _loc2_;
      var _loc4_;
      if(!lol.core.objects.ItemFactory.itemTypeStore[typeID])
      {
         _loc2_ = new lol.core.objects.P_Item();
         if(rootID != undefined)
         {
            _loc4_ = lol.core.objects.ItemFactory.getClass(rootID);
            _loc2_.item = new _loc4_(0,typeID,rootID);
         }
         lol.core.objects.ItemFactory.itemTypeStore[typeID] = _loc2_;
         lol.core.objects.ItemFactory.requestSI(typeID);
      }
      return lol.core.objects.ItemFactory.itemTypeStore[typeID];
   }
   static function getProtoItem(typeID)
   {
      return lol.core.objects.ItemFactory.itemTypeStore[typeID].item;
   }
}
