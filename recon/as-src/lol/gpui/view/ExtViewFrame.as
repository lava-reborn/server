class lol.gpui.view.ExtViewFrame extends lol.gpui.view.ViewFrame
{
   var H;
   var W;
   var _parent;
   var _xmouse;
   var _ymouse;
   var bottomRect;
   var createEmptyMovieClip;
   var doLater;
   var getNextHighestDepth;
   var leftRect;
   var mc_onEnterFrame;
   var onEnterFrame;
   var onMouseMove;
   var rightRect;
   var scrollX;
   var scrollY;
   var stepX;
   var stepY;
   var stopDragContent;
   var t1;
   var topRect;
   var xProc;
   var yProc;
   var scrollAreaWidth = 60;
   var timePouse = 500;
   var step = 20;
   var deceleration = 1.2;
   var exceptionW = 590;
   var exceptionH = 130;
   var scrollEnabled = true;
   var moveEnabled = false;
   var pressMiddleButton = false;
   var deleteOnEnterFrame = false;
   function ExtViewFrame()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.scrollOn();
      lol.core.SceneShifter._ref.addEventListener("sceneEnabled",this);
      this.middleMouseButton(true);
   }
   function kill()
   {
   }
   function scrollOn()
   {
      if(lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SCROLL_IN_SIDE))
      {
         this.onMouseMove = this.checkMousePosition;
      }
      else
      {
         delete this.onMouseMove;
      }
   }
   function sceneEnabled(obj)
   {
      var _loc2_ = obj.status;
      this.moveEnabled = !_loc2_;
      this.deleteOnEnterFrame = true;
      delete this.onMouseMove;
      if(this.moveEnabled)
      {
         this.scrollOn();
      }
   }
   function middleMouseButton(b)
   {
      if(b)
      {
         if(!this.mc_onEnterFrame)
         {
            this.mc_onEnterFrame = this.createEmptyMovieClip("mc_onEnterFrame",this.getNextHighestDepth());
            this.mc_onEnterFrame.onEnterFrame = function()
            {
               if(Key.isDown(4))
               {
                  if(!this._parent.pressMiddleButton && !lol.core.SceneShifter._ref.flagSceneEnabled)
                  {
                     this._parent.pressMiddleButton = true;
                     this._parent.startDragContent();
                  }
               }
               else if(this._parent.pressMiddleButton)
               {
                  this._parent.pressMiddleButton = false;
                  this._parent.stopDragContent();
               }
            };
         }
      }
      else
      {
         this.pressMiddleButton = false;
         this.stopDragContent();
         delete this.mc_onEnterFrame.onEnterFrame;
         this.mc_onEnterFrame.removeMovieClip();
         this.mc_onEnterFrame = null;
      }
   }
   function setSize(w, h)
   {
      super.setSize(w,h);
      this.buildRect(w,h);
   }
   function buildRect(w, h)
   {
      this.W = w;
      this.H = h;
      this.leftRect = new flash.geom.Rectangle(0,0,this.scrollAreaWidth,h - this.exceptionH);
      this.topRect = new flash.geom.Rectangle(this.scrollAreaWidth,0,w - 2 * this.scrollAreaWidth,this.scrollAreaWidth);
      this.rightRect = new flash.geom.Rectangle(w - this.scrollAreaWidth,0,this.scrollAreaWidth,h);
      this.bottomRect = new flash.geom.Rectangle(this.exceptionW,h - this.scrollAreaWidth,w - this.scrollAreaWidth - this.exceptionW,this.scrollAreaWidth);
   }
   function checkMousePosition()
   {
      if(!this.onEnterFrame)
      {
         this.t1.Clear();
         this.t1 = null;
      }
      var _loc3_ = this._xmouse;
      var _loc2_ = this._ymouse;
      var _loc5_ = this.W / 2;
      var _loc4_ = this.H / 2;
      var _loc7_;
      var _loc6_;
      if(this.leftRect.contains(_loc3_,_loc2_))
      {
         this.xProc = (this.scrollAreaWidth - _loc3_) * 100 / this.scrollAreaWidth;
         this.yProc = (_loc4_ - _loc2_) * 100 / _loc4_;
         this.startMove();
      }
      else if(this.topRect.contains(_loc3_,_loc2_))
      {
         this.yProc = (this.scrollAreaWidth - _loc2_) * 100 / this.scrollAreaWidth;
         this.xProc = (_loc5_ - _loc3_) * 100 / _loc5_;
         this.startMove();
      }
      else if(this.rightRect.contains(_loc3_,_loc2_))
      {
         _loc7_ = _loc3_ - this.W + this.scrollAreaWidth;
         this.xProc = (this.scrollAreaWidth - _loc7_) * 100 / this.scrollAreaWidth - 100;
         this.yProc = (_loc4_ - _loc2_) * 100 / _loc4_;
         this.startMove();
      }
      else if(this.bottomRect.contains(_loc3_,_loc2_))
      {
         _loc6_ = _loc2_ - (this.H - this.scrollAreaWidth);
         this.yProc = (this.scrollAreaWidth - _loc6_) * 100 / this.scrollAreaWidth - 100;
         this.xProc = (_loc5_ - _loc3_) * 100 / _loc5_;
         this.startMove();
      }
      else
      {
         this.stopMove();
      }
   }
   function startMove()
   {
      this.deleteOnEnterFrame = false;
      if(!this.t1)
      {
         this.t1 = new lol.utils.Timeout(this,this.moveTo,this.timePouse);
      }
   }
   function stopMove()
   {
      this.t1.Clear();
      this.t1 = null;
      this.deleteOnEnterFrame = true;
   }
   function moveTo()
   {
      delete this.onEnterFrame;
      this.onEnterFrame = function()
      {
         if(this.deleteOnEnterFrame)
         {
            this.stepX /= this.deceleration;
            this.stepY /= this.deceleration;
            if(Math.abs(this.stepX) <= 2 && Math.abs(this.stepY) <= 2)
            {
               this.deleteOnEnterFrame = false;
               delete this.onEnterFrame;
            }
         }
         else
         {
            this.stepX = this.step * this.xProc / 100;
            this.stepY = this.step * this.yProc / 100;
         }
         this.scrollX(Math.round(this.stepX));
         this.scrollY(Math.round(this.stepY));
      };
   }
}
