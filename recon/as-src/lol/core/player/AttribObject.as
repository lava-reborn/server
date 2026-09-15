class lol.core.player.AttribObject
{
   var _value_bonus;
   var value;
   function AttribObject()
   {
   }
   function get bonus()
   {
      var _loc2_ = this.value_bonus - this.value;
      return _loc2_;
   }
   function get level()
   {
      return this.value_bonus;
   }
   function get value_bonus()
   {
      return this._value_bonus;
   }
   function set value_bonus(value)
   {
      this._value_bonus = value;
   }
}
