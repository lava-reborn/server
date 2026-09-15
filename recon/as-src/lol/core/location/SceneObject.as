class lol.core.location.SceneObject
{
   var _point;
   var _sprite;
   var front_arr;
   var left;
   var right;
   var type;
   static var STATIC = 0;
   static var DYNAMIC = 1;
   function SceneObject(t)
   {
      this.type = t;
   }
   function set front(farr)
   {
      this.front_arr = farr;
      var _loc2_ = this.front_arr.length - 1;
      if(_loc2_ > 0)
      {
         this.front_arr.sortOn("x",Array.NUMERIC);
      }
      this.left = this.front_arr[0];
      this.right = this.front_arr[_loc2_];
   }
   function get front()
   {
      return this.front_arr;
   }
   function getFrontHex(param, val)
   {
      var _loc3_ = this.front.length;
      var _loc2_;
      _loc2_ = 0;
      while(_loc2_ < _loc3_)
      {
         if(this.front[_loc2_][param] == val)
         {
            return this.front[_loc2_];
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function setPoint(x, y)
   {
      this.point = {x:x,y:y};
   }
   function set point(p)
   {
      this._point = p;
      if(this.front.length == 1 || !this.front)
      {
         this.front = [this._point];
      }
   }
   function get point()
   {
      return this._point;
   }
   function set sprite(s)
   {
      this._sprite = s;
   }
   function get sprite()
   {
      return this._sprite;
   }
   function onMouseDown()
   {
      if(this._sprite.hitTest(_root._xmouse,_root._ymouse))
      {
         lol.core.SceneShifter.locationScreen.displayLoc.lBuilder.drawSOFronts(this);
      }
   }
}
