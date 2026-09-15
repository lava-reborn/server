class lol.core.sets.SetObject
{
   var desc;
   var descStrID;
   var dispatchEvent;
   var name;
   var nameStrID;
   var res;
   var typeID;
   static var UPDATE_SET = "UPDATE_SET";
   var inited = false;
   function SetObject(id)
   {
      this.typeID = id;
      lol.events.LEventDispatcher.initialize(this);
   }
   function initSet(obj)
   {
      this.res = obj.res;
      var _loc5_ = 2;
      var _loc6_;
      var _loc8_;
      var _loc11_;
      var _loc7_;
      var _loc2_;
      var _loc4_;
      while(_loc5_ < 7)
      {
         _loc6_ = 0;
         _loc8_ = obj["bonus_" + _loc5_ + "_attribs_m"];
         _loc11_ = obj["bonus_" + _loc5_ + "_attribs"];
         _loc7_ = 5;
         this["bonus_" + _loc5_ + "_attribs"] = new Array();
         _loc2_ = 0;
         while(_loc2_ < _loc7_)
         {
            _loc4_ = _loc8_ >> _loc2_ & 1;
            if(_loc4_)
            {
               this["bonus_" + _loc5_ + "_attribs"][_loc2_] = _loc11_[_loc6_];
               _loc6_ = _loc6_ + 1;
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      var _loc9_;
      while(_loc5_ < 7)
      {
         _loc6_ = 0;
         _loc8_ = obj["bonus_" + _loc5_ + "_skills_m"];
         _loc9_ = obj["bonus_" + _loc5_ + "_skills"];
         _loc7_ = 5;
         this["bonus_" + _loc5_ + "_skills"] = new Array();
         _loc2_ = 0;
         while(_loc2_ < _loc7_)
         {
            _loc4_ = _loc8_ >> _loc2_ & 1;
            if(_loc4_)
            {
               this["bonus_" + _loc5_ + "_skills"][_loc2_] = _loc9_[_loc6_];
               _loc6_ = _loc6_ + 1;
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      var _loc10_;
      while(_loc5_ < 7)
      {
         _loc6_ = 0;
         _loc8_ = obj["bonus_" + _loc5_ + "_specs_m"];
         _loc10_ = obj["bonus_" + _loc5_ + "_specs"];
         _loc7_ = 15;
         this["bonus_" + _loc5_ + "_specs"] = new Array();
         _loc2_ = 0;
         while(_loc2_ < _loc7_)
         {
            _loc4_ = _loc8_ >> _loc2_ & 1;
            if(_loc4_)
            {
               this["bonus_" + _loc5_ + "_specs"][_loc2_] = _loc10_[_loc6_];
               _loc6_ = _loc6_ + 1;
            }
            _loc2_ = _loc2_ + 1;
         }
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      while(_loc5_ < 7)
      {
         this["bonus_" + _loc5_ + "_hp"] = obj["bonus_" + _loc5_ + "_hp"];
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      while(_loc5_ < 7)
      {
         this["bonus_" + _loc5_ + "_st"] = obj["bonus_" + _loc5_ + "_st"];
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      while(_loc5_ < 7)
      {
         this["bonus_" + _loc5_ + "_od"] = obj["bonus_" + _loc5_ + "_od"];
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      while(_loc5_ < 7)
      {
         this["bonus_" + _loc5_ + "_cp"] = obj["bonus_" + _loc5_ + "_cp"];
         _loc5_ = _loc5_ + 1;
      }
      _loc5_ = 2;
      while(_loc5_ < 7)
      {
         this["bonus_" + _loc5_ + "_ce"] = obj["bonus_" + _loc5_ + "_ce"];
         _loc5_ = _loc5_ + 1;
      }
      this.initGDSLStringData(obj);
      this.inited = true;
      this.dispatchEvent({type:lol.core.sets.SetObject.UPDATE_SET});
   }
   function initGDSLStringData(obj)
   {
      var _loc3_ = lol.utils.StringCollector.getInstance();
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
         this.name = _loc3_.string;
         this.desc = _loc4_.string;
         this.dispatchEvent({type:lol.core.sets.SetObject.UPDATE_SET});
      }
      else
      {
         _loc2_.addEventListener("update",this,this.stringUpdate);
      }
   }
   function getProp(str)
   {
      return this[str];
   }
}
