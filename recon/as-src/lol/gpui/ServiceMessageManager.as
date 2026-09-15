class lol.gpui.ServiceMessageManager
{
   var content;
   var message_arr;
   var stackMessage;
   static var GOLD_MESSAGE_TIMEOUT = 20000;
   var tradeLocation_bool = true;
   var bagOverload_bool = true;
   var MESSAGE_WIDTH = 260;
   var SPAN = 10;
   function ServiceMessageManager()
   {
      this.stackMessage = new Array();
      var _loc2_ = lol.core.SceneShifter.linkWindow;
      this.content = _loc2_.createEmptyMovieClip("serviceMessage_mc",_loc2_.getNextHighestDepth());
      this.message_arr = new Array();
      this.init();
   }
   function init()
   {
      lol.core.SceneShifter._ref.addEventListener("resizeStage",this,this.resizeStage);
      lol.core.SceneShifter._ref.setMCSize();
   }
   function resizeStage(obj)
   {
      this.content._x = (- Stage.width) / 2 + obj.w - this.MESSAGE_WIDTH - 50;
      this.content._y = (- Stage.height) / 2 + obj.h - lol.services.ChatPan.DEFAULT_H - 50;
   }
   function newMessage(label_str, type)
   {
      var _loc3_;
      var _loc2_;
      if(this.message_arr.length <= 4)
      {
         _loc3_ = this.message_arr.length;
         _loc2_ = this.content.attachMovie("serviceMessage","serviceMessage" + _loc3_,this.content.getNextHighestDepth());
         _loc2_.label = label_str;
         _loc2_.type = type;
         _loc2_.id = _loc3_;
         _loc2_.addEventListener(lol.gpui.ServiceMessage.REMOVE_MESSAGE,this,this.removeMessage);
         _loc2_.addEventListener(lol.gpui.ServiceMessage.REMOVE_ALL_MESSAGES,this,this.removeAllMessages);
         this.message_arr.push(_loc2_);
         _loc2_._y = - this.getHeight();
         return _loc2_;
      }
      this.stackMessage.push({label_str:label_str,type:type});
   }
   function removeMessage(obj)
   {
      var _loc4_ = obj.target.id;
      var _loc6_ = Math.abs(this.message_arr[_loc4_ + 1]._height + this.message_arr[_loc4_ + 1]._y);
      this.message_arr[_loc4_].closeMessage();
      this.message_arr[_loc4_].removeEventListener(lol.gpui.ServiceMessage.REMOVE_MESSAGE,this,this.removeMessage);
      this.message_arr[_loc4_].removeEventListener(lol.gpui.ServiceMessage.REMOVE_ALL_MESSAGES,this,this.removeAllMessages);
      this.message_arr.splice(_loc4_,1);
      var _loc2_ = _loc4_;
      var _loc3_;
      while(_loc2_ < this.message_arr.length)
      {
         _loc3_ = this.getSlideToY(_loc2_);
         this.message_arr[_loc2_].id = _loc2_;
         this.message_arr[_loc2_].slide(_loc3_);
         _loc2_ = _loc2_ + 1;
      }
      var _loc5_;
      if(this.stackMessage.length > 0)
      {
         _loc5_ = this.stackMessage.shift();
         this.newMessage(_loc5_.label_str,_loc5_.type);
      }
   }
   function removeAllMessages(obj)
   {
      var _loc2_;
      while(this.stackMessage.length > 0)
      {
         _loc2_ = this.stackMessage.shift();
         if(_loc2_)
         {
            _loc2_.closeMessage();
            _loc2_.removeEventListener(lol.gpui.ServiceMessage.REMOVE_MESSAGE,this,this.removeMessage);
            _loc2_.removeEventListener(lol.gpui.ServiceMessage.REMOVE_ALL_MESSAGES,this,this.removeAllMessages);
         }
      }
      while(this.message_arr.length > 0)
      {
         _loc2_ = this.message_arr.shift();
         if(_loc2_)
         {
            _loc2_.closeMessage();
            _loc2_.removeEventListener(lol.gpui.ServiceMessage.REMOVE_MESSAGE,this,this.removeMessage);
            _loc2_.removeEventListener(lol.gpui.ServiceMessage.REMOVE_ALL_MESSAGES,this,this.removeAllMessages);
         }
      }
   }
   function getHeight()
   {
      var _loc3_ = 0;
      var _loc2_ = 0;
      while(_loc2_ < this.message_arr.length)
      {
         _loc3_ += this.message_arr[_loc2_]._height + this.SPAN;
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function getSlideToY(id)
   {
      var _loc3_ = this.message_arr[id]._height;
      var _loc2_ = 0;
      while(_loc2_ < this.message_arr.length)
      {
         if(_loc2_ == id)
         {
            break;
         }
         _loc3_ += this.message_arr[_loc2_]._height + this.SPAN;
         _loc2_ = _loc2_ + 1;
      }
      return - _loc3_;
   }
   function startTimeout(param)
   {
      this[param] = false;
      var _loc2_ = new lol.utils.Timeout(this,this.stopTimeout,lol.gpui.ServiceMessageManager.GOLD_MESSAGE_TIMEOUT,param);
   }
   function stopTimeout(param)
   {
      this[param] = true;
   }
}
