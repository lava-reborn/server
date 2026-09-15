class lol.gpui.controls.SortButton extends lol.gpui.controls.GPUIButton
{
   var _enabled;
   var dispatchEvent;
   var gotoAndStop;
   static var STATIC_FRAME = 1;
   static var STATIC_PRESS_FRAME = 2;
   static var SORT_UP_FRAME = 3;
   static var SORT_UP_PRESS_FRAME = 4;
   static var SORT_DOWN_FRAME = 5;
   static var SORT_DOWN_PRESS_FRAME = 6;
   var currentState = 1;
   function SortButton()
   {
      super();
   }
   function onPress()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.PRESS_EVENT});
      }
      this.gotoAndStop(this.currentState + 1);
      lol.gpui.HintManager.closeHint();
   }
   function onRelease()
   {
      if(this.currentState == lol.gpui.controls.SortButton.STATIC_FRAME)
      {
         this.gotoAndStop(lol.gpui.controls.SortButton.SORT_UP_FRAME);
         this.currentState = lol.gpui.controls.SortButton.SORT_UP_FRAME;
      }
      else if(this.currentState == lol.gpui.controls.SortButton.SORT_UP_FRAME)
      {
         this.gotoAndStop(lol.gpui.controls.SortButton.SORT_DOWN_FRAME);
         this.currentState = lol.gpui.controls.SortButton.SORT_DOWN_FRAME;
      }
      else if(this.currentState == lol.gpui.controls.SortButton.SORT_DOWN_FRAME)
      {
         this.gotoAndStop(lol.gpui.controls.SortButton.SORT_UP_FRAME);
         this.currentState = lol.gpui.controls.SortButton.SORT_UP_FRAME;
      }
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_EVENT});
      }
   }
   function onReleaseOutside()
   {
      if(this._enabled)
      {
         this.dispatchEvent({type:lol.gpui.controls.GPUIButton.RELEASE_OUTSIDE_EVENT});
      }
      this.gotoAndStop(this.currentState);
      lol.gpui.HintManager.closeHint();
   }
   function setFrame(_frame)
   {
      this.gotoAndStop(_frame);
      this.currentState = _frame;
   }
}
