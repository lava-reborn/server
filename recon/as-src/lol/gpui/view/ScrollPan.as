class lol.gpui.view.ScrollPan extends lol.gpui.view.ViewFrame
{
   var _content;
   var _ih;
   var _iv;
   var _xmouse;
   var _ymouse;
   var addEventListener;
   var bottom;
   var cont_mc;
   var countTime;
   var dispatchEvent;
   var doLater;
   var hBar;
   var intervalID;
   var mask_mc;
   var mouseListener;
   var onMouseMove;
   var position;
   var rect;
   var removeEventListener;
   var slideScrollY;
   var vBar;
   var xPosition;
   var yPosition;
   var scrollValue = 10;
   var maxTimer = 500;
   var scrollParam = 90;
   var enabled = true;
   function ScrollPan()
   {
      super();
      this.doLater(this,"init");
   }
   function init()
   {
      this.vBar.scrollValue = this.scrollValue;
      this.hBar.scrollValue = this.scrollValue;
      this.chekSize();
      this.mouseListener = new Object();
      this.mouseListener.onMouseWheel = mx.utils.Delegate.create(this,this.mouseWheel);
      Mouse.addListener(this.mouseListener);
   }
   function kill()
   {
      clearInterval(this.intervalID);
      this.intervalID = null;
      Mouse.removeListener(this.mouseListener);
      delete this.onMouseMove;
   }
   function mouseWheel(delta)
   {
      var _loc4_ = this._xmouse;
      var _loc3_ = this._ymouse;
      var _loc2_ = Math.abs(delta) / delta;
      var _loc8_;
      if(this.rect.contains(_loc4_,_loc3_))
      {
         this.slideScrollY(_loc2_ * this.scrollParam);
         this.dragContent();
         this.dispatchEvent({type:"enabledContent",status:this.enabled});
      }
   }
   function counter()
   {
      this.countTime = this.countTime + 1;
      if(this.countTime >= this.maxTimer)
      {
         clearInterval(this.intervalID);
         this.countTime = this.maxTimer;
      }
   }
   function mouseMove()
   {
      delete this.onMouseMove;
      this.enabled = true;
      this.dispatchEvent({type:"enabledContent",status:this.enabled});
   }
   function dragContent()
   {
      super.dragContent();
      this.hBar.position({pos:this.xPosition});
      this.vBar.position({pos:this.yPosition});
   }
   function setPosition(xpos, ypos)
   {
      super.setPosition(xpos,ypos);
   }
   function fillContent(link)
   {
      super.fillContent(link);
      this.chekSize();
      return this._content;
   }
   function setSize(w, h)
   {
      super.setSize(w,h);
      this.rect = null;
      this.rect = new flash.geom.Rectangle(0,0,w + 20,h);
      this.vBar.scrollArea = this.mask_mc._width;
      this.chekSize();
   }
   function placeScroll(w, h)
   {
      this.vBar._y = 0;
      this.hBar._x = 0;
      this.vBar._x = w;
      this.hBar._y = h;
      this.vBar.setSize(h);
      this.hBar.setSize(w);
   }
   function slideContX(x)
   {
      super.slideContX(x);
   }
   function slideContY(y)
   {
      super.slideContY(y);
      this.dragContent();
   }
   function chekSize()
   {
      var _loc2_ = this.cont_mc._width > this.mask_mc._width;
      var _loc3_ = this.cont_mc._height > this.mask_mc._height;
      if(!_loc3_)
      {
         this.vBar.__position = 0;
         this.position({xpos:this.xPosition,ypos:0});
      }
      if(!_loc2_)
      {
         this.hBar.__position = 0;
         this.position({xpos:0,ypos:this.yPosition});
      }
      this.initHScroll(_loc2_);
      this.initVScroll(_loc3_);
      this.placeScroll(this.mask_mc._width,this.mask_mc._height);
   }
   function yPositionHandler(obj)
   {
      this.yPosition = obj.pos;
   }
   function xPositionHandler(obj)
   {
      this.xPosition = obj.pos;
   }
   function initVScroll(i)
   {
      if(i != this._iv)
      {
         this._iv = i;
         if(i)
         {
            this.vBar.addEventListener("position",this,this.yPositionHandler);
            this.addEventListener("position",this.vBar);
            this.vBar._visible = true;
         }
         else
         {
            this.vBar.removeEventListener("position",this,this.yPositionHandler);
            this.removeEventListener("position",this.vBar);
            this.vBar._visible = false;
         }
      }
   }
   function initHScroll(i)
   {
      if(i != this._ih)
      {
         this._ih = i;
         if(i)
         {
            this.hBar.addEventListener("position",this,this.xPositionHandler);
            this.addEventListener("position",this.hBar);
            this.hBar._visible = true;
         }
         else
         {
            this.hBar.removeEventListener("position",this,this.xPositionHandler);
            this.removeEventListener("position",this.hBar);
            this.hBar._visible = false;
         }
      }
   }
   function boundOY()
   {
      super.boundOY();
      var _loc3_ = this.bottom;
      var _loc4_ = this.cont_mc._height > this.mask_mc._height;
      if(!_loc4_)
      {
         this.cont_mc._y = Math.round(_loc3_);
      }
   }
   function get content()
   {
      this.doLater("chekSize");
      return this._content;
   }
   function set content(c)
   {
   }
}
