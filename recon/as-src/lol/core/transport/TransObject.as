class lol.core.transport.TransObject
{
   var _afro_cost;
   var _aggro_mod;
   var _desc;
   var _gold_cost;
   var _name;
   var _speed_mod;
   var descStrID;
   var dispatchEvent;
   var id;
   var nameStrID;
   var res;
   var rootID;
   var typeID;
   static var TRANSPORT = 7;
   var inited = false;
   var premium = 0;
   function TransObject(_ID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.typeID = _ID;
      this.id = _ID;
      this.rootID = lol.core.transport.TransObject.TRANSPORT;
   }
   function initialize(obj)
   {
      this._speed_mod = obj.speed_mod;
      this._aggro_mod = obj.aggro_mod;
      this._gold_cost = obj.g_cost;
      this._afro_cost = obj.cost;
      this.res = obj.res;
      this.premium = obj.premium;
      this.initGSDLStringData(obj);
   }
   function initGSDLStringData(obj)
   {
      this.nameStrID = Number(obj.name);
      this.descStrID = obj.desc == "" ? null : Number(obj.desc);
      this.stringUpdate();
   }
   function stringUpdate(obj)
   {
      var _loc2_ = lol.utils.StringCollector.getInstance();
      var _loc3_ = _loc2_.getString(this.nameStrID);
      var _loc4_ = this.descStrID == null ? new lol.utils.SCString(0,"") : _loc2_.getString(this.descStrID);
      if(_loc3_ && _loc4_)
      {
         _loc2_.removeEventListener("update",this,this.stringUpdate);
         this._name = _loc3_.string;
         this._desc = _loc4_.string;
         this.inited = true;
         this.dispatchEvent({type:lol.core.transport.TransEvent.TRANS_OBJECT_UPDATE});
      }
      else
      {
         _loc2_.addEventListener("update",this,this.stringUpdate);
      }
   }
   function getProp(str)
   {
      var _loc2_ = this[str];
      return _loc2_;
   }
   function get name()
   {
      return this._name;
   }
   function get desc()
   {
      return this._desc;
   }
   function get speed_mod()
   {
      return this._speed_mod;
   }
   function get aggro_mod()
   {
      return this._aggro_mod;
   }
   function get g_cost()
   {
      return this._gold_cost;
   }
   function get cost()
   {
      return this._afro_cost;
   }
}
