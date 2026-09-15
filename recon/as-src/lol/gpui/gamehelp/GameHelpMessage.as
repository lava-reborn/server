class lol.gpui.gamehelp.GameHelpMessage extends lol.gpui.GPUIObject
{
   var _alpha;
   var _type;
   var _x;
   var bg;
   var createEmptyMovieClip;
   var dispatchEvent;
   var doLater;
   var getNextHighestDepth;
   var help_manager;
   var mc;
   var mc2;
   var removeMovieClip;
   var slideTo;
   var t;
   var type_id;
   static var REMOVE_MESSAGE = "GAME_HELP_REMOVE_MESSAGE";
   static var ON_RELEASE = "ON_RELEASE";
   var animationStatus = false;
   function GameHelpMessage()
   {
      super();
      this._alpha = 0;
      this.doLater("init");
   }
   function init()
   {
      this.mc = this.createEmptyMovieClip("mc",this.getNextHighestDepth());
      this.mc.onEnterFrame = mx.utils.Delegate.create(this,this.inOut);
      this.bg.onRelease = mx.utils.Delegate.create(this,this.bgOnRelease);
   }
   function bgOnRelease()
   {
      this._closeMessage();
      this.dispatchEvent({type:lol.gpui.gamehelp.GameHelpMessage.ON_RELEASE});
   }
   function _closeMessage()
   {
      this.dispatchEvent({type:lol.gpui.gamehelp.GameHelpMessage.REMOVE_MESSAGE});
      this.closeMessage();
   }
   function closeMessage()
   {
      this.t.Clear();
      delete this.t;
      this.animationStatus = true;
      this.mc.onEnterFrame = mx.utils.Delegate.create(this,this.inOut);
      this.help_manager.setMessageID(this.type_id);
      lol.core.SceneShifter.openNewWindow("game_hint","center");
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
   function slide(X)
   {
      if(!this.mc2)
      {
         this.mc2 = this.createEmptyMovieClip("mc2",this.getNextHighestDepth());
      }
      delete this.mc2.onEnterFrame;
      this.slideTo = X;
      this.mc2.onEnterFrame = mx.utils.Delegate.create(this,this._slide);
   }
   function _slide()
   {
      var _loc2_ = this.slideTo - this._x;
      if(Math.abs(_loc2_) < 2)
      {
         this._x = this.slideTo;
         delete this.mc2.onEnterFrame;
      }
      else
      {
         this._x += _loc2_ / 2;
      }
   }
   function set type(str)
   {
      this._type = str;
   }
}
