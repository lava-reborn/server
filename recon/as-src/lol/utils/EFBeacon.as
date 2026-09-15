class lol.utils.EFBeacon extends MovieClip
{
   var OEFF_arr;
   var onEnterFrame;
   var target;
   function EFBeacon()
   {
      super();
      this.OEFF_arr = new Array();
      this.target.newEnterFrame = mx.utils.Delegate.create(this,this.newEnterFrame);
      this.target.deleteEnterFrame = mx.utils.Delegate.create(this,this.deleteEnterFrame);
   }
   static function initialize(this_mc)
   {
      var _loc1_ = this_mc.createEmptyMovieClip("___oEnterFrameBeacon",-1);
      var _loc2_ = lol.utils.EFBeacon;
      _loc1_.__proto__ = _loc2_.prototype;
      _loc1_.target = this_mc;
      _loc2_.call(_loc1_);
      return lol.utils.EFBeacon(_loc1_);
   }
   function newEnterFrame(f)
   {
      var _loc3_;
      if(typeof f == "string")
      {
         _loc3_ = this.target[f];
      }
      else if(typeof f == "function")
      {
         _loc3_ = f;
      }
      for(var _loc4_ in this.OEFF_arr)
      {
         if(_loc3_ == this.OEFF_arr[_loc4_].func)
         {
            return undefined;
         }
      }
      var _loc5_;
      if(_loc3_)
      {
         _loc5_ = this.OEFF_arr.length;
         this.OEFF_arr[_loc5_] = new Object();
         this.OEFF_arr[_loc5_].func = _loc3_;
         if(arguments.length > 1)
         {
            arguments.splice(0,1);
            this.OEFF_arr[_loc5_].param = arguments;
         }
         if(!this.onEnterFrame)
         {
            this.onEnterFrame = this.applyOEF;
         }
         return _loc3_;
      }
   }
   function deleteEnterFrame(f)
   {
      if(!f)
      {
         this.deleteAll();
         return undefined;
      }
      var _loc2_;
      if(typeof f == "string")
      {
         _loc2_ = this.target[f];
      }
      else if(typeof f == "function")
      {
         _loc2_ = f;
      }
      if(_loc2_)
      {
         for(var _loc3_ in this.OEFF_arr)
         {
            if(_loc2_ == this.OEFF_arr[_loc3_].func)
            {
               this.OEFF_arr.splice(Number(_loc3_),1);
               if(this.OEFF_arr.length == 0)
               {
                  delete this.onEnterFrame;
               }
               return undefined;
            }
         }
      }
   }
   function applyOEF()
   {
      for(var _loc2_ in this.OEFF_arr)
      {
         this.OEFF_arr[_loc2_].func.apply(this.target,this.OEFF_arr[_loc2_].param);
      }
   }
   function deleteAll()
   {
      this.OEFF_arr = new Array();
      delete this.onEnterFrame;
   }
}
