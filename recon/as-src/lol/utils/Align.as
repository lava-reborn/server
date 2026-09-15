class lol.utils.Align
{
   var arr;
   function Align()
   {
      if(arguments[0] instanceof Array)
      {
         this.arr = arguments[0];
      }
      else
      {
         this.createArray(arguments[0],arguments[1]);
      }
   }
   function createArray(target_mc, type)
   {
      this.arr = new Array();
      var _loc3_ = !type ? Object : type;
      for(var _loc4_ in target_mc)
      {
         if(target_mc[_loc4_] instanceof _loc3_)
         {
            this.arr.unshift(target_mc[_loc4_]);
         }
      }
   }
   function getArray()
   {
      return this.arr;
   }
   function applyToArray(prop, val)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         this.arr[_loc2_][prop] = val;
         _loc2_ = _loc2_ + 1;
      }
   }
   function vAlign(dy, x, rel, align)
   {
      this.arr[0]._x = 0;
      this.arr[0]._y = 0;
      var _loc3_ = !align ? "left" : align;
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         if(rel)
         {
            this.arr[_loc2_]._y = this.arr[_loc2_ - 1]._y + this.arr[_loc2_ - 1]._height + dy;
         }
         else
         {
            this.arr[_loc2_]._y = _loc2_ * dy;
         }
         if(_loc3_ == "left")
         {
            this.arr[_loc2_]._x = x;
         }
         else if(_loc3_ == "right")
         {
            this.arr[_loc2_]._x = x - this.arr[_loc2_]._width;
         }
         else if(_loc3_ == "center")
         {
            this.arr[_loc2_]._x = (x - this.arr[_loc2_]._width) / 2;
         }
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function hAlign(dx, y, rel, align)
   {
      this.arr[0]._x = 0;
      this.arr[0]._y = 0;
      var _loc3_ = !align ? "top" : align;
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         if(rel)
         {
            this.arr[_loc2_]._x = this.arr[_loc2_ - 1]._x + this.arr[_loc2_ - 1]._width + dx;
         }
         else
         {
            this.arr[_loc2_]._x = _loc2_ * dx;
         }
         if(_loc3_ == "top")
         {
            this.arr[_loc2_]._y = y;
         }
         else if(_loc3_ == "bottom")
         {
            this.arr[_loc2_]._y = y - this.arr[_loc2_]._height;
         }
         else if(_loc3_ == "center")
         {
            this.arr[_loc2_]._y = (y - this.arr[_loc2_]._height) / 2;
         }
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function colAlign(num, dx, dy, halign, valign)
   {
      var _loc6_ = !halign ? "left" : halign;
      var _loc5_ = !valign ? "top" : valign;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.arr.length)
      {
         _loc3_ = _loc2_ % num;
         if(_loc6_ == "left")
         {
            this.arr[_loc2_]._x = dx * _loc3_;
         }
         else if(_loc6_ == "right")
         {
            this.arr[_loc2_]._x = dx * _loc3_ - this.arr[_loc2_]._width;
         }
         else if(_loc6_ == "center")
         {
            this.arr[_loc2_]._x = dx * _loc3_ - this.arr[_loc2_]._width / 2;
         }
         if(_loc5_ == "top")
         {
            this.arr[_loc2_]._y = dy * (_loc2_ - _loc3_) / num;
         }
         else if(_loc5_ == "bottom")
         {
            this.arr[_loc2_]._y = dy * (_loc2_ - _loc3_) / num - this.arr[_loc2_]._height;
         }
         else if(_loc5_ == "center")
         {
            this.arr[_loc2_]._y = dy * (_loc2_ - _loc3_) / num - this.arr[_loc2_]._height / 2;
         }
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function rowAlign(num, dx, dy, halign, valign)
   {
      var _loc6_ = !halign ? "left" : halign;
      var _loc5_ = !valign ? "top" : valign;
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.arr.length)
      {
         _loc3_ = _loc2_ % num;
         if(_loc6_ == "left")
         {
            this.arr[_loc2_]._x = dx * (_loc2_ - _loc3_) / num;
         }
         else if(_loc6_ == "right")
         {
            this.arr[_loc2_]._x = dx * (_loc2_ - _loc3_) / num - this.arr[_loc2_]._width;
         }
         else if(_loc6_ == "center")
         {
            this.arr[_loc2_]._x = dx * (_loc2_ - _loc3_) / num - this.arr[_loc2_]._width / 2;
         }
         if(_loc5_ == "top")
         {
            this.arr[_loc2_]._y = dy * _loc3_;
         }
         else if(_loc5_ == "bottom")
         {
            this.arr[_loc2_]._y = dy * _loc3_ - this.arr[_loc2_]._height;
         }
         else if(_loc5_ == "center")
         {
            this.arr[_loc2_]._y = dy * _loc3_ - this.arr[_loc2_]._height / 2;
         }
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function translate(dx, dy)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         this.arr[_loc2_]._x += dx;
         this.arr[_loc2_]._y += dy;
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function rotate(degree, center)
   {
      var _loc9_ = center != undefined ? center.x : 0;
      var _loc8_ = center != undefined ? center.y : 0;
      var _loc3_ = degree * 3.141592653589793 / 180;
      var _loc2_ = 0;
      var _loc5_;
      var _loc4_;
      var _loc7_;
      var _loc6_;
      while(_loc2_ < this.arr.length)
      {
         _loc5_ = this.arr[_loc2_]._x - _loc9_;
         _loc4_ = this.arr[_loc2_]._y - _loc8_;
         _loc7_ = _loc5_ * Math.cos(_loc3_) - _loc4_ * Math.sin(_loc3_);
         _loc6_ = _loc4_ * Math.cos(_loc3_) + _loc5_ * Math.sin(_loc3_);
         this.arr[_loc2_]._x = _loc7_ + _loc9_;
         this.arr[_loc2_]._y = _loc6_ + _loc8_;
         this.arr[_loc2_]._x = Math.round(this.arr[_loc2_]._x);
         this.arr[_loc2_]._y = Math.round(this.arr[_loc2_]._y);
         _loc2_ = _loc2_ + 1;
      }
   }
   function clearAll()
   {
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         if(this.arr[_loc2_] instanceof MovieClip)
         {
            this.arr[_loc2_].removeMovieClip();
         }
         else if(this.arr[_loc2_] instanceof TextField)
         {
            this.arr[_loc2_].removeTextField();
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function get length()
   {
      return this.arr.length;
   }
   function set length(§null§)
   {
      return undefined;
   }
   function getMax(prop)
   {
      var _loc3_ = new Object();
      var _loc4_ = 0;
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         if(this.arr[_loc2_][prop] >= _loc4_)
         {
            _loc4_ = this.arr[_loc2_][prop];
            _loc3_.obj = this.arr[_loc2_];
            _loc3_.id = _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function getMin(prop)
   {
      var _loc3_ = new Object();
      var _loc4_ = this.arr[0][prop];
      var _loc2_ = 0;
      while(_loc2_ < this.arr.length)
      {
         if(this.arr[_loc2_][prop] <= _loc4_)
         {
            _loc4_ = this.arr[_loc2_][prop];
            _loc3_.obj = this.arr[_loc2_];
            _loc3_.id = _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
}
