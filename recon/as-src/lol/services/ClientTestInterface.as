class lol.services.ClientTestInterface extends lol.gpui.GPUIObject
{
   function ClientTestInterface()
   {
      super();
      var _loc4_ = lol.core.SceneShifter.clientTest.testFunction_arr;
      var _loc5_ = _loc4_.length;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc5_)
      {
         _loc3_ = _loc4_[_loc2_];
         _loc2_ = _loc2_ + 1;
      }
   }
}
