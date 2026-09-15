class lol.gpui.view.TopWindow extends lol.gpui.GPUIObject
{
   var _y;
   var attachMovie;
   var bottom;
   var content;
   var onEnterFrame;
   var top;
   var delta = 18;
   function TopWindow()
   {
      super();
      this.top = this._y;
      this.bottom = this.top + this.delta;
   }
   function kill()
   {
      this.content.kill();
   }
   function open(link)
   {
      this.content = this.attachMovie(link,link,this.content.getNextHighestDepth());
      this.openWin();
      return this.content;
   }
   function openWin()
   {
      this.onEnterFrame = function()
      {
         var _loc2_ = this.bottom - this._y;
         this._y += _loc2_ / 2.5;
         this._y = Math.round(this._y);
         if(Math.abs(_loc2_) <= 1)
         {
            this._y = this.bottom;
            delete this.onEnterFrame;
         }
      };
   }
   function close()
   {
      this.kill();
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         var _loc2_ = this.bottom - this._y + 1;
         this._y -= _loc2_ * 1.5;
         this._y = Math.round(this._y);
         if(this._y <= this.top)
         {
            this._y = this.top;
            delete this.onEnterFrame;
            this.content.removeMovieClip();
         }
      };
   }
}
