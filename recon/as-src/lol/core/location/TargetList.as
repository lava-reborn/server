class lol.core.location.TargetList
{
   var currentTarget;
   var dispatchEvent;
   var target_list;
   static var KEY_LEFT_SQUARE_BRACKET = 219;
   static var KEY_RIGHT_SQUARE_BRACKET = 221;
   function TargetList()
   {
      this.target_list = new Array();
      lol.events.LEventDispatcher.initialize(this);
      Key.addListener(this);
   }
   function addTarget(id)
   {
      var _loc2_ = this.getTargetIndex(id);
      if(_loc2_ == null)
      {
         this.target_list.push(id);
      }
   }
   function removeTarget(id)
   {
      var _loc2_ = this.getTargetIndex(id);
      this.target_list.splice(_loc2_,1);
   }
   function nextTarget()
   {
      var _loc2_ = this.getTargetIndex(this.currentTarget);
      _loc2_ = _loc2_ + 1;
      if(_loc2_ >= this.target_list.length)
      {
         _loc2_ = 0;
      }
      this.currentTarget = this.target_list[_loc2_];
      if(this.currentTarget != undefined)
      {
         this.dispatchEvent({type:"change",targetID:this.currentTarget});
      }
      return this.currentTarget;
   }
   function prevTarget()
   {
      var _loc2_ = this.getTargetIndex(this.currentTarget);
      _loc2_ = _loc2_ - 1;
      if(_loc2_ < 0)
      {
         _loc2_ = this.target_list.length - 1;
      }
      this.currentTarget = this.target_list[_loc2_];
      if(this.currentTarget != undefined)
      {
         this.dispatchEvent({type:"change",targetID:this.currentTarget});
      }
      return this.currentTarget;
   }
   function onKeyDown()
   {
      var _loc2_;
      if(Key.getCode() == lol.core.location.TargetList.KEY_LEFT_SQUARE_BRACKET)
      {
         _loc2_ = this.prevTarget();
      }
      if(Key.getCode() == lol.core.location.TargetList.KEY_RIGHT_SQUARE_BRACKET)
      {
         _loc2_ = this.nextTarget();
      }
   }
   function get length()
   {
      return this.target_list.length;
   }
   function getTargetList()
   {
      return this.target_list;
   }
   function getTargetIndex(id)
   {
      var _loc2_;
      var _loc3_ = this.target_list.length;
      _loc2_ = 0;
      while(_loc2_ < _loc3_)
      {
         if(this.target_list[_loc2_] == id)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return null;
   }
}
