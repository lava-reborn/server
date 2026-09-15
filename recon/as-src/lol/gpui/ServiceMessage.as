class lol.gpui.ServiceMessage extends lol.gpui.GPUIObject
{
   var _alpha;
   var _label_str;
   var _type;
   var _y;
   var bg;
   var bg_bottom;
   var bg_middle;
   var bg_top;
   var createEmptyMovieClip;
   var dispatchEvent;
   var getNextHighestDepth;
   var label_txt;
   var mc;
   var mc2;
   var removeMovieClip;
   var slideTo;
   var t;
   var type_mc;
   static var QUEST_MESSAGE = "QUEST_MESSAGE";
   static var QUEST_MESSAGE_COMPLETE = "QUEST_MESSAGE_COMPLETE";
   static var MAIL_MESSAGE = "MAIL_MESSAGE";
   static var SKILL_0_MESSAGE = "SKILL_0_MESSAGE";
   static var SKILL_1_MESSAGE = "SKILL_1_MESSAGE";
   static var SKILL_2_MESSAGE = "SKILL_2_MESSAGE";
   static var SKILL_3_MESSAGE = "SKILL_3_MESSAGE";
   static var SKILL_4_MESSAGE = "SKILL_4_MESSAGE";
   static var SKILL_0_MESSAGE_PREMIUM = "SKILL_0_MESSAGE_PREMIUM";
   static var SKILL_1_MESSAGE_PREMIUM = "SKILL_1_MESSAGE_PREMIUM";
   static var SKILL_2_MESSAGE_PREMIUM = "SKILL_2_MESSAGE_PREMIUM";
   static var SKILL_3_MESSAGE_PREMIUM = "SKILL_3_MESSAGE_PREMIUM";
   static var SKILL_4_MESSAGE_PREMIUM = "SKILL_4_MESSAGE_PREMIUM";
   static var GOLD_MESSAGE = "GOLD_MESSAGE";
   static var REPUTATION_MESSAGE = "REPUTATION_MESSAGE";
   static var REMOVE_MESSAGE = "REMOVE_MESSAGE";
   static var REMOVE_ALL_MESSAGES = "REMOVE_ALL_MESSAGES";
   static var ON_RELEASE = "ON_RELEASE";
   var animationStatus = false;
   var pause = 8000;
   function ServiceMessage()
   {
      super();
      this.bg_top = this.bg.bg_top;
      this.bg_middle = this.bg.bg_middle;
      this.bg_bottom = this.bg.bg_bottom;
      this._alpha = 0;
      this.doLater("init");
   }
   function init()
   {
      this.mc = this.createEmptyMovieClip("mc",this.getNextHighestDepth());
      this.mc.onEnterFrame = mx.utils.Delegate.create(this,this.inOut);
      var _loc2_ = (Math.floor(this.label_txt._height / 16) + 1) * 2000;
      this.t = new lol.utils.Timeout(this,this._closeMessage,_loc2_);
      this.bg.onRelease = mx.utils.Delegate.create(this,this.bgOnRelease);
   }
   function bgOnRelease()
   {
      this._closeMessage(Key.isDown(17));
      this.dispatchEvent({type:lol.gpui.ServiceMessage.ON_RELEASE});
   }
   function _closeMessage(removeAll)
   {
      if(removeAll)
      {
         this.dispatchEvent({type:lol.gpui.ServiceMessage.REMOVE_ALL_MESSAGES});
      }
      else
      {
         this.dispatchEvent({type:lol.gpui.ServiceMessage.REMOVE_MESSAGE});
      }
      this.closeMessage();
   }
   function closeMessage()
   {
      this.t.Clear();
      delete this.t;
      this.animationStatus = true;
      this.mc.onEnterFrame = mx.utils.Delegate.create(this,this.inOut);
   }
   function removeThis()
   {
      this.mc.removeMovieClip();
      this.removeMovieClip();
   }
   function inOut()
   {
      if(!this.animationStatus)
      {
         if(this._alpha < 100)
         {
            this._alpha += 10;
         }
         else
         {
            this._alpha = 100;
            delete this.mc.onEnterFrame;
         }
      }
      else if(this._alpha > 0)
      {
         this._alpha -= 10;
      }
      else
      {
         this._alpha = 0;
         delete this.mc.onEnterFrame;
         this.doLater("removeThis");
      }
   }
   function slide(Y)
   {
      if(!this.mc2)
      {
         this.mc2 = this.createEmptyMovieClip("mc2",this.getNextHighestDepth());
      }
      delete this.mc2.onEnterFrame;
      this.slideTo = Y;
      this.mc2.onEnterFrame = mx.utils.Delegate.create(this,this._slide);
   }
   function _slide()
   {
      var _loc2_ = this.slideTo - this._y;
      if(Math.abs(_loc2_) < 2)
      {
         this._y = this.slideTo;
         delete this.mc2.onEnterFrame;
      }
      else
      {
         this._y += _loc2_ / 2;
      }
   }
   function resize()
   {
      this.label_txt.y = this.bg_top._height;
      this.bg_middle._y = this.label_txt._y;
      this.bg_bottom._y = this.label_txt.y + Math.round(this.label_txt._height) + this.bg_bottom._height;
      this.bg_middle._height = Math.round(this.label_txt._height);
   }
   function set label(str)
   {
      this._label_str = str;
      this.label_txt.autoSize = true;
      this.label_txt.multiline = true;
      this.label_txt.html = true;
      this.label_txt.htmlText = "<B>" + str + "</B>";
      this.resize();
   }
   function get label()
   {
      return this._label_str;
   }
   function set type(str)
   {
      this.doLater("gotoAndStopType_mc",[str]);
      this._type = str;
   }
   function gotoAndStopType_mc(str)
   {
      this.gotoAndStopBG(3);
      this.type_mc.gotoAndStop(str);
      switch(str)
      {
         case lol.gpui.ServiceMessage.QUEST_MESSAGE:
            this.gotoAndStopBG(2);
            break;
         case lol.gpui.ServiceMessage.QUEST_MESSAGE_COMPLETE:
            this.gotoAndStopBG(1);
            break;
         case lol.gpui.ServiceMessage.GOLD_MESSAGE:
            this.gotoAndStopBG(4);
            break;
         case lol.gpui.ServiceMessage.REPUTATION_MESSAGE:
            this.gotoAndStopBG(5);
         default:
            return;
      }
   }
   function gotoAndStopBG(num)
   {
      this.bg_top.gotoAndStop(num);
      this.bg_middle.gotoAndStop(num);
      this.bg_bottom.gotoAndStop(num);
   }
   function get type()
   {
      return this._type;
   }
}
