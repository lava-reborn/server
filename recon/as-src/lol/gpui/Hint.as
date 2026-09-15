class lol.gpui.Hint extends lol.gpui.GPUIObject
{
   var _alpha;
   var _height;
   var _width;
   var _x;
   var _y;
   var back;
   var comics;
   var hint_mc;
   var left;
   var middle;
   var onEnterFrame;
   var onMouseMove;
   var param;
   var removeMovieClip;
   var right;
   var t;
   var title_str;
   var title_txt;
   var leftMargin = 5;
   var topMargin = 0;
   var speedAlpha = 30;
   var pause = 0;
   var build = false;
   var reverseFlag = false;
   var stageRight = 5;
   function Hint()
   {
      super();
      this.left = this.back.left;
      this.middle = this.back.middle;
      this.right = this.back.right;
      this.hint_mc = this;
      this.doLater("init");
   }
   function init()
   {
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.title_txt.autoSize = true;
      this.title_txt.htmlText = this.title_str;
      this.title_txt.setTextFormat(_loc2_);
      this.hintSize();
   }
   function removeHint()
   {
      this.build = false;
      this.t.Clear();
      delete this.onMouseMove;
      this.removeMovieClip();
   }
   function hintSize()
   {
      var _loc2_ = this.title_txt._width;
      this.middle._width = _loc2_;
      this.right._x = this.middle._x + this.middle._width + this.right._width;
      this.right._width = - this.right._width;
   }
   function timePause()
   {
      this.t = new lol.utils.Timeout(this,this.init,this.param.pause);
   }
   function reverse()
   {
      this.reverseFlag = !this.reverseFlag;
      if(this.reverseFlag)
      {
         this.comics.gotoAndStop(2);
         this.comics._y = 0;
         this.back._y = this.comics._height;
         this.title_txt._y = this.back._y;
      }
      else
      {
         this.comics.gotoAndStop(1);
         this.comics._y = - this.comics._y;
         this.back._y = -22;
         this.title_txt._y = this.back._y;
      }
   }
   function hintPosition(_hintX, _hintY)
   {
      var _loc3_;
      var _loc2_;
      if(_hintY != undefined)
      {
         _loc3_ = _hintX;
         _loc2_ = _hintY;
      }
      else
      {
         _loc3_ = lol.core.SceneShifter.linkHint._xmouse;
         _loc2_ = lol.core.SceneShifter.linkHint._ymouse;
      }
      var _loc6_ = this;
      var _loc4_;
      if(_loc3_ + this._width + this.stageRight > Stage.width)
      {
         _loc4_ = _loc3_ + this._width + this.stageRight - Stage.width;
         this.comics._x = Math.round(_loc4_);
         _loc3_ = Stage.width - this._width - this.stageRight;
      }
      if(_loc2_ + this._height > Stage.height)
      {
         _loc2_ -= this._height;
      }
      this._x = Math.round(_loc3_);
      this._y = Math.round(_loc2_);
   }
   function showIn()
   {
      this.build = true;
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         this._alpha += 30;
         if(this._alpha >= 100)
         {
            this._alpha = 100;
            delete this.onEnterFrame;
         }
      };
   }
   function showOut()
   {
      this.t.Clear();
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         this._alpha -= 30;
         if(this._alpha <= 0)
         {
            delete this.onEnterFrame;
            this.build = false;
            this.removeMovieClip();
         }
      };
      delete this.onMouseMove;
   }
}
