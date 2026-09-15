class lol.gpui.view.ViewFrame extends lol.gpui.GPUIObject
{
   var _content;
   var cont_mc;
   var createEmptyMovieClip;
   var deleteEnterFrame;
   var dispatchEvent;
   var drawMethod;
   var maskH;
   var maskW;
   var mask_mc;
   var newEnterFrame;
   var v = 20;
   var defaultW = 100;
   var defaultH = 100;
   var setArea = false;
   var setAreaObj = new Object();
   var handDrag = false;
   function ViewFrame()
   {
      super();
      lol.utils.EFBeacon.initialize(this);
      if(!this.cont_mc)
      {
         this.cont_mc = this.createEmptyMovieClip("cont_mc",0);
      }
      if(!this.mask_mc)
      {
         this.mask_mc = this.createEmptyMovieClip("mask_mc",1);
      }
      this.cont_mc.setMask(this.mask_mc);
      Key.addListener(this);
      if(this.mask_mc._width > 1 && this.mask_mc._height > 1)
      {
         this.drawMethod = this.resizeMask;
      }
      else
      {
         this.drawMethod = this.drawMask;
         this.setSize();
      }
      Key.addListener(this);
   }
   function setHandScroll(h)
   {
      if(h)
      {
         this.handDrag = true;
         this.cont_mc.onPress = mx.utils.Delegate.create(this,this.startDragContent);
         this.cont_mc.onRelease = this.cont_mc.onReleaseOutside = mx.utils.Delegate.create(this,this.stopDragContent);
      }
      else
      {
         this.handDrag = false;
         this.stopDragContent();
         delete this.cont_mc.onPress;
         delete this.cont_mc.onRelease;
         delete this.cont_mc.onReleaseOutside;
      }
   }
   function startDragContent()
   {
      this.cont_mc.startDrag(false,this.left,this.top,this.right,this.bottom);
      this.cont_mc.onMouseMove = mx.utils.Delegate.create(this,this.dragContent);
   }
   function stopDragContent()
   {
      delete this.cont_mc.onMouseMove;
      this.cont_mc.stopDrag();
      this.dispatchPosition();
   }
   function dragContent()
   {
      this.dispatchPosition();
   }
   function fillContent(link)
   {
      if(link)
      {
         this._content = this.cont_mc.attachMovie(link,"_content",0);
         this.setPosition(0,0);
      }
      else
      {
         this._content = this.cont_mc.createEmptyMovieClip("_content",0);
      }
      return this._content;
   }
   function setScrollArea(x, y, w, h)
   {
      if(x == undefined)
      {
         this.setArea = false;
      }
      else
      {
         this.setAreaObj.top = y + h;
         this.setAreaObj.left = x + w;
         this.setAreaObj.bottom = - y;
         this.setAreaObj.right = - x;
         this.setArea = true;
      }
   }
   function clearContent()
   {
      this._content.removeMovieClip();
   }
   function get content()
   {
      return this._content;
   }
   function setSize(w, h)
   {
      this.maskW = w;
      this.maskH = h;
      this.drawMethod(w,h);
      this.setPosition(this.xPosition,this.yPosition);
      this.boundOX();
      this.boundOY();
   }
   function getSize()
   {
      return {width:this.maskW,height:this.maskH};
   }
   function drawMask(w, h)
   {
      var _loc3_ = !w ? this.defaultW : w;
      var _loc2_ = !h ? this.defaultH : h;
      this.mask_mc.clear();
      lol.utils.Draw.drawFillRect(this.mask_mc,0,0,_loc3_,_loc2_,1,0,0,16711680,30);
   }
   function resizeMask(w, h)
   {
      this.mask_mc._width = w;
      this.mask_mc._height = h;
   }
   function setPosition(xpos, ypos)
   {
      this.cont_mc._x = this.right - xpos * (this.right - this.left) / 100;
      this.cont_mc._y = this.bottom - ypos * (this.bottom - this.top) / 100;
      this.dispatchPosition();
   }
   function position(obj)
   {
      if(this.cont_mc._height > this.mask_mc._height)
      {
         this.xPosition = obj.xpos;
         this.yPosition = obj.ypos;
      }
      else if(this.cont_mc._height != 0)
      {
         this.xPosition = 0;
         this.yPosition = 0;
      }
   }
   function dispatchPosition()
   {
      this.dispatchEvent({type:"position",xpos:this.xPosition,ypos:this.yPosition,width:this.mask_mc._width,height:this.mask_mc._height});
   }
   function get xPosition()
   {
      return 100 * (this.right - this.cx) / (this.right - this.left);
   }
   function set xPosition(pos)
   {
      this.cx = this.right - pos * (this.right - this.left) / 100;
   }
   function get yPosition()
   {
      return 100 * (this.bottom - this.cy) / (this.bottom - this.top);
   }
   function set yPosition(pos)
   {
      this.cy = this.bottom - pos * (this.bottom - this.top) / 100;
   }
   function slideToCenter(X, Y)
   {
      this.cx = this.mask_mc._width / 2 - X;
      this.cy = this.mask_mc._height / 2 - Y;
   }
   function centerPoint(x, y)
   {
      this.doLater("_centerPoint",[x,y]);
   }
   function _centerPoint(x, y)
   {
      this.cont_mc._x = this.mask_mc._width / 2 - x;
      this.cont_mc._y = this.mask_mc._height / 2 - y;
      this.boundOX();
      this.boundOY();
      this.dispatchPosition();
   }
   function scrollX(v)
   {
      this.cont_mc._x += v;
      this.boundOX();
   }
   function scrollY(v)
   {
      this.cont_mc._y += v;
      this.boundOY();
   }
   function slideScrollX(v)
   {
      this.cx += v;
   }
   function slideScrollY(v)
   {
      this.cy += v;
   }
   function set cx(x)
   {
      this.deleteEnterFrame("slideContX");
      var _loc2_ = Math.round(x);
      this.newEnterFrame("slideContX",_loc2_);
      this.dispatchPosition();
   }
   function get cx()
   {
      return this.cont_mc._x;
   }
   function set cy(y)
   {
      this.deleteEnterFrame("slideContY");
      var _loc2_ = Math.round(y);
      this.newEnterFrame("slideContY",_loc2_);
      this.dispatchPosition();
   }
   function get cy()
   {
      return this.cont_mc._y;
   }
   function slideContX(endX)
   {
      var _loc2_ = endX - this.cont_mc._x;
      var _loc4_ = Math.abs(_loc2_) / _loc2_;
      this.cont_mc._x = endX;
      if(Math.abs(_loc2_) <= 1)
      {
         this.deleteEnterFrame("slideContX");
         this.cont_mc._x = endX;
      }
      this.boundOX();
      this.dispatchPosition();
   }
   function slideContY(endY)
   {
      var _loc2_ = endY - this.cont_mc._y;
      var _loc4_ = Math.abs(_loc2_) / _loc2_;
      this.cont_mc._y = endY;
      if(Math.abs(_loc2_) <= 1)
      {
         this.deleteEnterFrame("slideContY");
         this.cont_mc._y = endY;
      }
      this.boundOY();
      this.dispatchPosition();
   }
   function boundOX()
   {
      var _loc2_ = this.right;
      var _loc3_ = this.left;
      var _loc4_ = this.cont_mc._width > this.mask_mc._width;
      if(_loc3_ < _loc2_)
      {
         if(this.cont_mc._x < _loc3_ && _loc4_)
         {
            this.cont_mc._x = _loc3_;
            this.deleteEnterFrame(this.slideContX);
            return undefined;
         }
         if(this.cont_mc._x > _loc2_ && _loc4_)
         {
            this.cont_mc._x = Math.ceil(_loc2_);
            this.deleteEnterFrame(this.slideContX);
            return undefined;
         }
      }
   }
   function boundOY()
   {
      var _loc2_ = this.top;
      var _loc3_ = this.bottom;
      var _loc4_ = this.cont_mc._height > this.mask_mc._height;
      if(this.cont_mc._y < _loc2_ && _loc4_)
      {
         this.cont_mc._y = Math.floor(_loc2_);
         this.deleteEnterFrame(this.slideContY);
         return undefined;
      }
      if(this.cont_mc._y > _loc3_ && _loc4_)
      {
         this.cont_mc._y = Math.ceil(_loc3_);
         this.deleteEnterFrame(this.slideContY);
         return undefined;
      }
   }
   function get left()
   {
      if(this.setArea)
      {
         return this.mask_mc._width - this.setAreaObj.left;
      }
      return this.mask_mc._width - this._content._width - this._content.getRect().xMin;
   }
   function get top()
   {
      if(this.setArea)
      {
         return this.mask_mc._height - this.setAreaObj.top;
      }
      return this.mask_mc._height - this.cont_mc._height - this._content.getRect().yMin;
   }
   function get right()
   {
      if(this.setArea)
      {
         return this.setAreaObj.right;
      }
      return - this._content.getRect().xMin;
   }
   function get bottom()
   {
      if(this.setArea)
      {
         return this.setAreaObj.bottom;
      }
      return - this._content.getRect().yMin;
   }
}
