class lol.display.SpriteFocus
{
   var __color;
   var activated;
   var bitmap;
   var dispatchEvent;
   var flareTarget;
   var onMouseDown;
   var onMouseMove;
   var runtime;
   var spt;
   var spt_int;
   var target;
   static var onSpriteOver = "spriteOver";
   static var onSpriteClick = "spriteClick";
   static var onSpriteClickUp = "onSpriteClickUp";
   var mouseOvered = false;
   function SpriteFocus(targ, ft, rt)
   {
      lol.events.LEventDispatcher.initialize(this);
      Mouse.addListener(this);
      this.target = targ;
      this.flareTarget = !ft ? targ : ft;
      this.runtime = rt;
      this.color = "neutral";
      this.startPC();
   }
   function activate(a)
   {
      if(a != this.activated)
      {
         this.activated = a;
         if(a)
         {
            this.onMouseDown = this.__onMouseDown;
            this.onMouseMove = this.__onMouseMove;
         }
         else
         {
            this.flare(false);
            this.mouseOvered = false;
            this.bitmap.dispose();
            delete this.onMouseDown;
            delete this.onMouseMove;
         }
      }
   }
   function __onMouseDown()
   {
      if(this.chekOver())
      {
         this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteClick});
      }
   }
   function __onMouseUp()
   {
      if(this.chekOver())
      {
         this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteClickUp});
      }
   }
   function __onMouseMove()
   {
      if(this.chekOver())
      {
         if(!this.mouseOvered)
         {
            this.mouseOvered = true;
            this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteOver,over:this.mouseOvered});
            return undefined;
         }
      }
      else if(this.mouseOvered)
      {
         this.mouseOvered = false;
         this.dispatchEvent({type:lol.display.SpriteFocus.onSpriteOver,over:this.mouseOvered});
         return undefined;
      }
   }
   function chekOver()
   {
      var _loc3_;
      var _loc6_;
      var _loc5_;
      var _loc4_;
      if(this.flareTarget.hitTest(_root._xmouse,_root._ymouse,false) && this.target)
      {
         if(this.runtime || !this.bitmap)
         {
            this.drawBitmap();
         }
         _loc3_ = new flash.geom.Point(0,0);
         _loc6_ = this.flareTarget.getRect().xMin;
         _loc5_ = this.flareTarget.getRect().yMin;
         _loc4_ = new flash.geom.Point(this.flareTarget._xmouse,this.flareTarget._ymouse);
         if(this.bitmap.hitTest(_loc3_,128,_loc4_))
         {
            return true;
         }
         return false;
      }
      return false;
   }
   function flare(f)
   {
      var _loc2_;
      if(f)
      {
         _loc2_ = new flash.filters.GlowFilter(this.__color,100,3,3,4,1);
         this.flareTarget.filters = new Array(_loc2_);
      }
      else
      {
         this.flareTarget.filters = new Array();
      }
   }
   function set color(cs)
   {
      switch(cs)
      {
         case "enemy":
            this.__color = 14963539;
            break;
         case "friend":
            this.__color = 3701304;
            break;
         case "neutral":
            this.__color = 16645995;
            break;
         default:
            this.__color = 16777215;
      }
   }
   function drawBitmap()
   {
      var _loc5_ = this.flareTarget._width;
      var _loc6_ = this.flareTarget._height;
      var _loc2_ = new flash.geom.Matrix();
      var _loc4_ = this.flareTarget.getRect().xMin;
      var _loc3_ = this.flareTarget.getRect().yMin;
      _loc2_.translate(- _loc4_,- _loc3_);
      this.bitmap.dispose();
      this.bitmap = new flash.display.BitmapData(_loc5_,_loc6_,true,0);
      this.bitmap.draw(this.flareTarget,_loc2_);
   }
   function kill()
   {
      Mouse.removeListener(this);
      this.bitmap.dispose();
      this.activate(false);
      delete this.onMouseDown;
      delete this.onMouseMove;
      this.flare(false);
      this.flareTarget.filters = new Array();
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("aaaSpriteFocus_" + this.target._name + "_" + this.spt + "_" + this.bitmap,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
