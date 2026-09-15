class lol.services.ClientTest
{
   var testFunction_arr;
   function ClientTest()
   {
      this.testFunction_arr = new Array();
   }
   function addFunctionTest(name, type, functionName, place, param0, param1)
   {
      var _loc2_ = new lol.services.ClientTestObject();
      _loc2_.name = name;
      var _loc5_;
      var _loc3_;
      var _loc4_;
      var _loc6_;
      if(type == "returnFunction")
      {
         _loc5_ = getTimer();
         _loc3_ = place[functionName + "_old"](param0,param1);
         _loc2_.oldTime = getTimer() - _loc5_;
         _loc4_ = getTimer();
         _loc6_ = place[functionName + "_new"](param0,param1);
         _loc2_.newTime = getTimer() - _loc4_;
         _loc2_.checkReturnObject = this.checkReturnObject(_loc3_,_loc6_);
         this.testFunction_arr.push(_loc2_);
         return _loc3_;
      }
   }
   function checkReturnObject(oldReturnObj, newReturnObj)
   {
      var _loc2_;
      var _loc1_;
      if(typeof oldReturnObj == "object")
      {
         _loc2_ = oldReturnObj.length;
         _loc1_ = 0;
         while(_loc1_ < _loc2_)
         {
            if(oldReturnObj[_loc1_] != newReturnObj[_loc1_])
            {
               return false;
            }
            _loc1_ = _loc1_ + 1;
         }
         return true;
      }
   }
}
