class lol.utils.LocIdToCoordinate
{
   static var xMask = 67100672;
   static var xShift = 13;
   static var yMask = 8191;
   static var yShift = 0;
   static var zShift = 26;
   function LocIdToCoordinate()
   {
   }
   static function getValue(loc_id)
   {
      var _loc1_ = new Object();
      _loc1_.x = (loc_id & lol.utils.LocIdToCoordinate.xMask) >> lol.utils.LocIdToCoordinate.xShift;
      _loc1_.y = (loc_id & lol.utils.LocIdToCoordinate.yMask) >> lol.utils.LocIdToCoordinate.yShift;
      _loc1_.z = loc_id >> lol.utils.LocIdToCoordinate.zShift;
      return _loc1_;
   }
}
