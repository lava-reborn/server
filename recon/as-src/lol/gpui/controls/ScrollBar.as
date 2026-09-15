class lol.gpui.controls.ScrollBar extends lol.gpui.GPUIObject
{
   var H;
   var _xmouse;
   var _ymouse;
   var back_bottom_mc;
   var back_mc;
   var back_top_mc;
   var deleteEnterFrame;
   var dispatchEvent;
   var downButton;
   var newEnterFrame;
   var scrTarget;
   var scrollArea;
   var scrollTarget;
   var slideArea;
   var sliderButton;
   var upButton;
   static var POSITION = "position";
   var scrollValue = 10;
   var isDrag = false;
   function ScrollBar()
   {
      super();
      lol.utils.EFBeacon.initialize(this);
      this.doLater("init");
      this.doLater("preSet");
   }
   function init()
   {
      this.sliderButton.onPress = mx.utils.Delegate.create(this,this.dragSlider);
      this.sliderButton.onRelease = this.sliderButton.onReleaseOutside = mx.utils.Delegate.create(this,this.stopDragSlider);
      this.upButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrollUp);
      this.upButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
      this.downButton.addEventListener(lol.gpui.controls.GPUIButton.PRESS_EVENT,this,this.scrollDown);
      this.downButton.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.stopScroll);
   }
   function mouseWheel(delta)
   {
      var _loc3_ = this._xmouse;
      var _loc2_ = this._ymouse;
      var _loc5_ = Math.abs(delta) / delta;
      var _loc6_;
      if(_loc3_ < 0 && _loc3_ > - this.scrollArea && _loc2_ > 0 && _loc2_ < this.H)
      {
         this.sliderButton._y -= delta * this.scrollValue;
         if(this.sliderButton._y > this.bottom)
         {
            this.sliderButton._y = this.bottom;
         }
         else if(this.sliderButton._y < 0)
         {
            this.sliderButton._y = 0;
         }
         this.dispatchPosition();
      }
   }
   function dragSlider()
   {
      this.isDrag = true;
      this.sliderButton.startDrag(false,0,this.top,0,this.bottom);
      this.sliderButton.onMouseMove = mx.utils.Delegate.create(this,this.dragging);
   }
   function stopDragSlider()
   {
      this.isDrag = false;
      this.sliderButton.stopDrag();
      delete this.sliderButton.onMouseMove;
   }
   function dragging()
   {
      this.dispatchPosition();
   }
   function dispatchPosition()
   {
      this.scrollTarget();
      this.dispatchEvent({type:lol.gpui.controls.ScrollBar.POSITION,pos:this.__position});
   }
   function setPosition(pos)
   {
      this.position({pos:pos});
      this.dispatchPosition();
   }
   function position(obj)
   {
      if(!this.isDrag)
      {
         this.__position = obj.pos;
      }
   }
   function preSet()
   {
      this.__position = 0;
      var _loc2_ = this.downButton._y + this.downButton._height;
      this.setSize(_loc2_);
   }
   function setSize(h)
   {
      this.H = h;
      this.downButton._y = h - this.downButton._height;
      this.slideArea = new Object();
      this.top = this.upButton._height + 2;
      this.bottom = this.downButton._y - this.sliderButton._height - 2;
      this.drawBorder();
   }
   function drawBorder()
   {
      this.back_bottom_mc._y = this.downButton._y + this.downButton._height - 1;
      this.back_mc._height = this.back_bottom_mc._y - this.back_top_mc._height;
   }
   function get __position()
   {
      return 100 * (this.sliderButton._y - this.top) / (this.bottom - this.top - 1);
   }
   function set __position(pos)
   {
      this.sliderButton._y = this.top + pos / 100 * (this.bottom - this.top);
   }
   function get top()
   {
      return this.slideArea.top;
   }
   function set top(val)
   {
      this.slideArea.top = val;
   }
   function get bottom()
   {
      return this.slideArea.bottom;
   }
   function set bottom(val)
   {
      this.slideArea.bottom = val;
   }
   function scrollUp()
   {
      this.newEnterFrame(this.scroll,- this.scrollValue);
   }
   function scrollDown()
   {
      this.newEnterFrame(this.scroll,this.scrollValue);
   }
   function scroll(dy)
   {
      this.sliderButton._y += dy;
      if(this.sliderButton._y < this.top)
      {
         this.sliderButton._y = this.top;
         this.stopScroll();
      }
      if(this.sliderButton._y > this.bottom)
      {
         this.sliderButton._y = this.bottom;
         this.stopScroll();
      }
      this.dispatchPosition();
   }
   function stopScroll()
   {
      this.deleteEnterFrame(this.scroll);
   }
   function set target(targ)
   {
      if(targ instanceof TextField)
      {
         this.scrTarget = targ;
         this.scrollTarget = this.scrollText;
      }
      else if(targ instanceof lol.gpui.GPUIObject && targ.position)
      {
         this.scrTarget = targ;
         this.scrollTarget = this.scrollView;
      }
      else
      {
         this.scrollTarget = null;
      }
   }
   function scrollText()
   {
      this.scrTarget.scroll = this.scrTarget.maxscroll * this.__position / 100;
   }
   function scrollView()
   {
      this.scrTarget.position({pos:this.__position});
   }
}
