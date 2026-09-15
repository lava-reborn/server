class lol.gpui.GPUIObject extends MovieClip
{
   var __methodTable;
   var initialized;
   var methodTable;
   var onEnterFrame;
   function GPUIObject()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.initialized = true;
   }
   function doLater()
   {
      if(this.methodTable == undefined)
      {
         this.methodTable = new Array();
      }
      var _loc3_;
      if(typeof arguments[0] == "object" || typeof arguments[0] == "movieclip")
      {
         _loc3_ = arguments.shift();
      }
      else
      {
         _loc3_ = this;
      }
      var _loc4_ = arguments[0];
      var _loc5_ = arguments[1];
      if(_loc4_)
      {
         this.methodTable.push({obj:_loc3_,func:_loc4_,param:_loc5_});
         this.onEnterFrame = this.doLaterDispatcher;
      }
   }
   function doLaterDispatcher(Void)
   {
      delete this.onEnterFrame;
      this.__methodTable = this.methodTable;
      this.methodTable = new Array();
      var _loc2_;
      var _loc3_;
      if(this.__methodTable.length > 0)
      {
         while((_loc2_ = this.__methodTable.shift()) != undefined)
         {
            _loc3_ = _loc2_.obj[_loc2_.func];
            _loc3_.apply(_loc2_.obj,_loc2_.param);
         }
      }
   }
}
