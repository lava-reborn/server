class lol.core.location.FireAck
{
   var _critical;
   var _dmg;
   var _hex;
   var _sdmg;
   var _targetID;
   var _type;
   var _x;
   var _y;
   static var TARGET = "target";
   static var WALL = "wall";
   static var POINT = "point";
   function FireAck(pType)
   {
      if(pType == lol.core.location.FireAck.TARGET || pType == lol.core.location.FireAck.WALL || pType == lol.core.location.FireAck.POINT)
      {
         this._type = pType;
      }
   }
   function get type()
   {
      return this._type;
   }
   function set targetID(id)
   {
      if(this._type == lol.core.location.FireAck.TARGET)
      {
         this._targetID = id;
      }
   }
   function get targetID()
   {
      return this._targetID;
   }
   function set dmg(d)
   {
      if(this._type == lol.core.location.FireAck.TARGET)
      {
         this._dmg = !d ? 0 : d;
      }
   }
   function get dmg()
   {
      return this._dmg;
   }
   function set sdmg(sd)
   {
      if(this._type == lol.core.location.FireAck.TARGET)
      {
         this._sdmg = !sd ? 0 : sd;
      }
   }
   function get sdmg()
   {
      return this._sdmg;
   }
   function set critical(c)
   {
      if(this._type == lol.core.location.FireAck.TARGET)
      {
         this._critical = Boolean(c);
      }
   }
   function get critical()
   {
      return this._critical;
   }
   function set hex(h)
   {
      if(this._type == lol.core.location.FireAck.WALL)
      {
         this._hex = h;
      }
   }
   function get hex()
   {
      return this._hex;
   }
   function set x(px)
   {
      if(this._type == lol.core.location.FireAck.POINT)
      {
         this._x = px;
      }
   }
   function get x()
   {
      return this._x;
   }
   function set y(py)
   {
      if(this._type == lol.core.location.FireAck.POINT)
      {
         this._y = py;
      }
   }
   function get y()
   {
      return this._y;
   }
}
