class lol.events.FireEvent
{
   var damagedArray;
   var hits;
   var type;
   static var FIRE_ACK = "fireAck";
   var access = true;
   function FireEvent(_type)
   {
      this.type = !_type ? lol.events.FireEvent.FIRE_ACK : _type;
      this.hits = new Array();
      this.damagedArray = new Array();
   }
   function hitTarget(targetID, dmg, sdmg, crit)
   {
      var _loc2_ = new lol.core.location.FireAck(lol.core.location.FireAck.TARGET);
      _loc2_.targetID = targetID;
      _loc2_.dmg = dmg;
      _loc2_.sdmg = sdmg;
      _loc2_.critical = crit;
      this.hits.push(_loc2_);
      this.damage(_loc2_);
   }
   function hitWall(hex)
   {
      var _loc2_ = new lol.core.location.FireAck(lol.core.location.FireAck.WALL);
      _loc2_.hex = hex;
      this.hits.push(_loc2_);
   }
   function miss(x, y)
   {
      var _loc2_ = new lol.core.location.FireAck(lol.core.location.FireAck.POINT);
      _loc2_.x = x;
      _loc2_.y = y;
      this.hits.push(_loc2_);
   }
   function damage(fAck)
   {
      var _loc2_;
      if(fAck.type == lol.core.location.FireAck.TARGET)
      {
         _loc2_ = this.getFAck(fAck.targetID);
         _loc2_.dmg += fAck.dmg;
         _loc2_.sdmg += fAck.sdmg;
      }
   }
   function getFAck(id)
   {
      var _loc2_;
      for(var _loc4_ in this.damagedArray)
      {
         _loc2_ = this.damagedArray[_loc4_];
         if(_loc2_.targetID == id)
         {
            return _loc2_;
         }
      }
      _loc2_ = new lol.core.location.FireAck(lol.core.location.FireAck.TARGET);
      _loc2_.targetID = id;
      _loc2_.dmg = 0;
      _loc2_.sdmg = 0;
      this.damagedArray.push(_loc2_);
      return _loc2_;
   }
   function getDamaged()
   {
      return this.damagedArray;
   }
   function get successful()
   {
      return this.damagedArray.length > 0;
   }
}
