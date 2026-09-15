class lol.core.location.LocDeclaration
{
   static var hexWidth = 40;
   static var hexHeight = 0.8660254037844386 * lol.core.location.LocDeclaration.hexWidth;
   static var k = 0.4330127018922193;
   static var cellH = lol.core.location.LocDeclaration.hexWidth * 3 / 8;
   function LocDeclaration()
   {
   }
   static function abstractToReal(point)
   {
      var _loc4_ = point.x;
      var _loc3_ = point.y;
      var _loc2_ = lol.core.location.LocDeclaration.hexWidth * _loc4_;
      var _loc1_ = lol.core.location.LocDeclaration.k * lol.core.location.LocDeclaration.hexWidth * _loc3_;
      return {x:_loc2_,y:_loc1_};
   }
   static function realToAbstract(point)
   {
      var _loc2_ = point.x;
      var _loc1_ = point.y;
      var _loc4_ = _loc2_ / lol.core.location.LocDeclaration.hexWidth;
      var _loc3_ = _loc1_ / (lol.core.location.LocDeclaration.k * lol.core.location.LocDeclaration.hexWidth);
      return {x:_loc4_,y:_loc3_};
   }
   static function realToGrid(point)
   {
      var _loc5_ = point.x;
      var _loc3_ = point.y;
      var _loc2_ = Math.floor(_loc3_ / lol.core.location.LocDeclaration.cellH);
      var _loc6_ = _loc3_ - _loc2_ * lol.core.location.LocDeclaration.cellH - 0.5 * lol.core.location.LocDeclaration.cellH;
      var _loc1_;
      var _loc10_;
      var _loc4_;
      var _loc9_;
      if(Math.abs(_loc6_) > lol.core.location.LocDeclaration.cellH / 6)
      {
         _loc1_ = _loc6_ >= 0 ? (_loc1_ = 1) : (_loc1_ = 0);
         _loc10_ = "";
      }
      else
      {
         _loc4_ = _loc5_ - lol.core.location.LocDeclaration.hexWidth * 0.5 * (_loc2_ % 2);
         _loc10_ = lol.core.location.LocDeclaration.hexWidth * 0.5 - Math.abs(_loc4_ - Math.floor((_loc4_ + lol.core.location.LocDeclaration.hexWidth * 0.5) / lol.core.location.LocDeclaration.hexWidth) * lol.core.location.LocDeclaration.hexWidth);
         _loc9_ = _loc3_ - _loc2_ * lol.core.location.LocDeclaration.cellH - lol.core.location.LocDeclaration.cellH / 3;
         _loc9_ <= Math.abs(_loc10_ / 4) ? (_loc1_ = 0) : (_loc1_ = 1);
      }
      var _loc7_ = _loc2_ + _loc1_;
      var _loc8_ = 0.5 * (_loc7_ % 2);
      var _loc11_ = Math.floor(_loc5_ / lol.core.location.LocDeclaration.hexWidth - _loc8_ + 0.5);
      return {x:_loc11_,y:_loc7_};
   }
}
