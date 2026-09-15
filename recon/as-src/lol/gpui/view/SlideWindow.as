class lol.gpui.view.SlideWindow extends lol.gpui.view.SimpleWindow
{
   var _y;
   var bottom;
   var dispatchEvent;
   var doLater;
   var onEnterFrame;
   var removeMovieClip;
   var top;
   var topClose;
   var inBottom = false;
   var isClose = false;
   var deleteFlag = false;
   function SlideWindow()
   {
      super();
      this.doLater("rollBottom");
   }
   function rollBottom()
   {
      this.isClose = false;
      this.inBottom = true;
      this.slideTo(this.bottom);
   }
   function rollTop()
   {
      this.isClose = false;
      this.inBottom = false;
      this.slideTo(this.top);
   }
   function rollClose()
   {
      this.isClose = true;
      this.inBottom = false;
      this.slideTo(this.topClose);
   }
   function slideTo(param)
   {
      delete this.onEnterFrame;
      var path;
      this.onEnterFrame = function()
      {
         path = param - this._y;
         this._y += path;
         this._y = Math.round(this._y);
         if(Math.abs(path) < 3)
         {
            this.deleteWindow();
            delete this.onEnterFrame;
         }
      };
   }
   function deleteWindow()
   {
      if(this.deleteFlag)
      {
         this.dispatchEvent({type:"closeSlideWin"});
         this.removeMovieClip();
      }
   }
}
