class lol.gpui.controls.ToggleButton extends lol.gpui.controls.GPUIButton
{
   var _enabled;
   var _toggled;
   var _totalframes;
   var _width;
   var _ymouse;
   var clickEvent;
   var dispatchEvent;
   var gotoAndStop;
   var hintTitle_str;
   var showHint;
   function ToggleButton()
   {
      super();
      this._toggled = false;
   }
   function onPress()
   {
      this.toggled = !this.toggled;
      if(this._enabled)
      {
         this.dispatchEvent({type:this.clickEvent});
      }
      this.gotoAndStop(2);
      this.showHint(false);
      lol.gpui.HintManager.closeHint();
   }
   function onRelease()
   {
      this.toggled = this.toggled;
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_EVENT});
      }
   }
   function onRollOver()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT});
      }
      if(this._totalframes > 2)
      {
         this.gotoAndStop(3);
      }
      if(this.hintTitle_str)
      {
         lol.gpui.HintManager.showHint(this.hintTitle_str,this._ymouse,this._width - this._ymouse);
      }
      this.showHint(true);
   }
   function onRollOut()
   {
      this.toggled = this.toggled;
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.ROLL_OUT_EVENT});
      }
      lol.gpui.HintManager.closeHint();
      this.showHint(false);
   }
   function onReleaseOutside()
   {
      this.toggled = !this.toggled;
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT});
      }
   }
   function set toggled(t)
   {
      this._toggled = t;
      if(t)
      {
         this.gotoAndStop(2);
      }
      else
      {
         this.gotoAndStop(1);
      }
      this.dispatchEvent({type:"change"});
   }
   function get toggled()
   {
      return this._toggled;
   }
}
